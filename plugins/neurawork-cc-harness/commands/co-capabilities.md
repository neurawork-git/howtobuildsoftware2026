---
description: Derive the compliance capability layer now — cluster constraints into capabilities, map them to 2026 stack components, refresh the stack scaffold
argument-hint: "[--frameworks gdpr,soc2,iso27001] [--all] [--dry-run]"
---

# Derive the compliance capability layer

Turn the extracted **constraints** into per-framework **capabilities** (concrete
technical building blocks, each carrying the constraint ids it satisfies and 2-5
recommended stack components), then refresh the stack scaffold so `catalog/stack.json`
knows about every capability. The capability catalog otherwise ships prebuilt with the
install, and the install scaffolds `stack.json` from it; this command re-derives both
after the constraint catalog changed.

1. Locate the catalog dir: the top-level directory containing `scripts/capabilities.py`
   and `hooks/co-post-tooluse.py` (commonly `compliance-base`). If none exists, tell the
   user to install first via `/neurawork-cc-harness:compliance-compiler`. If
   `catalog/<framework>.json` is missing, the constraints have not been extracted yet —
   run `/neurawork-cc-harness:co-extract` first.
2. Derive the capabilities (requires `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`):

   ```bash
   uv run --directory <catalog-dir> python scripts/capabilities.py $ARGUMENTS
   ```

   No arguments derives all configured frameworks, skipping any whose constraint
   catalog is unchanged since the last run (content hash); `--frameworks gdpr,soc2`
   limits the run; `--all` ignores those hashes and rebuilds everything; `--dry-run`
   prints the cluster/delta/reuse plan without any LLM call. The script **fails**
   (exit 1) when an agent failed or when a mandatory constraint ends up covered by no
   capability — it prints the uncovered ids under `COVERAGE GAP`.
3. Refresh the stack scaffold, so capabilities added by step 2 get an entry to decide on:

   ```bash
   uv run --directory <catalog-dir> python scripts/stack.py --scaffold
   ```

   Existing `chosen` / `rationale` and the `stack-compiler` applicability fields are
   carried over by key; only new capabilities appear with `chosen: null`. The same run
   writes the gap report to `<catalog-dir>/reports/stack-gaps-<date>.md` and prints how
   many applicable mandatory-linked capabilities still have no chosen component. It is
   report-only and exits 0 — a non-zero gap count is a decision the human still owes,
   not a failure.
4. Report the capability count and mandatory coverage per framework, plus the cost the
   script printed. Name any failed agents, any `COVERAGE GAP` ids, and any orphaned
   stack keys the scaffold dropped. Point the user at
   `<catalog-dir>/catalog/capabilities.md` for the catalog and at the gap report for the
   open component decisions.
