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
- [x] **`/nw-ship-pr` should capture open items, not only review findings** — Phase 6.5 persists deferred review findings, but everything else the run surfaces (unverified claims, degraded config, known-broken state named in the Phase 9 report) is only spoken in the report and lost when the session ends. Extend Phase 6.5 so the deferred-findings sink also takes the open items from the Phase 5 explanation and the Phase 9 report, and state in the command that open work is written to the backlog rather than only mentioned. Keep the existing rule that 0 items means no write and no empty commit.  (`plugins/neurawork-cc-harness/commands/nw-ship-pr.md`, ship-pr deferred #32)
- [x] **`validate_commands` is empty, so the pre-merge gate never runs** — `.claude/ship-pr.local.md` declares the key with no items, so Phase 4.5 reports SKIP on every run and the merge gate has no deterministic evidence behind it; PR #32 was merged on manually-run suites. Seed it with this repo's authoritative commands from `CLAUDE.md`: the four per-directory `unittest discover` runs and `uvx ruff check`. **Done 2026-08-21:** the key carries six commands (five per-directory engine suites plus the prompt-asset suite from the plugin root); `uvx ruff check` is deliberately excluded because a repo-root run reports 268 pre-existing findings (the config note said ~145 when it was written on 2026-08-21) and the gate would be a permanent false RED.  (`.claude/ship-pr.local.md`, ship-pr deferred #32)
- [ ] **`claudemd-lerner` has never applied a daily log** — `scripts/state.json` does not exist and `scripts/last-update.json` is stamped 2026-06-25, while five logs sit in `daily/` (newest 2026-08-20). The SessionStart gate keeps spawning `update.py` detached with stdout on `DEVNULL`, so the failure is silent, and the fresh `cl-update.lock` suppresses further spawns for six hours. Run `uv run --directory claudemd-lerner python scripts/update.py` in the foreground to get the real error, then fix the cause.  (`claudemd-lerner/scripts/`, ship-pr deferred #32)
- [ ] **Implement the harness doctor** — the plan is merged and ready; nothing is built yet. It specifies a read-only `/nw-doctor` (`scripts/harness_probe.py` + `scripts/doctor.py`) covering engine discovery, version and `_shared/` drift, install integrity, hook wiring, and queue health. The hooks.json bug fixed in PR #32 means no health signal has ever fired in a user's repo, so this is the first one that would work.  (`.claude/PRPs/plans/harness-doctor.plan.md`, ship-pr deferred #32)
- [ ] **PR #36 was merged with its last commit unreviewed** — the review workflow ran against `652c90c`; the follow-up commit `7b6b811` was pushed afterwards and merged on the validation gate alone (GREEN, 6/6). It changes only the implementation report and one backlog line — no code, no command prose — so the exposure is a wrong sentence in a report, not a behaviour. Read it once; if it holds, close this.  (`.claude/PRPs/reports/ship-pr-open-item-capture-report.md`, ship-pr deferred #36)
- [ ] **A stale `validate_commands` transcription on another checkout runs the same suite twice** — PR #38 narrowed the key to non-test extras and moved the test commands into the `neurawork-cc-harness:rules` block, but `.claude/ship-pr.local.md` is gitignored and per-machine: only this machine's copy was emptied. On any other checkout the old six-command transcription stays in the key, and Phase 4.5 drops only **exact**-string duplicates — a transcription that differs by a space or a path would run the same suite a second time rather than being deduped. Either normalise the merged list before deduping, or have Phase 0.2 report when a `validate_commands` entry looks like a test command the block already carries.  (`plugins/neurawork-cc-harness/commands/nw-ship-pr.md`, ship-pr deferred #38)
