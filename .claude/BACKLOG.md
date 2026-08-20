# Backlog

Rolling list of not-yet-scheduled work. Newest first. Mirror significant items
into the relevant PRD under `.claude/PRPs/prds/`.

## claudemd-lerner: enforce three base docs folders + one-liner CLAUDE.md

**Date:** 2026-07-23
**Skill:** `claudemd-lerner`
**Status:** open

The learner should **always** scaffold and maintain three base `docs/` folders:

- `docs/troubleshooting/`
- `docs/patterns/`
- `docs/rules/`

These three are exactly the categories that belong in `CLAUDE.md` (rules,
patterns, troubleshooting). Fine-tune the learner so that:

- On install / update it creates the three folders if missing.
- Every **new** `CLAUDE.md` entry lands as a **one-liner only** in `CLAUDE.md`,
  with the full explanation written to the matching `docs/` folder and **linked**
  from the one-liner.
- Goal: `CLAUDE.md` stays small; detail lives in `docs/`.

Requires tuning the `claudemd-lerner` `AGENTS.md` constitution (routing rule:
category → docs folder + one-line back-link) and the seed/update engine
(folder scaffolding).

- [ ] **`$MAIN_ROOT` is used in `nw-ship-pr.md` but computed nowhere** — the Phase 4.5 fix removed the only line that resolved it (`MAIN_ROOT=$(cd "$(git rev-parse --git-common-dir)/.." && pwd)`), while eight later usages remain (Phase 6.5 config write + gitignore, 8.1 prose, the 8.4 cleanup block) and the 4.5 escape hatch still recommends it. Shell state does not survive between Bash calls, so the variable was already empty there — the consequence is a failed command, not damage. Resolve it once in the ground rules alongside the `is_main_checkout` probe, and state that the path is inserted literally.  (`plugins/neurawork-cc-harness/commands/nw-ship-pr.md`, ship-pr deferred #29)
- [ ] **`claudemd-lerner/install.py` copies plugin-only `_shared` tests into the target** — its `_copy_code` runs `copytree(SHARED_SRC, …, ignore=ignore_patterns("__pycache__"))`, so `_shared/tests/test_manifest.py` and `test_version_check.py` land in every installed copy. Both assert plugin-level facts (the marketplace manifest, `<plugin>/hooks/version-check.py`) that do not exist in an install, so they fail on arrival. `compliance-compiler/install.py` already solves this with a `PLUGIN_ONLY_SHARED_TESTS` exclusion plus a prune of stale copies an older install left behind — port that to `claudemd-lerner` and `knowledge-compiler`. Surfaced by the ADOPT re-install in the rules-init work, where the two files appeared as untracked additions and were deleted by hand.  (`plugins/neurawork-cc-harness/engines/{claudemd-lerner,knowledge-compiler}/install.py`)
