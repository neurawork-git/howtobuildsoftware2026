# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-stack-compiler-selection/.claude/PRPs/plans/stack-compiler-selection.plan.md`
**Branch:** `feature/stack-compiler-selection`
**Status:** `COMPLETE`

## Outcome

The component decision now has a place to land. `compliance-base/scripts/stack.py` gained a
fourth entry point, `--apply-selection`, plus an eighth decision-owned field `chosen_from` —
the hash of the catalog capability a choice was made against — and per-capability staleness in
`gaps()`. `stack-base/` gained an LLM-free selection pass: `scripts/selection.py` renders the
recorded ranking as an editable markdown sheet (one block per applicable capability, its
components in best-fit-first order with the reason for each position, and a blank `choice:`
line), reads the filled sheet back, gates it against the closed pool, and writes through the
schema owner.

Verified on the live catalog: 41 applicable capabilities rendered, two confirmed choices
applied, the mandatory gap dropped 38 → 36, and a single decision-relevant catalog edit
reopened exactly that one choice while a prose-only edit reopened none.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s compliance-compiler/tests` | `passed` | Ran 125 tests, OK (baseline 106; +19 for `capability_hash`, `apply_selection`, `stale_choices`, `chosen_from` carry-over) |
| `python3 -m unittest discover -s stack-compiler/tests` | `passed` | Ran 131 tests, OK (baseline 92; +39 for `selection_lib`, the CLI, and the end-to-end apply) |
| `python3 -m unittest discover -s _shared/tests` | `passed` | Ran 34 tests, OK |
| `python3 -m unittest discover -s knowledge-compiler/tests` | `passed` | Ran 15 tests, OK |
| `python3 -m unittest discover -s claudemd-lerner/tests` | `passed` | Ran 13 tests, OK |
| `cd stack-base && uvx ruff check` | `passed` | 2 errors, both pre-existing `PLW1510` in `_shared/{gitctx,recon}.py`; identical count on `main`. No finding in the new files. |
| `cd compliance-base && uvx ruff check` | `passed` | 40 errors, identical count on `main`, none in `scripts/stack.py` |
| `diff …/compliance-compiler/payload/scripts/stack.py compliance-base/scripts/stack.py` | `passed` | no output — the two copies are identical |
| `test_payload_drift` (in the stack-compiler suite) | `passed` | payload and `stack-base/` match for all 7 scripts, `AGENTS.md`, `pyproject.toml`, `VERSION` |
| Runtime: render the real sheet | `passed` | `41 applicable capability/-ies: 0 chosen, 41 undecided`; 41 `##` blocks, no scoped-out key, every `choice:` blank |
| Runtime: apply two confirmed choices | `passed` | `2 choice(s) recorded, 39 applicable capability/-ies still undecided`; gap line `36 of 38` (was `38 of 38`); both entries carry `chosen`, `chosen_from`, and unchanged `ranked_from`/`scoped_from` |
| Runtime: per-capability staleness | `passed` | one component's `license` changed → `! 1 chosen component(s) were decided against an older version of their capability: gdpr/accountability-liability-governance-evidence`; a `stack_notes` rewording on the other chosen capability reported nothing |
| Runtime: revert | `passed` | `git status --porcelain compliance-base/catalog/` empty — the real 41-capability pass is the engineer's to make |

## Deviations and Decisions

- **`select.py` → `selection.py`, `select_lib.py` → `selection_lib.py`.** The plan named the
  modules `select*.py`. That name is unusable: `scripts/` is first on `sys.path` for every
  script run out of it, so a module named `select` shadows the stdlib `select` that
  `selectors` — and through it `asyncio` — imports. It broke `scope.py` and `rank.py` at
  import time (`AttributeError: partially initialized module 'selectors'`), caught by their
  existing preflight tests. The reason is recorded in `selection.py`'s docstring and in the
  root `CLAUDE.md` so it is not "cleaned up" later. Report/sheet names follow:
  `reports/selection-sheet-<date>.md` (the sheet) and `reports/selection-<date>.md` (the run
  report).
- **`is_scoped` moved from `rank.py` to `rank_lib.py`** as planned; the two tests that
  addressed `rank.is_scoped` now address `rank_lib.is_scoped`.
- **`selection_lib` builds on `rank_lib.rankable_universe` and reuses `rank_lib.license_check`**
  rather than re-deriving the catalog join or the license policy. `selectable_universe` takes
  `(stack, capabilities)`, not `(stack)` as the plan sketched.
- **The gate has no separate `not_applicable` bucket.** A choice for a scoped-out capability is
  not in the universe, so it surfaces as `unknown`; `stack.py` distinguishes the two precisely
  on the write side, where the difference is actionable. One bucket less, no information lost.
- **Added one end-to-end CLI test beyond the plan** (`TestSelectionReachesTheSchemaOwner`):
  it installs both engines into a temp repo and drives sheet → parse → gate → real
  `stack.py --apply-selection`, proving the two engines agree on field names. The plan left
  AC2 to two separate unit layers; this closes the seam between them.
- **The `selection.py` CLI tests copy the payload scripts into a temp install layout** and run
  them from there, because the script resolves `_shared` (the write guard) from its own parent
  directory. `rank.py`/`scope.py` tests never reach that import, so they run the payload copy
  directly; no production code changed for this.
- **No `VERSION` bump**, matching Phase 2 (`git show 2da4b38 --stat`), which changed both
  engines' payloads without advancing either counter. The counters advance when Phase 5 ships
  the installer.
- **`compliance-base/CLAUDE.md`'s ownership bullet was stale before this change** (it named one
  `stack.py` apply mode and five carried fields; Phase 2 had added two more). Rewritten once to
  name all three apply modes and all eight fields.

## Completion Gate

- **Plan tasks complete:** `Yes` — all five, including the runtime pass on the live catalog.
- **Acceptance criteria satisfied:** `Yes` — AC1 (sheet render), AC2 (filled sheet → tracked
  decision, gap drops by exactly the count applied), AC3 (closed pool and applicability
  enforced twice, nothing written on failure), AC4 (per-capability staleness, prose-insensitive),
  AC5 (ranking/scoping/pool untouched, `chosen_from` carried by `scaffold()`, no API key or
  network in the selection pass, both mirror pairs identical).
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The selection pass end to end: `stack.py`'s `capability_hash`/`apply_selection`/`chosen_from`/
`stale_choices` plus its payload mirror and tests; `stack-base/scripts/selection{,_lib}.py` plus
their payload mirrors and two new test modules; `is_scoped` relocated to `rank_lib`; the
`AGENTS.md` boundary correction in both copies; root `CLAUDE.md` and `compliance-base/CLAUDE.md`;
the plan file and the PRD phase row. No catalog data — the real selection pass is the
engineer's.

## Delivery

- **Commits:** `8ba1c6d feat(stack-compiler): the chosen component per capability is now a tracked decision`; `a8ae59f docs(prd): record Phase 3 implementation report and PR`
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/28
- **Base / Head:** `main <- feature/stack-compiler-selection`
- **Source PRD:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/prds/stack-compiler.prd.md` — Phase 3, row updated to `in-progress` with plan/report/PR links
- **Tracked follow-ups:** `None`
