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
   - **plugin currency WARN** — the *installed plugin itself* is older than the
     marketplace clone on this machine, so every fix shipped since then is stranded.
     `/plugin update neurawork-cc-harness`, then `/reload-plugins`. When the doctor also
     notes a `reinstall` finding, do that update **before** re-running any install skill —
     otherwise the skill copies the running plugin's older payload.
   - **queue WARN "stamped but nothing ingested"** — a completion stamp with no
     `state.json`. A completed run writes its ingest state before it stamps, so the engine
     either died before doing any work (a detached hook discards the traceback) or the
     stamp came from a seed run. Run the named command in the foreground and read the
     error; for `claudemd-lerner` the hook's own output is in `scripts/update.log`.
   - **credentials WARN** — no API key and no subscription login: capture still works,
     compile/update/extract cannot. A **NOTE** instead means a subscription login exists
     and the engines will fall back to it — they run, but an API key is what third-party
     plugin use is sanctioned for.

3. Offer to run the fixes, one at a time, and let the user choose. Never run a fix
   without asking: every one of them writes into the repo, and several (a foreground
   compile, an installer re-run) cost money or change tracked files.

For compliance gaps beyond "the catalog files exist and parse" — mandatory-unchosen
capabilities, `chosen_from` drift — point the user at
`uv run --directory <compliance-dir> python scripts/stack.py`, which owns that answer.
