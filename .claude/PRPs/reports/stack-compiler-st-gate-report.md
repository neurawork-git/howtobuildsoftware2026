# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/stack-compiler-st-gate.plan.md`
**Branch:** `feature/stack-compiler-st-gate`
**Status:** `COMPLETE`

## Outcome

Every catalog component a live PRD or PRP plan names is now classified against
`compliance-base/catalog/stack.json` at write time. A second `PostToolUse` hook,
`stack-base/hooks/st-post-tooluse.py`, runs beside the existing `co-` one: it matches
live `.claude/PRPs/prds/*.prd.md` and `.claude/PRPs/plans/**/*.plan.md` writes, runs a
pure `scripts/gate_lib.py` precheck inline (~18 ms on a real PRD, no API key, no
network), and emits a one-paragraph advisory as `additionalContext` naming the
off-stack components, their capability, and the component `stack.json` records
instead. When — and only when — the document's content hash changed and the stack
carries choices to enforce, it spawns `scripts/validate.py` detached: one SDK agent
separates a *proposal* from a passing *mention* and names the applicable capabilities
the document ignores, while the script filters the agent's output against the known
sets and owns the exit code.

The gate reads `stack.json` and writes nothing to it; `chosen` is still recorded only
by `scripts/selection.py` through `compliance-base/scripts/stack.py`.

Three real choices were recorded through the selection pass so the gate has a
non-empty allowlist in this repo (the human decision Task 7 calls for): the two
change-management capabilities and the outsourced-development-oversight capability now
record this repository's actual GitHub pull-request flow. The other 38 applicable
capabilities stay deliberately undecided.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s stack-compiler/tests` | `passed` | `Ran 188 tests … OK` (baseline 134; +54 across `test_gate_lib.py`, `test_gate_hook.py`, `test_gate_validate.py`, `test_payload_drift.py`) |
| `… discover -s _shared/tests` | `passed` | `Ran 34 tests … OK` |
| `… discover -s knowledge-compiler/tests` | `passed` | `Ran 15 tests … OK` |
| `… discover -s claudemd-lerner/tests` | `passed` | `Ran 13 tests … OK` |
| `… discover -s compliance-compiler/tests` | `passed` | `Ran 125 tests … OK` |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | `passed` | `Ran 9 tests … OK` |
| `cd stack-base && uvx ruff check` | `passed` | 3 findings, all pre-existing in kind: 2 `PLW1510` in the copied `_shared/`, 1 `I001` on the new hook — the identical `I001` the shipped `compliance-base/hooks/co-post-tooluse.py` already carries (the two ruff configs disagree on whether `_shared` is first-party) |
| `cd plugins/neurawork-cc-harness/engines/stack-compiler && uvx ruff check` | `passed` | 1 finding, pre-existing (`RUF012` in `tests/test_rank.py`); no new-file findings |
| `diff -r -x __pycache__ …/payload/scripts stack-base/scripts` and `… /payload/hooks stack-base/hooks` | `passed` | no output |
| Drift guard exercised deliberately | `passed` | removing `payload/hooks/st-post-tooluse.py` fails `test_hooks_are_identical` (`payload/hooks and stack-base/hooks hold different files`); a one-line byte change fails it too. Both reverted, not committed |
| `printf '%s' '{"tool_name":"Read"}' \| python3 stack-base/hooks/st-post-tooluse.py; echo $?` | `passed` | exits `0`, prints nothing |
| `python3 -c "import json;json.load(open('.claude/settings.json'))"` | `passed` | valid JSON; `PostToolUse` now lists `co-post-tooluse.py`, `st-post-tooluse.py` — the `co-` entry byte-identical |
| Live off-stack advisory (AC1) on a throwaway PRD naming Argo CD | `passed` | `Stack gate: 4 catalog component(s) named, 0 of them this product's recorded choice. 2 off-stack: Argo CD (\`iso27001/change-release-management-for-production\` records GitHub (Enterprise) …); Argo CD (GitOps) (\`soc2/change-management-secure-sdlc\` records GitHub (branch protection + CODEOWNERS + required reviews)); 2 filling a capability still undecided.` — precheck 18 ms |
| Live `scripts/validate.py` run on that PRD (AC4) | `passed` | one agent, `cost_usd 0.27`, wrote `reports/st-gate-smoke.prd.md` + `reports/st-gate-smoke.prd.stack.json`, script-side set math found the 2 off-stack proposals, **exit 1** |
| Debounce on unchanged content (AC3) | `passed` | after the run, `should_spawn` is `False` for the same hash `41d7c9ccf9a2e088`; the ledger entry carries `spawned_at` + `completed_at` + `ok: false` and gains no second stamp |
| False-positive floor (AC2) | `passed` | case-sensitive closed-pool scan over the live catalog: 5 components on `stack-compiler.prd.md`, 2 on the Phase-3 plan, **0** on `CLAUDE.md` and `docs/ARCHITECTURE.md` — asserted in `test_gate_lib.py` against the real catalog when present |

