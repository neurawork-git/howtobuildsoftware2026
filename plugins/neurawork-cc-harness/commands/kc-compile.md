---
description: Compile the repo's knowledge base now — distil daily logs into knowledge/ articles
argument-hint: "[--all|--file <daily>]"
---

# Manual knowledge compile

Compile the per-repo knowledge base on demand (does not wait for the SessionStart
6-hour gate).

1. Locate the knowledge dir: the top-level directory containing
   `scripts/compile.py` and `hooks/session-end.py` (commonly `knowledge-base`).
   If none exists, tell the user to install first via
   `/neurawork-cc-harness:knowledge-compiler`.
2. Run the compiler (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <kdir> python scripts/compile.py $ARGUMENTS
   ```

   With no arguments it compiles new/changed daily logs; `--all` recompiles
   everything; `--file <daily>` compiles one log.
3. Report what compiled and the total cost printed by the script. Point the user
   at `<kdir>/knowledge/index.md` for the updated catalog.
