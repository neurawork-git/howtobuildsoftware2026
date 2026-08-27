# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-capability-validator/.claude/PRPs/plans/compliance-capability-validator.plan.md`
**Branch:** `feature/capability-validator`
**Status:** `COMPLETE`

## Outcome

A PRP plan is now checked against the derived **capability** layer, not only against constraint IDs.

- A plan declares what it delivers with one line in its `## Compliance` section —
  `**Capabilities**: gdpr/audit-logging, soc2/change-management`, or `**Capabilities**: none — <reason>`.
- **Tier 1** (`precheck.capability_precheck`, inline in the `co-` PostToolUse hook, no LLM): reports whether
  the declaration exists, whether every key resolves against `catalog/capabilities.json`, and what
  `stack.json` says about the declared keys (no chosen component / scoped out). Advisory — never blocks.
- **Tier 2** (`validate.py`, detached SDK agent): the agent judges which capabilities the plan's own content
  makes applicable and writes `reports/<plan-stem>.capabilities.json`; the script computes
  `applicable ∩ mandatory-linked − declared` and **exits non-zero** when that set is non-empty. The agent
  never asserts its own verdict, and an invented key is filtered out before the math.

Deliberately not enumerated: the 62 mandatory-linked capabilities. Mirroring the constraint tier's
"279/279 unreferenced" line at capability scale would double an already-ignored signal.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s compliance-compiler/tests` | passed | `Ran 79 tests … OK` (was 63; 16 new across `TestCapabilityDeclaration`, `TestCapabilityPrecheck`, `TestCapabilityVerdict`) |
| `python3 -m unittest discover -s _shared/tests` | passed | `Ran 34 tests … OK` |
| `python3 -m unittest discover -s knowledge-compiler/tests` | passed | `Ran 15 tests … OK` |
| `python3 -m unittest discover -s claudemd-lerner/tests` | passed | `Ran 13 tests … OK` |
| `uvx ruff check scripts/precheck.py scripts/utils.py scripts/validate.py hooks/co-post-tooluse.py` (from `compliance-base/`) | passed | 1 finding, `I001` in the hook's import block — reproduced against `git show origin/main:compliance-base/hooks/co-post-tooluse.py`, so pre-existing; my changes add zero findings |
| `python3 -c "import precheck, utils, validate"` | passed | clean import without `claude_agent_sdk` |
| **AC1** — `uv run python scripts/validate.py <fixture A: PII store, authenticated API, audit trail, no declaration>` | passed | `EXIT=1`; verdict JSON written; `applicable_total: 44`, `undeclared_mandatory: 43` keys; report's `Capabilities` section names them. Cost $2.02 |
| **AC2** — same fixture with the 44 keys declared | passed | `EXIT=0`; `applicable_total: 44` (identical set across runs), `undeclared_mandatory: []`, `declared_not_applicable: 0`. Cost $2.40 |
| **AC3** — hook on fixture A (`uv` removed from child PATH so no agent spawns) | passed | summary ends `No '**Capabilities**:' declaration found — add one to the '## Compliance' section … or **Capabilities**: none — <reason>.` |
| **AC3** — hook on fixture B | passed | `Plan declares 44 capability/capabilities (44 with no chosen component in stack.json).` |
| **AC4** — hook output on both fixtures | passed | no `decision` key present; `validate_mode: "block"` branch untouched, still keyed on unreferenced constraint IDs |
| **AC5** — degrade paths | passed | `_capability_summary({"catalog_built": False})` → `''`; `_load_verdict` → `None` for missing, corrupt (`{not json`), and wrong-shape (`{"applicable": "not-a-list"}`) input; `main()` then prints an explicit skip line and returns 0 |
| **AC6** — tree parity | passed | `diff -rq compliance-base/scripts payload/scripts --exclude=__pycache__` silent; hook and `AGENTS.md` identical |
| `sync_catalog_seed.py --check` | passed | `seed in sync with compliance-base/catalog`, exit 0 |
| `git status --porcelain` | passed | exactly the 11 intended files; fixtures and their reports removed |

Real-catalog smoke: `precheck.precheck()` on this plan itself against the live 359-constraint /
68-capability catalog → `declared_none: True`, `mandatory_linked_total: 62`, no crash.

## Deviations and Decisions

- **`known_capabilities` is public, not private.** The plan put a `_known_capabilities` helper in
  `precheck.py`; `validate.py` needs the same filtered catalog + key index, so it is exported rather than
  duplicated. One owner of the framework-filtering rule.
- **`_capabilities_text` takes the prepared index and mandatory set** instead of re-deriving them from the
  frameworks list — it was reloading `capabilities.json` twice for the same answer.
- **`capability_verdict` gained an optional `known_keys` argument.** The plan named invented-key filtering
  as a risk mitigation but left it unplaced; putting it in the pure function keeps it unit-testable
  (`test_invented_key_is_filtered_out_before_the_math`).
- **Declaration parsing is comma-token-exact, not regex-scan.** Scanning the paragraph for `<a>/<b>` would
  turn a path like `.claude/PRPs` in adjacent prose into a phantom unknown key. Only tokens that are
  *entirely* a key are taken (`test_prose_with_a_slash_never_becomes_a_key`). The declaration still reads to
  the next blank line, so a wrapped list works.
- **`validate.py` deletes a stale verdict before the run** so a failed agent cannot be judged on the
  previous run's file.
- **Pre-existing `I001` in the hook's import block left alone** — the import order is load-bearing
  (`recursion_guard()` must run before `_shared.gitctx` is imported), and it is outside this change.
- **Task 6's fixtures were run from the repo root path**: `validate.py` resolves a relative plan path against
  `ROOT_DIR.parent`, so `../.claude/...` fails; absolute paths were used. No code change — existing behavior.

## Completion Gate

- **Plan tasks complete:** `Yes` (6 of 6)
- **Acceptance criteria satisfied:** `Yes` (AC1–AC6, evidence above)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The capability-coverage gate on plan writes, in both trees:

- `compliance-base/scripts/utils.py` — `load_capability_catalog` / `load_stack` readers (never raise).
- `compliance-base/scripts/precheck.py` — `declared_capabilities`, `known_capabilities`,
  `capability_precheck`, `capability_verdict`; `precheck()` gains a `capabilities` sub-dict.
- `compliance-base/hooks/co-post-tooluse.py` — `_capability_summary` appended to the advisory summary.
- `compliance-base/scripts/validate.py` — capability catalog in the prompt, verdict JSON, exit code.
- `compliance-base/AGENTS.md` — `## Capability validation rules (plan → capability verdict)`.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/…` — byte-identical mirrors.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_shards_precheck.py` — 16 new tests.

Not included (other phases): PRD-write matching + debounce (harness PRD Phase 7), component-allowlist /
license gate (`stack-compiler` Phase 4), `/co-capabilities` + docs (this PRD's Phase 4).

## Delivery

- **Commits:** `98e3fbe feat(compliance-compiler): plans are checked against the capability layer` · `16b35b0 docs(prd): record Phase 3 report and PR`
- **Pull Request:** `https://github.com/neurawork-git/howtobuildsoftware2026/pull/24` (open, ready; Analyze (python), CodeQL, GitGuardian all pass)
- **Base / Head:** `main <- feature/capability-validator`
- **Source PRD:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/prds/compliance-capabilities.prd.md` — Phase 3 `in-progress`, plan + report + PR #24 recorded (commit `16b35b0`; the PRD edit rides this branch rather than being written straight to `main`)
- **Tracked follow-ups:** `None`
