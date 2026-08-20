# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-harness-worktree-ship-pr-port/.claude/PRPs/plans/harness-worktree-ship-pr-port.plan.md`
**Branch:** `feature/harness-worktree-ship-pr-port`
**Status:** `COMPLETE`

## Outcome

`neurawork-cc-harness` now ships the delivery lifecycle alongside the knowledge half. Two
prompt-only **workflow surfaces** were added — no install engine, no payload, no hooks:

- `skills/nw-worktree/SKILL.md` — creates a sibling (Hand) worktree from the cached per-repo
  profile in `.claude/worktree.local.md` and activates it via `EnterWorktree {path}`.
- `commands/nw-ship-pr.md` — commit → push → PR → parallel review → validation gate →
  explanation → mandatory approval gate → follow-up capture → CI check → merge → cleanup.
- `workflows/nw-ship-pr-review.js` — the review fan-out, resolving as
  `neurawork-cc-harness:nw-ship-pr-review`.
- `tests/test_skill_assets.py` — turns the three guard invariants into failing assertions.

Four harness-specific adaptations, per the plan:

1. **Phase 8.0 is a report line, not a flush.** The harness redirects capture at the hook layer
   (`_shared/gitctx`), and both compile gates already refuse to run inside a worktree, so the
   ported subprocess call and its failure handling were deleted rather than translated.
2. **Phase 4.5 is config-driven.** `validate_commands` (a YAML list in
   `.claude/ship-pr.local.md`) replaces the pyright block, which would have reported a permanent
   `SKIP` in a stdlib-Python + ruff + unittest repo. Absent/empty → `SKIP`; a missing binary →
   a named skip; a non-zero exit → `RED` carried into the approval gate as a warning.
3. **Phase 6.5 defaults probe this repo's real backlog paths** and seed `validate_commands` from
   the repo's own `CLAUDE.md` when readable, an empty list otherwise.
4. **Re-namespaced** to `nw-`, English throughout, workflow under the harness namespace.

Per-repo state is deliberately shared with a `coding-suite` install (same
`.claude/worktree.local.md`, same `.claude/.ship-pr-state.json`), so this repo needs no RECON
and no `.gitignore` edit — lines 75-78 already cover both paths.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s tests` (from `plugins/neurawork-cc-harness/`) | `passed` | Ran 9 tests, OK |
| `python3 -m unittest discover -s _shared/tests` (from `engines/`) | `passed` | Ran 34 tests, OK |
| `python3 -m unittest discover -s knowledge-compiler/tests` | `passed` | Ran 15 tests, OK |
| `python3 -m unittest discover -s claudemd-lerner/tests` | `passed` | Ran 13 tests, OK |
| `python3 -m unittest discover -s compliance-compiler/tests` | `passed` | Ran 106 tests, OK |
| `uvx ruff check` (from `engines/`) | `passed (no regression)` | 144 pre-existing errors; identical count on the untouched main checkout, so this change adds none |
| `uvx ruff check --line-length 100 tests/` | `passed` | All checks passed (after adding `check=False` to the `node --check` subprocess call) |
| `node --check plugins/neurawork-cc-harness/workflows/nw-ship-pr-review.js` | `passed` | no output, exit 0 |
| Manifests parse (`json.loads` on both) | `passed` | manifests ok |
| Negative check (uncommitted, reverted): appended the forbidden merge flag to `nw-ship-pr.md` | `failed as designed` | `AssertionError: '--delete-branch' unexpectedly found`; file restored, suite green again |
| `grep -c "nw-ship-pr\|nw-worktree"` over the four doc files | `passed` | README 2, CLAUDE.md 3, plugins/CLAUDE.md 6, docs/ARCHITECTURE.md 5 |

The runtime gates in the plan's Validation table (`/nw-worktree port-smoke`, a live `/nw-ship-pr`
run through the approval gate, the first-run config round-trip) are **manual** and not run here —
they exercise the real tools interactively. Prose behaviour cannot be unit tested; the module
docstring of `test_skill_assets.py` says so explicitly so green asset tests are not mistaken for
a working lifecycle.

## Deviations and Decisions

- **The forbidden merge flag is never named literally in `nw-ship-pr.md`.** Plan Task 5 assertion
  5 requires the file to contain no `--delete-branch` *anywhere*, including prose. The prohibition
  is therefore phrased as "`gh pr merge`'s post-merge branch-delete flag" in the ground rules and
  in the 8.1 comment. The test's failure message states this so a future editor understands why
  the flag name is absent instead of re-adding it for clarity.
- **The `git checkout` / `git switch` prohibition in `SKILL.md` was split across two sentences**
  so each line that names a branch-switching command also carries a `never`. Assertion 7 is
  line-scoped; a single-line prohibition spanning a wrap would have failed it.
- **The report lives in `.claude/PRPs/reports/`, not `$PRP_DIR`.** `PRP_HOME` is unset and all
  five prior reports plus every plan are tracked under `.claude/PRPs/`; following the repo
  convention keeps the artifact reviewable, same rationale the plan gives for the plan file.
- **`.claude/PRPs/specs/grillme.spec.md`** was carried into this worktree by the `/worktree`
  stash-carry but is unrelated pre-existing work. It stays untracked and out of the commit.
- **Plan Task 3's "middle option" was dropped as planned** — no legacy un-namespaced global copy
  of this workflow exists, so Phase 4 lists exactly two resolution paths.

## Completion Gate

- **Plan tasks complete:** `Yes` (Tasks 1-6)
- **Acceptance criteria satisfied:** `Yes` for the statically verifiable ones — AC2/AC3 (approval
  gate is the only merge path; no implicit-checkout flag; both 8.3 and 8.4 inline their own
  `is_main_checkout` probe), AC4 (Phase 8.0 makes no subprocess call and cites the three hook
  files; no capture hook was modified), AC5 (SKIP-on-empty, named skip on missing binary, RED as
  a gate warning), AC6 (namespaced name + `${CLAUDE_PLUGIN_ROOT}` fallback both resolve to the
  shipped file, which returns the four-key shape), AC7 (existing profile and both `.gitignore`
  lines reused untouched), AC8 (suite green; the negative check confirms it goes red). AC1 is a
  runtime criterion that only an interactive run can close.
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The port itself: the three new assets, the structural test suite (plus its empty `__init__.py`),
the plugin version bump to `0.2.0` with both manifest descriptions, and the four doc updates
(README command table, `docs/ARCHITECTURE.md` layout + workflow-skill category, `plugins/CLAUDE.md`
layout + gotcha, root `CLAUDE.md` fifth test command + architecture bullet). Plus the plan file
itself, per repo convention. Excluded: `.claude/PRPs/specs/grillme.spec.md` (unrelated).

## Delivery

- **Commits:** `a2b03bd — feat(harness): the plugin now carries a change from worktree to merged PR`
- **Pull Request:** `https://github.com/neurawork-git/howtobuildsoftware2026/pull/29`
- **Base / Head:** `main <- feature/harness-worktree-ship-pr-port`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
