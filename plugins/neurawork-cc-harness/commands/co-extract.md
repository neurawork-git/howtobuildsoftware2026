---
description: (Re)build the repo's compliance catalog now — parallel agents distil GDPR/SOC2/ISO27001 into constraints
argument-hint: "[--frameworks gdpr,soc2,iso27001] [--dry-run]"
---

# Extract the compliance catalog

Build (or rebuild) the per-repo compliance catalog on demand. The catalog is
otherwise built at install time; this command refreshes it. Fans out ~30 parallel agents.

1. Locate the catalog dir: the top-level directory containing `scripts/extract.py`
   and `hooks/co-post-tooluse.py` (commonly `compliance-base`). If none exists, tell
   the user to install first via `/neurawork-cc-harness:compliance-compiler`.
2. Run the extractor (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <catalog-dir> python scripts/extract.py $ARGUMENTS
   ```

   No arguments extracts all configured frameworks; `--frameworks gdpr,soc2` limits
   the run; `--dry-run` prints the shard plan without any LLM call.
3. Report how many constraints were extracted per framework and the total cost.
   Point the user at `<catalog-dir>/catalog/index.md`. Note any failed shards
   (the script exits non-zero if any shard failed).
