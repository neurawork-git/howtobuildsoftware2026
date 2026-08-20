# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-rules-init-baseline/.claude/PRPs/plans/nw-rules-init-baseline-rules.plan.md`
**Branch:** `feature/rules-init-baseline`
**Status:** `COMPLETE`

## Outcome

The harness can now put prescriptive working rules into a repo, and keep them.

- `/neurawork-cc-harness:nw-rules-init` (`skills/nw-rules-init/SKILL.md`) writes one
  marker-delimited block — Scope, Simplicity, Evaluation-first — into the root `CLAUDE.md`.
  It detects the repo's real test runner from six ordered signals (existing CLAUDE.md
  command → CI → `pyproject.toml` → a `unittest` tests tree → `package.json` → `go.mod`/
  `Cargo.toml`), never defaults to pytest, reports per-cluster coverage against the file it
  read, and asks before writing. Re-runs offer Replace/Keep, `--force` refreshes, and a
  second block is never written.
- `claudemd-lerner` now guards marker blocks deterministically. `payload/scripts/markers.py`
  snapshots every `owner:name` span before the SDK call in `update_one()` and `run_seed()`
  and splices the original bytes back in a `finally`, printing a `Marker guard:` line per
  restoration. Text outside the spans — the learner's real work — is never touched. The
  guard is marker-generic, so a `coding-suite:coding-discipline-init` block in someone
  else's repo is protected by the same pass.

