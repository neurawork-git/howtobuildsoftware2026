---
description: Diagnose this repo's harness installs — wiring, versions, integrity and queue health, read-only
argument-hint: "[--json]"
---

# Harness doctor

The harness engines run as detached, fire-and-forget hooks whose output goes nowhere, so
a compile or update that never finishes leaves no trace: daily logs keep piling up while
the gate stays shut behind a lock nobody cleared. This is the command that says so.

Run it whenever the harness "seems quiet" — no new knowledge articles, a `CLAUDE.md` that
stopped moving, a hook you are not sure ever fired.

1. Run the doctor. It is **system `python3`, not `uv run`** — deliberately: a missing `uv`
   or an absent `.venv` is one of the states it exists to report, and a `uv run` entry
   point could not start in that case.

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" $ARGUMENTS
   ```

   It reads only. It never edits `.claude/settings.json`, never removes a lock and never
   spawns a compile. `--repo <path>` inspects another checkout; `--json` emits the same
   findings machine-readably. The exit code is the worst severity: `0` OK/NOTE, `1` WARN,
   `2` ERROR.

2. Report the findings **worst first**, grouped by engine. For each ERROR and WARN give
   the one-line problem and the fix command the doctor already named — do not invent a
   different remedy. The common ones and what they mean:

   - **queue ERROR** — a run was spawned and never completed; the fresh lock now blocks
     the gate. Run the named command in the *foreground* to see the real error, then
     remove the lock file. Do not delete the lock first: the failure would just repeat.
   - **discovery ERROR** — either an install dir that no hook names (it never fires), or
     a hook pointing at a dir that is missing or incomplete (it fails at every session
     start). Both are fixed by re-running the engine's install skill in ADOPT mode.
   - **version / shared WARN** — the in-repo copy is behind, ahead of, or has drifted
     from the plugin. Re-run the install skill; `_shared/` is refreshed on every install.
   - **credentials WARN** — capture still works, compile/update/extract cannot.

3. Offer to run the fixes, one at a time, and let the user choose. Never run a fix
   without asking: every one of them writes into the repo, and several (a foreground
   compile, an installer re-run) cost money or change tracked files.

`stack-compiler` ships no installer — its self-host is mirrored by hand from
`plugins/neurawork-cc-harness/engines/stack-compiler/payload/`, so its fixes are manual.

For compliance gaps beyond "the catalog files exist and parse" — mandatory-unchosen
capabilities, `chosen_from` drift — point the user at
`uv run --directory <compliance-dir> python scripts/stack.py`, which owns that answer.
