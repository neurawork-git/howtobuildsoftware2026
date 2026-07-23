# Implementation Report

**Plan**: `.claude/PRPs/plans/plugin-upgrade-nudge-and-version.plan.md`
**Branch**: `feature/plugin-upgrade-nudge-and-version`
**Date**: 2026-07-23
**Status**: COMPLETE

---

## Summary

Closed the plugin-upgrade UX gap. Added a semver `version` to the plugin manifest
(Feature A) and a plugin-level `SessionStart` hook that warns when an in-repo engine
copy is behind the plugin's shipped `VERSION`, telling the user to re-run the installer
(ADOPT) to propagate the upgrade (Feature B). Feature B lives at the plugin level
because installed hooks resolve paths from their own on-disk location and never see
`CLAUDE_PLUGIN_ROOT`, so they cannot read the shipped `VERSION`.

---

## Assessment vs Reality

| Metric     | Predicted | Actual | Reasoning |
| ---------- | --------- | ------ | --------- |
| Complexity | LOW       | LOW    | Isolated new plugin surface + 2 tests + 3 doc edits; no engine/payload/install.py touched, as planned |
| Confidence | 9/10      | 9/10   | Matched the plan exactly; the one uncertainty (auto-load + additionalContext surfacing) was covered by the Level-6 manual reproduction |

No deviations from the plan.

---

## Tasks Completed

| # | Task | File | Status |
| - | ---- | ---- | ------ |
| 1 | Add semver `version` | `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` | ✅ |
| 2 | Staleness-check script | `plugins/neurawork-cc-harness/hooks/version-check.py` | ✅ |
| 3 | Register plugin SessionStart hook | `plugins/neurawork-cc-harness/hooks/hooks.json` | ✅ |
| 4 | Unit tests for the check | `engines/_shared/tests/test_version_check.py` | ✅ |
| 5 | Manifest guard test | `engines/_shared/tests/test_manifest.py` | ✅ |
| 6 | Document the nudge | `docs/INSTALL.md` | ✅ |
| 7 | Document plugin hook + version | `docs/ARCHITECTURE.md` | ✅ |

---

## Validation Results

| Check | Result | Details |
| ----- | ------ | ------- |
| JSON valid | ✅ | plugin.json + hooks.json parse |
| Lint (ruff) | ✅ | `version-check.py` clean; new test files clean under canonical `engines/` lint |
| Unit tests | ✅ | 91 passed (34 `_shared` incl. 22 new, 15 kc, 13 cl, 29 co), 0 failed |
| Build | ⏭️ | N/A (interpreted Python) |
| Manual (Level 6) | ✅ | silent when current; correct nudge when installed 1 < shipped 2; plugin VERSION restored |

---

## Files Changed

| File | Action | Lines |
| ---- | ------ | ----- |
| `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` | UPDATE | +1 |
| `plugins/neurawork-cc-harness/hooks/version-check.py` | CREATE | +~155 |
| `plugins/neurawork-cc-harness/hooks/hooks.json` | CREATE | +14 |
| `plugins/neurawork-cc-harness/engines/_shared/tests/test_version_check.py` | CREATE | +~135 |
| `plugins/neurawork-cc-harness/engines/_shared/tests/test_manifest.py` | CREATE | +22 |
| `docs/INSTALL.md` | UPDATE | +10 |
| `docs/ARCHITECTURE.md` | UPDATE | +15/-1 |

---

## Deviations from Plan

None.

---

## Issues Encountered

- `version-check.py` initially tripped ruff `ISC004` (implicit string concat) and
  `BLE001` (blind `except`). Fixed: explicit `+` concat; kept the broad catch with an
  inline `# noqa: BLE001` justified by "a hook crash must never break session start"
  (mirrors the existing `session-start.py` pattern). The repo-wide `uvx ruff check` from
  `engines/` shows ~140 pre-existing findings unrelated to this change — left untouched
  (surgical scope); the new files add none.

---

## Tests Written

| Test File | Test Cases |
| --------- | ---------- |
| `test_version_check.py` | `installed_dir_for` (default/renamed/missing/no-hooks), `is_behind` (int behind/current/ahead, non-int differ/equal), `find_stale` (stale/current/missing-version/no-install), `main` (no-env no-op, stale prints additionalContext) |
| `test_manifest.py` | manifest is valid JSON with `name` + semver `version` |

---

## Next Steps

- [ ] Review implementation
- [ ] Create PR (`/ship-pr` — flushes learn-capture, then merges + removes the worktree)
- [ ] Merge when approved