The throwaway PRD and its two report files were deleted afterwards; `stack-base/reports/`
is gitignored.

## Deviations and Decisions

- **`gate_lib.verdict` owns the set math, not `validate.py`.** The plan put the
  filtering in `validate.py`; it lives in `gate_lib` instead so it is unit-testable
  straight from `payload/scripts` without a temp install (`validate.py` imports
  `_shared.repo_guard`). Same split, one import lower — and it matches the module's
  stated reason for existing: it serves two entry points.
- **A proposed component is re-classified rather than looked up.** `verdict` filters
  the agent's `proposed` list against the catalog's own component names and then runs
  `classify` on it, so a proposal the deterministic scan missed is still judged and an
  invented name is dropped before any set math.
- **License verdicts are worst-case across a component's catalog records.** A
  component listed under two capabilities can carry two roles; taking whichever record
  was read first would let a permissive listing excuse a role the policy does not
  permit.
- **`_LICENSE_ALIASES`-style component alias table has two entries** (`Postgres`,
  `ArgoCD`). Kept deliberately tiny: a missing alias costs a missed mention, never a
  false accusation.
- **Inside a linked worktree the hook reads the *main checkout's* catalog**, exactly
  as `co-post-tooluse.py` does, and writes its ledger there. Consequence for this
  branch: the live hook running in this worktree sees `main`'s `stack.json` (0 chosen)
  and therefore never spawns. The AC1/AC3/AC4 evidence above was produced by running
  the gate against this branch's catalog directly (`scripts/validate.py` and the pure
  `gate_lib` path), which is what an installed non-worktree session executes.
- **Lint is not clean-at-zero in either directory and was not made so.** The
  pre-existing findings listed above are outside this plan's scope; the new files add
  none beyond the `I001` the shipped `co-` hook already carries.

## Completion Gate

- **Plan tasks complete:** `Yes` (1–7)
- **Acceptance criteria satisfied:** `Yes` (AC1–AC5)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The `st-` component gate and its wiring:

- new `stack-base/scripts/gate_lib.py`, `stack-base/scripts/validate.py`,
  `stack-base/hooks/st-post-tooluse.py`
- `stack-base/scripts/config.py` — `HOOKS_DIR`, `GATE_STATE_FILE`, the three new
  config defaults, `gate_mode()`
- `stack-base/config.json` + `engines/stack-compiler/config.default.json` — the same
  keys
- `stack-base/AGENTS.md` — the `## Gate rules` section
- the byte-identical `payload/` mirror of all of the above, plus `VERSION` 1 → 2 on
  both sides
- new `tests/test_gate_lib.py`, `tests/test_gate_hook.py`, `tests/test_gate_validate.py`;
  `tests/test_payload_drift.py` extended to `hooks/`
- `.claude/settings.json` — the `st-` `PostToolUse` entry beside the `co-` one
- `compliance-base/catalog/stack.json` — the three recorded choices (data, written by
  `selection.py` through `stack.py --apply-selection`)
- `.claude/PRPs/prds/stack-compiler.prd.md` — Phase 4 status
- the plan itself, `.claude/PRPs/plans/stack-compiler-st-gate.plan.md`

Not part of this scope and left uncommitted: `.claude/PRPs/specs/grillme.spec.md`,
unrelated work carried into the worktree from the main checkout.

## Delivery

- **Commits:** `Not created`
- **Pull Request:** `Not opened`
- **Base / Head:** `main <- feature/stack-compiler-st-gate`
- **Source PRD:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/prds/stack-compiler.prd.md`, Phase 4
- **Tracked follow-ups:** `None`
