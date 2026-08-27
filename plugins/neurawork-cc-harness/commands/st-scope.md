---
description: Decide which compliance capabilities apply to this product, and why
argument-hint: "[--product PATH] [--all] [--dry-run]"
---

# Scope the compliance capabilities to this product

Run the first stack-compiler pass: parallel agents read the tracked `product.md` and
record, per capability, whether it applies to this product and the reason.

1. Locate the stack dir — the top-level directory holding `scripts/scope.py` and
   `hooks/st-post-tooluse.py`, commonly `stack-base`. If missing, tell the user to
   install via `/neurawork-cc-harness:stack-compiler`.
2. Run the pass (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <stack-dir> python scripts/scope.py $ARGUMENTS
   ```

3. Report how many capabilities stayed applicable per framework, the reasons recorded
   for those scoped out, and the report path under `<stack-dir>/reports/scope-<date>.md`.
   On a non-zero exit, say which gate stopped it — the challenge agent refuting a "not
   applicable" claim, or the mandatory-safety gate — because either way **nothing was
   written**; scoping is all-or-nothing. If it exited 1 because `product.md` did not
   exist, say the template was just written to `<stack-dir>/product.md` and must be
   filled in before re-running.
