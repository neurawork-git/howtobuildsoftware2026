---
description: Update CLAUDE.md and docs/ now from captured session logs (claudemd-lerner)
argument-hint: "[--all|--dry-run]"
---

# Manual CLAUDE.md / docs update

Apply captured session logs to the repo's CLAUDE.md hierarchy and `docs/` on demand
(does not wait for the SessionStart 6-hour gate).

1. Locate the lerner dir: the top-level directory containing `scripts/update.py` and
   `hooks/cl-session-end.py` (commonly `claudemd-lerner`). If none exists, tell the
   user to install first via `/neurawork-cc-harness:claudemd-lerner`.
2. Run the updater (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <ldir> python scripts/update.py $ARGUMENTS
   ```

   With no arguments it applies new/changed daily logs; `--all` re-applies every
   log; `--dry-run` shows what would update without calling the model.
3. Report which files were edited and the total cost printed by the script. The
   updated docs are the repo-root `CLAUDE.md` (+ any area CLAUDE.md within the
   configured depth) and the `docs/` tree.
