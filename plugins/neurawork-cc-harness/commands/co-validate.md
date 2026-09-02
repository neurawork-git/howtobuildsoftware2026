---
description: Validate a PRP plan against the compliance catalog — deep LLM gap report
argument-hint: "<path-to-plan.plan.md>"
---

# Validate a plan against the compliance catalog

Run the deep validator on a specific PRP plan (the same check the PostToolUse hook
spawns automatically on plan writes, on demand here).

1. Locate the catalog dir (contains `scripts/validate.py`, commonly
   `compliance-base`). If missing, tell the user to install via
   `/neurawork-cc-harness:compliance-compiler` and build the catalog with
   `/neurawork-cc-harness:co-extract` first.
2. Run the validator (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <catalog-dir> python scripts/validate.py $ARGUMENTS
   ```

   `$ARGUMENTS` is the plan path, e.g. `.claude/PRPs/plans/my-feature.plan.md` or, in the
   `PRP_HOME` store layout, `.claude/PRPs/<repo>-<hash>/plans/my-feature.plan.md`. With the
   store linked (the default wiring), the flat layout is the one a plan actually lands in.
3. Report the written report path and summarize both tiers: which applicable mandatory
   **constraints** are addressed vs unaddressed, and which **capabilities** the plan's
   own content makes applicable but does not declare (the agent's verdict lands in
   `<catalog-dir>/reports/<plan-stem>.capabilities.json`). The report lives in
   `<catalog-dir>/reports/<plan-stem>.md`. If the capability gate reports the layer is
   not built, point the user at `/neurawork-cc-harness:co-capabilities`.
