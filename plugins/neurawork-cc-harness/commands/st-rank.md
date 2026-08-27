---
description: Order each applicable capability's catalog components best-fit-first
argument-hint: "[--product PATH] [--all] [--dry-run]"
---

# Rank the components of each applicable capability

Run the second stack-compiler pass: parallel agents order the catalog components of
every still-applicable capability best-fit-first, with a reason per position. Requires
a scoped `stack.json` — run `/neurawork-cc-harness:st-scope` first.

1. Locate the stack dir — the top-level directory holding `scripts/rank.py` and
   `hooks/st-post-tooluse.py`, commonly `stack-base`. If missing, tell the user to
   install via `/neurawork-cc-harness:stack-compiler`.
2. Run the pass (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <stack-dir> python scripts/rank.py $ARGUMENTS
   ```

3. Report the per-capability ordering summary and the report path under
   `<stack-dir>/reports/rank-<date>.md`. On a ranking-gate failure, say that a ranking
   must name exactly that capability's `options`, once each — the component pool is
   closed — and that **nothing was written**; ranking is all-or-nothing.
