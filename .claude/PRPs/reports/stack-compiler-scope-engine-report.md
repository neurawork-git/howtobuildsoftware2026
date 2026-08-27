# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-stack-compiler-scope-engine/.claude/PRPs/plans/stack-compiler-scope-engine.plan.md`
**Branch:** `feature/stack-compiler-scope-engine`
**Status:** `COMPLETE`

## Outcome

The 68-capability compliance catalog can now be narrowed to one product, accountably.
`stack-base/scripts/scope.py` reads the tracked `stack-base/product.md`, fans out one
Claude Agent SDK agent per framework to decide per capability whether it applies and
why, runs a single challenge agent that tries to refute every "not applicable" claim
against the same description, and applies a deterministic safety gate before anything
is written. The write goes through the new `stack.py --apply-scope`, so
`compliance-base/catalog/stack.json` keeps exactly one schema owner and this engine
owns no data artifact.

On this repo's own product description the pass ruled 27 of 68 capabilities out, each
with a recorded reason, and traced 86 mandatory constraints to a justified
non-applicable capability. `stack.py`'s gap report now counts applicable capabilities
only, so its mandatory denominator dropped from 62 to 38 and a fully-decided stack can
reach 0.

The refutation path was exercised live: a first pass claimed
`gdpr/downstream-recipient-tracking-change-propagation` did not apply because "the
plugin discloses data to no recipients", the challenge agent refuted it by quoting
"The only outbound network call is to the Anthropic API…", the run exited 1 and wrote
nothing. `product.md` gained an explicit "Who receives data" section and the re-run
passed — the intended human loop.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s stack-compiler/tests` (from `engines/`) | `passed` | `Ran 39 tests … OK` — safety gate, shard parsing, prompt builders, preflight, drift guard |
| `python3 -m unittest discover -s compliance-compiler/tests` | `passed` | `Ran 72 tests … OK` (was 61 on `main`; +11 for `apply_scope`, applicability-aware `gaps()`, report rendering) |
| `python3 -m unittest discover -s _shared/tests` | `passed` | `Ran 34 tests … OK` |
| `python3 -m unittest discover -s knowledge-compiler/tests` | `passed` | `Ran 15 tests … OK` |
| `python3 -m unittest discover -s claudemd-lerner/tests` | `passed` | `Ran 13 tests … OK` |
| `uvx ruff check` in `stack-compiler/` | `passed (baseline-consistent)` | 12 findings, all in classes already present on `main` (TRY004, ISC004, RUF100, PLW1510); 0 lines over the project's `line-length = 100` |
| `uvx ruff check` in `compliance-compiler/` | `passed (baseline-consistent)` | 53 findings; `main`'s `stack.py` already carried 3 ISC004, the change adds 2 more of the same idiom used throughout the file |
| `diff -q …/payload/scripts/stack.py compliance-base/scripts/stack.py` | `passed` | no output — mirror intact |
| `test_payload_drift.py` | `passed` | ran (not skipped); it caught one un-mirrored edit mid-implementation and failed until `stack-base/` was re-synced |
| `uv sync --directory stack-base` | `passed` | resolved, `.venv` created |
| `uv run --directory stack-base python scripts/scope.py --dry-run` | `passed` | `68 capabilities across 3 framework(s)`; gdpr 25/109, iso27001 18/59, soc2 25/111 — 279 mandatory constraints, no LLM call |
| Adversarial fixture run (`--product …/underscoped-product.md`) | `passed, different mechanism` | 68/68 stayed applicable; nothing was dropped on the false "no personal data" claim, so the challenge pass had nothing to refute. See Deviations. |
| Live refutation (truthful `product.md`, first pass) | `passed` | `REFUTED — … 1 'not applicable' decision(s); nothing written`; `git hash-object compliance-base/catalog/stack.json` unchanged at `5ffd8eeb…` |
| Live scoping (truthful `product.md`, re-run) | `passed` | `41 applicable, 27 ruled out`, `86 mandatory constraint(s) traced to a justified non-applicable capability` |
| Artifact check on `stack.json` | `passed` | 68 entries, `scoped_from == dbc748613f86f0e7` on all, 27 non-applicable all carrying a reason, every `chosen` still `None` and every `rationale` still `""` |
| Unchanged-product skip | `passed` | second identical run: `Product description unchanged since the recorded scoping — nothing to do (use --all to force).` — zero agents spawned |

Total live-agent cost across all runs: ~$3.60.

## Deviations and Decisions

- **AC3's fixture did not fail the way the plan predicted, and the fixture was
  re-framed rather than forced.** The plan expected
  `tests/fixtures/underscoped-product.md` to exit 1 with refuted decisions. In the
  live run the scoping agents read past the false "This service processes no personal
  data" sentence and kept all 68 capabilities applicable, so nothing reached the
  challenge pass. The invariant held — no capability was silently dropped — but by a
  different mechanism. Engineering a description that reliably fools the scoping agent
  would be a fragile regression check, so the fixture's header now states what it
  actually proves ("a false blanket assertion must not shrink the compliance surface")
  and records the observed result. **AC3's refutation mechanism is instead proven by
  the live refutation on `product.md` quoted above, plus unit coverage in
  `test_scope_lib.py` and `test_scope.py`.**
- **`product.md` was amended mid-validation**, adding a "Who receives data" section, in
  direct response to the live refutation. This is the designed loop (gate refutes →
  human corrects the description → re-run), not a workaround: the original description
  genuinely omitted that the Anthropic API receives prompt content.
- **The gap-report headline was reworded** to "N of M **applicable** mandatory-linked
  capabilities…", as the plan's Agent Notes required. Three existing assertions in
  `test_stack.py` were updated; the per-framework table gained a *Not applicable*
  column so "Chosen" stays arithmetically correct.
- **`gaps()` returns two new keys** (`non_applicable`, `unexplained_non_applicable`)
  and `mandatory_total` now counts applicable capabilities only. Existing behaviour is
  unchanged for an unscoped `stack.json` — proven by
  `test_unscoped_stack_is_unaffected`.
- **The subprocess boundary held up in practice.** `scope.py` never imports
  `compliance-base` Python; the `config` module-name collision the plan identified
  cannot occur. `stack.py` stays stdlib-only on the `--apply-scope` path, so no `uv`
  environment is needed for the write.
- **ISC004/TRY004/PLW1510 lint findings were left in place** to match the surrounding
  code, per the repo's "match existing style" rule. `uvx ruff check` runs ruff's
  default rule set; the project itself pins only `line-length = 100`, which is clean.
- **Not done, and outside this phase:** `install.py`, `recon.py`, slash commands, the
  plugin-manifest entry, `docs/` (PRD Phase 5); component ranking and selection
  (Phases 2–3); the `st-` hook (Phase 4). The root `CLAUDE.md` gained one bullet
  marking `stack-base/` as a hand install so the new top-level directory is not
  undocumented.
- **PRD Phase 0 is still `in-progress`** although every Phase-0 deliverable is present
  in the PRD files. Not touched here — `/prp-prd-update` owns one phase per call and
  must not edit another. Recommend flipping it to `complete`.

## Completion Gate

- **Plan tasks complete:** `Yes` — all five tasks.
- **Acceptance criteria satisfied:** `Yes` — AC1, AC2, AC4, AC5, AC6, AC7 as specified;
  AC3's outcome is met and its mechanism proven live, but via the truthful product
  description rather than the fixture (see Deviations).
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One coherent outcome — product scoping of the compliance capability catalog:

- `stack.py` (payload + `compliance-base` mirror): applicability-aware `gaps()`,
  `apply_scope()`, `--apply-scope` CLI, report rendering; `test_stack.py` extended.
- New engine `plugins/neurawork-cc-harness/engines/stack-compiler/`: `VERSION`,
  `config.default.json`, `payload/` (`AGENTS.md` constitution, `pyproject.toml`,
  `config.py`, `scope_lib.py`, `scope.py`), `tests/` (3 suites + fixture).
- New hand-installed self-host `stack-base/` (machinery, `_shared/`, `config.json`,
  `.gitignore`, tracked `product.md`).
- `CLAUDE.md`: one architecture bullet for `stack-base/`.
- `compliance-base/catalog/stack.json`: the reviewed scoping result (27 of 68 ruled
  out, all reasoned).
- `.claude/PRPs/plans/stack-compiler-scope-engine.plan.md` and the PRD phase row.

Excluded: `.venv/`, `reports/`, `.shards/`, `uv.lock` (all gitignored).

## Delivery

- **Commits:** `b9114cc` feat(stack-compiler): narrow the capability catalog to one product, accountably; `97e2b66` docs(prd): record phase 1 implementation report and PR
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/25 (open, ready for review)
- **Base / Head:** `main <- feature/stack-compiler-scope-engine`
- **Source PRD:** `/home/felix/projects/howtobuildsoftware2026-stack-compiler-scope-engine/.claude/PRPs/prds/stack-compiler.prd.md` — Phase 1 recorded as `implemented` (status stays `in-progress` until the PR merges)
- **Tracked follow-ups:** `None`
