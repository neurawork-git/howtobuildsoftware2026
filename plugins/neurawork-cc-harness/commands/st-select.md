---
description: Render the stack selection sheet, or record the components chosen on it
argument-hint: "[--apply <selection-sheet.md>] [--dry-run]"
---

# Choose the component per capability

Run the third stack-compiler pass. It runs **no agent** — the ranked proposal already
exists — and needs **no API key**. Two modes:

- no arguments → renders an editable selection sheet from the current ranking;
- `--apply <sheet>` → reads back the component a human wrote per capability and records
  it, stamping `chosen_from` so a later catalog change reopens exactly the affected
  choices.

1. Locate the stack dir — the top-level directory holding `scripts/selection.py` and
   `hooks/st-post-tooluse.py`, commonly `stack-base`. If missing, tell the user to
   install via `/neurawork-cc-harness:stack-compiler`.
2. Run the pass:

   ```bash
   uv run --directory <stack-dir> python scripts/selection.py $ARGUMENTS
   ```

3. In render mode, report the sheet path under
   `<stack-dir>/reports/selection-sheet-<date>.md` and tell the user to fill in one
   component per capability, then re-run with `--apply <that path>`. In apply mode,
   report how many capabilities were recorded this sitting and how many remain
   undecided — an undecided capability is a counted gap, not an omission. A choice must
   come from that capability's ranked `options`; a failed gate writes nothing.
