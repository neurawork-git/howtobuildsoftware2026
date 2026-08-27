---
description: Validate a PRD or PRP plan against the chosen stack — deep LLM report
argument-hint: "<path-to-prd-or-plan.md>"
---

# Validate a document against the chosen stack

Run the deep stack validator on a specific PRD or PRP plan (the same check the
`st-` PostToolUse hook spawns automatically on document writes, on demand here).

1. Locate the stack dir — the top-level directory holding `scripts/validate.py` and
   `hooks/st-post-tooluse.py`, commonly `stack-base`. If missing, tell the user to
   install via `/neurawork-cc-harness:stack-compiler` and record the choices with
   `/neurawork-cc-harness:st-scope`, `:st-rank` and `:st-select` first.
2. Run the validator (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <stack-dir> python scripts/validate.py $ARGUMENTS
   ```

   `$ARGUMENTS` is the document path, e.g. `.claude/PRPs/prds/my-product.prd.md` or
   `.claude/PRPs/plans/my-feature.plan.md`.
3. Report the written report path `<stack-dir>/reports/<stem>.md`, the verdict in
   `<stack-dir>/reports/<stem>.stack.json`, and which components the document names
   that are off-stack or violate the catalog's `license_policy`. If the verdict says
   nothing is chosen yet, point the user at `/neurawork-cc-harness:st-select`.