Before this, the hand-written "Working principles" section in this repo's own `CLAUDE.md`
had no marker and no protection; the learner could reword or drop it on any run.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s claudemd-lerner/tests` (from `engines/`) | passed | Ran 27 tests, OK (13 pre-existing + 13 marker unit tests + 1 wiring test) |
| `python3 -m unittest discover -s tests` (from plugin root) | passed | Ran 15 tests, OK (9 pre-existing + 6 rules-block tests) |
| `python3 -m unittest discover -s _shared/tests` | passed | Ran 36 tests, OK |
| `python3 -m unittest discover -s knowledge-compiler/tests` | passed | Ran 15 tests, OK |
| `python3 -m unittest discover -s compliance-compiler/tests` | passed | Ran 125 tests, OK |
| `python3 -m unittest discover -s stack-compiler/tests` | passed | Ran 134 tests, OK |
| Negative control: guard `finally` removed, wiring test rerun | failed as required | `AssertionError: … not found in '…- Scope, but I reworded it…'` — the test is not vacuous; restored and rerun: OK |
| `uvx ruff check scripts/markers.py` (in `claudemd-lerner/payload`) | passed | All checks passed |
| `uvx ruff check` (in `claudemd-lerner/payload`) | 30 findings, all pre-existing | `--statistics`: LOG015 ×12, I001 ×8, UP017 ×5, BLE001 ×3, PLW1510 ×1, S110 ×1 — none in `markers.py`; the two in the files I edited (`seed.py:35` PLW1510, `update.py:164` BLE001) sit on untouched lines |
| Payload identity | passed | `diff -r --exclude=__pycache__ --exclude=.ruff_cache …/payload/scripts claudemd-lerner/scripts` → no output; `AGENTS.md` identical; both `VERSION` files read `3` |
| Docs presence | passed | `grep -n nw-rules-init` hits `CLAUDE.md:91`, `plugins/CLAUDE.md:15`, `plugins/neurawork-cc-harness/README.md:21`, `docs/INSTALL.md:140` |
| Manual — recon truthfulness on this repo | passed | Stage 1 resolves signal 1 (a command already in `CLAUDE.md:29-41`): the four `unittest discover` lines plus the plugin-root suite — **not** pytest. Stage 2: Scope `✅` (`CLAUDE.md:196-207`, "Touch only what you must. Clean up only your own mess."), Simplicity `✅` (`:185-187`, "Minimum code that solves the problem. Nothing speculative."), Evaluation-first `✅` (`:212-219`, "Write a test that reproduces it, then make it pass"). All three covered → **recommendation: Skip**, and nothing was written. That is the expected outcome (AC3), not a failure |

Acceptance criteria: AC1/AC2 are proven by the block-template tests plus the skill's
documented Replace/Keep + `--force` paths; AC3 by the manual recon row; AC4/AC5 by the
unit tests and the wiring test with its negative control; AC6 by
`test_rendered_block_stays_inside_the_budget` (rendered block: 782 of 1,200 characters);
AC7 by the payload-identity and VERSION rows.

## Deviations and Decisions

- **Added a wiring test beyond the plan's test list.** The plan specified unit tests for
  the helpers and a *manual, paid* end-to-end run for the SDK path. `test_markers_wiring.py`
  replaces that manual run with a subprocess execution of `update.py` against a stubbed
  `claude_agent_sdk` whose `query` rewrites the block — deterministic, free, and it catches
  the one failure mode the unit tests cannot (a correct guard nobody calls). Proven
  non-vacuous by removing the `finally` and watching it fail.
- **The ADOPT re-install dragged two plugin-only `_shared` tests into the self-host copy**
  (`_shared/tests/test_manifest.py`, `test_version_check.py`). They assert plugin-level
  facts that do not exist in an install and would fail there, so both were deleted rather
  than committed. The installer defect itself is out of scope — recorded in
  `.claude/BACKLOG.md` (see Tracked follow-ups).
- **`markers.py` reports duplicate spans instead of deleting them.** If a marker id ends up
  twice in a file, the guard restores the first and reports the extras rather than removing
  content. Deletion is the one irreversible move available to a background hook; a loud
  message is the safer contract.
- **Restoration warns, never fails the run.** The learner runs from a `SessionStart` hook;
  aborting there over a doc-formatting disagreement would be worse than the restoration.

## Completion Gate

- **Plan tasks complete:** `Yes` — all four tasks (guard, skill, self-host refresh, docs).
- **Acceptance criteria satisfied:** `Yes` — AC1-AC7, evidence in the table above.
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One coherent outcome: baseline coding rules the harness can write, plus the guard that
keeps any tool-owned marker block intact.

- New: `skills/nw-rules-init/SKILL.md`, `engines/claudemd-lerner/payload/scripts/markers.py`,
  `engines/claudemd-lerner/tests/test_markers.py`, `…/tests/test_markers_wiring.py`.
- Changed: `update.py` + `seed.py` (guard wiring, one traversal for the prompt and the
  guard), `payload/AGENTS.md` (Update Rule 8), `engines/claudemd-lerner/VERSION` 2 → 3,
  `tests/test_skill_assets.py` (rules-block invariants).
- Self-host ADOPT refresh: `claudemd-lerner/{AGENTS.md,VERSION,scripts/*}`.
- Docs: root `CLAUDE.md`, `plugins/CLAUDE.md`, plugin `README.md`, `docs/INSTALL.md`.
- Also carried: the plan itself and the backlog entry for the installer defect.

Not included, deliberately: writing the block into this repo's `CLAUDE.md` (the recon
recommends Skip — all three clusters are already covered), and the plugin README's
unrelated staleness.

## Delivery

- **Commits:** one commit, the sole commit on `feature/rules-init-baseline`:
  `feat(harness): baseline coding rules a repo can install, and a guard that keeps them`
  (SHA is the branch head — this report is part of that commit, so it cannot quote it)
- **Pull Request:** `Not opened — deferred to /nw-ship-pr` (this repo's PR lifecycle owns
  push → PR → review fan-out → validation gate → approval gate → merge → branch cleanup;
  opening one directly would bypass that gate and duplicate the review)
- **Base / Head:** `main <- feature/rules-init-baseline`
- **Source PRD:** `None`
- **Tracked follow-ups:** `.claude/BACKLOG.md` — "`claudemd-lerner/install.py` copies
  plugin-only `_shared` tests into the target" (port `compliance-compiler`'s
  `PLUGIN_ONLY_SHARED_TESTS` exclusion to `claudemd-lerner` and `knowledge-compiler`).
