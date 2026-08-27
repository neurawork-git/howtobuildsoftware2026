# Make the doctor answer "is the harness current, and is anything silently dead?"

**Plan ID:** `doctor-plugin-currency-and-silent-engine-failure`
**Source PRD:** None
**PRD Phase:** None
**Source Issue:** None
**Plan Publication:** None

## Outcome

**Problem:** `/nw-doctor` reports 33 OK / 2 NOTE / 1 WARN on a repo where the learner engine has
never executed a single time and the installed plugin is a version behind the marketplace. Three
separate defects produce that false all-clear:

1. `claudemd-lerner`'s `update.py` dies at import (`ModuleNotFoundError: No module named '_shared'`)
   on every invocation, and its hook discards the traceback — so the learner has produced zero
   `CLAUDE.md` updates while looking healthy.
2. The doctor's queue check renders that state as a benign `NOTE` ("the gate reopens at 18:30"),
   because the one combination that proves an engine never ran — a completion stamp with no
   ingest state — carries no distinct severity.
3. The doctor never compares the installed plugin against the marketplace at all. Live right now:
   cache `0.5.0`, marketplace clone `0.5.1`, doctor silent.

**Affected user:** The harness operator running `/nw-doctor` in any repo — the report is the only
surface that ever tells them a detached, output-discarding hook stopped working.

**User outcome:** A doctor run answers, without a second tool and without network: is the installed
plugin the newest version, does it match the marketplace, does anything need re-installing — and
does any engine carry evidence that it never actually ran.

**Invariant:** The doctor stays read-only and side-effect-free. It never spawns a process, creates a
directory, writes, or deletes; it never touches the network; it runs under system `python3` with
stdlib only; and it always produces a report rather than raising, no matter what is missing.
(`plugins/neurawork-cc-harness/scripts/doctor.py:2-26`, pinned by
`plugins/neurawork-cc-harness/tests/test_doctor.py:559-586`.)

**Success signal:** Run the doctor in this repo after the change: it reports the plugin as a version
behind with the `/plugin update` fix, and — before the `update.py` fix is applied — flags
`claudemd-lerner` at WARN for "stamped but nothing ingested". After the `update.py` fix and one real
update run, both findings clear and `claudemd-lerner/scripts/state.json` exists.

**Approach:** Three independent changes to the same diagnostic surface, plus the one-line engine fix
whose failure motivated all of it:

- **A.** Fix `update.py`'s missing `sys.path` bootstrap (both byte-identical copies), stamp only when
  a log actually ingested, and stop the hook from discarding the child's output.
- **B.** Escalate the doctor's queue check when a stamp exists with no ingest state.
- **C.** Add a plugin-currency section: installed cache version vs. marketplace-clone version vs. the
  running plugin root, plus leftover cache versions and a re-install-would-be-futile cross-check.

## Recommendation

Every piece reuses a primitive that already exists.

**A** is a one-line insertion copied verbatim from a sibling file. `flush.py:28` and `seed.py:22` in
the same directory already carry
`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # <ldir> for _shared`;
`update.py` is the only script in any engine payload that imports `_shared` without it (audited: all
14 payload scripts referencing `_shared`, only `update.py` lacks the bootstrap). No new abstraction,
no shared bootstrap module — a single-use import fix stays a single-use import fix.

**B** needs no new state and no new file read. `check_queue` already loads both `state.json` and the
completion stamp (`doctor.py:429`, `:461-465`); the change is a severity branch over values it holds.
The rule is exact: a completed `update.py`/`compile.py` run writes ingest state *before* it stamps
(`update.py:179` inside `update_one`, `_stamp_last_update()` at `:227` after the loop), so a stamp
with no state means either the engine crashed before doing work, or the stamp came from `seed.py`,
which stamps `LAST_UPDATE_FILE` and has no ingest concept at all (`seed.py:151-155`). Both readings
are worth surfacing; the finding names both.

**C** reads four on-disk JSON/text artifacts already present on any machine that installed the
plugin, all offline and stdlib-parseable — verified live:

| Artifact | Supplies |
|---|---|
| `~/.claude/plugins/installed_plugins.json` | installed version, `installPath`, `gitCommitSha`, `lastUpdated`, keyed `neurawork-cc-harness@<marketplace>` |
| `~/.claude/plugins/known_marketplaces.json` | the marketplace's `installLocation` (a local clone) |
| `<installLocation>/.claude-plugin/marketplace.json` → its plugin entry's `source.path` | where the plugin source sits inside that clone |
| `<installLocation>/<source.path>/.claude-plugin/plugin.json` | the newest available version |
| sibling dirs of `installPath` | leftover cache versions |

No `git` call is needed — and none is permitted, since `test_doctor.py:577-586` greps the doctor's
own source text for `subprocess`, `Popen`, `mkdir`, `write_text`, `os.remove` and `unlink`. Version
comparison reuses `probe.compare()` (`harness_probe.py:180-193`), which already returns
`same`/`behind`/`ahead`/`unknown` and is already the doctor's engine-version primitive
(`doctor.py:269-295`).

Registry knowledge goes in `harness_probe.py` (it already owns `ENGINES` and every discovery
primitive for both consumers, per its docstring `:8-11`); rendering and severity stay in `doctor.py`.
That is the existing split, not a new one.

The one genuinely new thing is that the doctor reads outside the repo and plugin root for the first
time. That is bounded to `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/`, is read-only like everything
else, and every absence degrades to a single NOTE rather than an error — a CI checkout or a machine
that installed the plugin some other way must still get a full report.

### Evidence

- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/update.py:16-23` — imports
  `_shared.repo_guard` with no `sys.path` bootstrap and no `import sys`. Reproduced live:
  `uv run --directory claudemd-lerner python scripts/update.py --dry-run` →
  `ModuleNotFoundError: No module named '_shared'` at line 23, before `argparse`, before `main()`.
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/flush.py:28` and
  `seed.py:22` — the exact bootstrap line to copy.
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/hooks/cl-session-start.py:64-68` —
  `subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, ...)`: why the crash
  has been invisible. The lock is written immediately after (`:69-70`) regardless of the child's fate.
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/update.py:222-228` —
  `_stamp_last_update()` runs after the loop unconditionally; `update_one` returns `0.0` from its
  `except` before reaching `save_state` (`:164-166`, `:172-179`). Latent even after the import fix.
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/seed.py:151-155` — the other
  writer of `LAST_UPDATE_FILE`, with no `STATE_FILE` concept. This is what stamped 12:30 today.
- `plugins/neurawork-cc-harness/scripts/doctor.py:211-219` — the credentials check reads two env
  vars and asserts "compile / update / extract cannot run".
- `claudemd-lerner/scripts/flush.log` — `Using bundled Claude Code CLI: …/claude_agent_sdk/_bundled/claude`,
  `Flush cost: $0.0937`, `Result: FLUSH_OK`, with neither env var set. The assertion is false.
- `claudemd-lerner/.venv/…/claude_agent_sdk/_internal/transport/subprocess_cli.py:81-125` — the SDK
  resolves a bundled CLI first, then `PATH`; no engine script reads either env var (greps across all
  `payload/scripts/*.py` and `engines/_shared/*.py` return hits only in `install.py` print strings).
- `claudemd-lerner/.venv/…/claude_agent_sdk/_internal/session_resume.py:320-359` — names
  `${CLAUDE_CONFIG_DIR:-~/.claude}/.credentials.json` as the subscription artifact. Present on this
  machine (925 bytes, mode 0600).
- `knowledge-base/knowledge/connections/sdk-subprocess-forces-api-key.md` and root `CLAUDE.md`
  ("Subscription credentials are not sanctioned for third-party plugin use; public installs must set
  an API key") — the standing decision. The finding must keep pointing at an API key; only the
  false "cannot run" claim goes.
- `plugins/neurawork-cc-harness/scripts/harness_probe.py:180-193` (`compare`), `:307-337`
  (`find_stale`) — the version primitives to reuse.
- `plugins/neurawork-cc-harness/tests/test_doctor.py:559-586` — the read-only guarantee: byte-identical
  repo after a run, plus a source-text grep banning `subprocess`/`Popen`/`mkdir`/`write_text`/`os.remove`/`unlink`.
- Live currency gap: `installed_plugins.json` → `0.5.0` at
  `~/.claude/plugins/cache/neurawork-harness/neurawork-cc-harness/0.5.0`;
  `~/.claude/plugins/marketplaces/neurawork-harness/plugins/neurawork-cc-harness/.claude-plugin/plugin.json`
  → `0.5.1`. Leftovers in the cache dir: `0.1.0 0.2.0 0.3.0 0.3.1`.
- `~/.claude/plugins/plugin-catalog-cache.json` — contains only the official Anthropic catalog, no
  `neurawork-cc-harness` entry. Not a usable source.
- `knowledge-base/knowledge/concepts/plugin-version-bump-propagates-cache.md` — the prior finding
  that a source fix is invisible in an installed cache until a version bump plus `/plugin update` +
  `/reload-plugins`. This check is the missing detector for exactly that state.

### Alternatives considered

- **Have the doctor shell out to `git -C <marketplace clone> log/describe` for the newest version:**
  loses against the invariant. `test_doctor.py:577-586` bans `subprocess` from the source text
  outright, and the clone's `plugin.json` already carries the version verbatim.
- **Query the marketplace over the network for the newest version:** loses against the invariant
  (offline, read-only) and adds a failure mode to a tool whose job is to work when things are broken.
  The clone is refreshed by `/plugin` itself and is the same data.
- **Stamp the installing plugin version into each engine's install dir, so the doctor can say "this
  install came from 0.3.1":** the strongest form of "does an engine originate from an older plugin
  version", but it needs an `install.py` + payload change across four engines and only helps installs
  made *after* the change. The composition of the existing per-engine `VERSION` check with the new
  plugin-currency check already answers the operational question ("is re-installing worth it right
  now"), so this stays out. Task 5 delivers that composition instead.
- **Drop the credentials finding entirely because the bundled CLI works:** contradicts the recorded
  decision in `connections/sdk-subprocess-forces-api-key.md` and root `CLAUDE.md`. The finding is
  kept and made accurate.
- **Give `update.py` a shared bootstrap helper imported by every payload script:** a new abstraction
  for a problem that occurs once. Three sibling files already solve it with one line.

## Root Cause

- **Observed failure:** `claudemd-lerner/scripts/state.json` absent while
  `claudemd-lerner/scripts/last-update.json` is stamped (`{"ts": 1787826603.421651}` = 2026-08-27
  12:30) and 6 daily logs sit in `claudemd-lerner/daily/`. Reproduced directly:
  `uv run --directory claudemd-lerner python scripts/update.py --dry-run` →
  `ModuleNotFoundError: No module named '_shared'` (`update.py`, line 23). The same crash occurs for
  the exact command the hook builds (`… python scripts/update.py --all`).
- **Causal chain:** `update.py:23` imports `_shared.repo_guard`; running `python scripts/update.py`
  puts only `scripts/` on `sys.path`, and `_shared` lives one level up → `ModuleNotFoundError` at
  module-import time, before `argparse`, before `main()`, before the SDK is imported. `save_state()`
  (`utils.py:30`) is reachable only from `update_one()` inside `main()`'s loop, so `state.json` is
  never created. `cl-session-start.py:64-68` spawns the child with both streams to `DEVNULL`, so
  nothing surfaces. `last-update.json` exists because `seed.py` — which *does* carry the bootstrap
  at `:22` — ran once and stamps the same file (`seed.py:151-155`) without any ingest state.
- **Fix boundary:** `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/update.py:16-23`
  and its byte-identical self-host copy `claudemd-lerner/scripts/update.py:16-23` — add `import sys`
  and the `sys.path.insert` line before the `_shared` import. Nothing else in `update.py`'s control
  flow, marker-guard wiring, or `--all`/`--dry-run` contract changes.
- **Regression proof:** the existing suite masks this. `test_markers_wiring.py:104` injects
  `env["PYTHONPATH"] = os.pathsep.join([str(stub_dir), str(lerner)])`, supplying exactly what the
  missing line should supply — 30/30 green today despite the defect. The new test must invoke
  `update.py` the way production does: `subprocess.run([sys.executable, "scripts/update.py", "--dry-run"],
  cwd=<lerner dir>)` with no lerner path on `PYTHONPATH`, asserting `returncode == 0` and no
  `ModuleNotFoundError` in stderr. It fails today and passes after the one-line fix.
- **Remaining uncertainty:** which actor ran `seed.py` at 12:30 was not traced. It does not change
  the fix boundary — `seed.py` is the only script that can write `last-update.json` without touching
  `state.json`, which is sufficient to explain the observed file pair.

## Implementation Context

### Mandatory reading

| File | Why it matters |
|---|---|
| `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/update.py:16-23,160-180,205-230` | The import crash, the `except → return 0.0` that skips `save_state`, and the unconditional stamp |
| `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/flush.py:24-31` | The exact bootstrap line and comment to copy, plus the logging precedent |
| `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/hooks/cl-session-start.py:53-73` | Where the child's output is discarded and the lock is written |
| `plugins/neurawork-cc-harness/scripts/doctor.py:41-67,179-228,393-516,562-643` | Severity table, `Finding`, `check_environment`, `check_queue`, orchestration and rendering |
| `plugins/neurawork-cc-harness/scripts/harness_probe.py:30-63,66-129,180-193` | `Queue`/`Engine`/`ENGINES` and the `compare()` version primitive |
| `plugins/neurawork-cc-harness/tests/test_doctor.py:32-75,559-586` | How fixtures are built from the real payload, and the read-only guard the new code must not trip |
| `plugins/neurawork-cc-harness/tests/test_harness_probe.py:8-9,25-53` | Temp-dir fixture style; the docstring forbids using the live self-host as a fixture |
| `plugins/neurawork-cc-harness/commands/nw-doctor.md` | Pinned by `test_skill_assets.py:123-163`: must keep invoking `"${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"`, use `python3` in every fenced block, and keep the "never removes a lock" prose |

### Existing patterns and primitives

- **Severity + exit code:** `doctor.py:45-47` — `SEVERITIES`/`RANK`/`EXIT = {"OK": 0, "NOTE": 0,
  "WARN": 1, "ERROR": 2}`. A new NOTE keeps exit 0; a new WARN makes the run exit 1.
- **Repo-level findings:** `doctor.py:50` — `REPO = "-"` groups a finding under the `repo` section.
  The plugin-currency findings need their own group; use a module constant alongside it rather than
  overloading `REPO`, so `render_text` (`:593-606`) prints a distinct section.
- **Version comparison:** `harness_probe.compare(installed, shipped)` `:180-193` → `same`/`behind`/
  `ahead`/`unknown`, already int-tuple aware with a string fallback.
- **Tolerant JSON read:** `doctor.py:86-87` (`read_json`) returns `(None, error)` rather than
  raising — the pattern every new file read must follow.
- **Never-raise checks:** every `check_*` returns `list[Finding]` and swallows its own failures
  (`doctor.py:481-494` proves an unparsable `settings.json` still yields a report).

### Integration points

- `doctor.py:562-588` (`run_checks`) — add the plugin-currency check to the ordered list, before the
  per-engine loop, so currency reads first in the report (it is the question the user asks first).
- `doctor.py:593-606` (`render_text`) — a new group label must render like the existing ones.
- `doctor.py:618-638` (`main`) — `--json` and `--repo` must carry the new findings unchanged.
- `harness_probe.py` — new plugin-currency probe functions live here beside `ENGINES`.

## Scope

### In scope

- `update.py` import fix in both copies, plus a regression test that runs it the production way.
- Stamp `last-update.json` only when at least one log ingested.
- Stop `cl-session-start.py` from discarding the update child's output.
- Queue check: distinct WARN for "stamp present, ingest state absent".
- Credentials check: three-state, accurate wording, subscription-login detection.
- New plugin-currency check: installed vs. marketplace vs. running plugin root, leftover cache
  versions, and the "re-installing now would still install the old engine" cross-check.
- `commands/nw-doctor.md` updated to describe the new findings and their fixes.

### Not building

- Stamping the installing plugin version into engine install dirs (see Alternatives).
- Extending `hooks/version-check.py` to nudge on plugin staleness — the doctor is the surface asked
  for; the hook's SessionStart budget is deliberately small.
- Any change to `knowledge-compiler`, `compliance-compiler` or `stack-compiler` payloads. Their
  scripts were audited and all carry the bootstrap.
- Deleting leftover cache versions. The doctor reports; it never removes.
- Running the real `update.py` against this repo's 6 pending logs. That costs money and rewrites
  tracked docs — the operator's call, after the fix ships.

## Compliance

**Capabilities**: none — this change fixes one import line in a local developer-tooling script,
redirects a child process's output to a gitignored log beside it, and extends a read-only local
diagnostic that parses files already on the operator's own disk. It processes no personal data,
exposes no interface, adds no network path, no data store, and no authentication or authorisation
surface, and it changes no runtime data flow — so no capability in `compliance-base/catalog/capabilities.json`
is delivered by it.

One handling rule is load-bearing and is pinned as acceptance rather than left to care: Task 6 checks
only the **existence** of `${CLAUDE_CONFIG_DIR:-~/.claude}/.credentials.json` and must never read,
parse, log, or render its contents. AC6 states this and its test asserts no substring of the fixture
credentials file appears in the doctor's output — including under `--json`.

## Delivery Considerations

| Concern | Decision and owned work |
|---|---|
| Discoverability / adoption | The `update.py` fix reaches installed caches only after a plugin version bump plus `/plugin update` + `/reload-plugins` (`knowledge/concepts/plugin-version-bump-propagates-cache.md`). Task 7 owns the bump and CHANGELOG entry. |
| Compatibility / migration | The self-host `claudemd-lerner/` copy must be patched alongside the payload, or this repo's own learner stays dead. Task 1 owns both copies. `state.json` is created on the first successful run; no migration. |
| Rollout / reversibility | All changes are additive to a read-only diagnostic plus one import line. Reverting is a `git revert`; no data shape changes. |
| Observability | Task 3 is itself the observability fix: the update child's output stops going to `/dev/null`, so the next such crash leaves a trace. Task 4 makes the doctor name the resulting state. |
| Documentation / communication | `commands/nw-doctor.md` (Task 6) and the CHANGELOG (Task 7). Root `CLAUDE.md` needs no change — the doctor's described role is unchanged, only its coverage. |

## Implementation

### 1. `update.py` runs instead of dying at import

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/update.py:16-23` — UPDATE.
- `claudemd-lerner/scripts/update.py:16-23` — UPDATE. The self-host copy; must stay byte-identical.

**Implementation**
- Add `import sys` to the stdlib import block and, after the `from pathlib import Path` line, insert
  the bootstrap exactly as `flush.py:28` writes it:
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # <ldir> for _shared`,
  before the `from _shared.repo_guard import …` line.
- Change nothing else. `--all` / `--dry-run` behavior, the marker guard, and the SDK call stay as they are.

**Tests**
- New regression test in `plugins/neurawork-cc-harness/engines/claudemd-lerner/tests/`: build a temp
  lerner install from the real payload (fixture style of `tests/test_doctor.py:51-75`), then
  `subprocess.run([sys.executable, "scripts/update.py", "--dry-run"], cwd=<install>, …)` with an env
  whose `PYTHONPATH` does **not** contain the install dir. Assert `returncode == 0` and
  `"ModuleNotFoundError"` not in stderr. Must fail against the unfixed file.
- Assert the two copies are byte-identical (there is no drift test covering `claudemd-lerner`; only
  `stack-compiler` has one, at `engines/stack-compiler/tests/test_payload_drift.py`).

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s claudemd-lerner/tests`
  — new test passes, existing 30 still pass.
- `uv run --directory claudemd-lerner python scripts/update.py --dry-run` — lists 6 pending logs
  instead of a traceback. No LLM call, no cost.

### 2. A failed run no longer advances the gate

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/scripts/update.py:222-228` — UPDATE,
  and the self-host copy.

**Implementation**
- Track whether any log actually ingested (the same signal `save_state` writes) and call
  `_stamp_last_update()` only when at least one did. A run where every log errored must leave the
  stamp untouched, so the 6-hour gate reopens and the work is retried rather than silently deferred.
- Keep printing the per-log error; do not convert a partial failure into a non-zero exit — the hook
  spawns this detached and a raised exception would change nothing for the caller.
- Leave `update_one`'s `except → return 0.0` shape alone; per-log isolation is intentional.

**Tests**
- With a stubbed SDK that raises for every log: `last-update.json` is not created/updated and
  `state.json` records no ingest. With a stub that succeeds for one of two logs: the stamp advances
  and `state["ingested"]` holds exactly the successful log.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s claudemd-lerner/tests`

### 3. The update child's failure leaves a trace

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/hooks/cl-session-start.py:63-71` —
  UPDATE, and the self-host copy `claudemd-lerner/hooks/cl-session-start.py`.

**Implementation**
- Replace `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` with an append-mode handle on
  `SCRIPTS_DIR / "update.log"`, mirroring how `flush.py` already keeps `flush.log` next to itself.
- Keep the spawn non-blocking, keep `start_new_session=True`, keep the `except OSError: pass`, and
  keep writing the lock afterwards. If the log file cannot be opened, fall back to `DEVNULL` — the
  gate must never fail because logging failed.
- Confirm `update.log` is covered by the install's `.gitignore` (it sits beside the already-ignored
  `flush.log` and `state.json`); add it if not.

**Tests**
- Assert the hook's spawn does not pass `DEVNULL` for `stderr`, and that a spawn failure still leaves
  the hook returning normally.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s claudemd-lerner/tests`

### 4. The doctor names an engine that never ran

**Files and integration points**
- `plugins/neurawork-cc-harness/scripts/doctor.py:426-436,459-466` — UPDATE inside `check_queue`.

**Implementation**
- After reading `state` and `last_ts`, add one branch: `state` is not a dict (file absent or corrupt)
  **and** `last_ts` is not None **and** there are pending logs → `WARN`, ahead of the existing
  stamp/lock branches, since it invalidates their reasoning.
- Message must state both readings without asserting either: a completed run writes ingest state
  before it stamps, so a stamp with no `state.json` means the run either never got as far as
  ingesting anything or the stamp came from `seed.py`. Fix line: run the engine's foreground command
  (the existing `queue.command`, already worktree-adjusted at `:446-449`) and read the error.
- Do not change the pending-count arithmetic, the in-flight grace, the worktree redirection, or the
  existing OK/NOTE/WARN/ERROR branches.

**Tests**
- Fixture with `last-update.json` present, no `state.json`, and pending logs → exactly one `WARN`
  naming the state file; exit code 1.
- Fixture with neither file and pending logs → the existing NOTE/WARN behavior is unchanged (a fresh
  install must not become a WARN).
- Fixture with `state.json` present and a stamp → unchanged.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`
- `python3 plugins/neurawork-cc-harness/scripts/doctor.py` in this repo — `claudemd-lerner` reports
  the new WARN (until a real update run is performed).

### 5. The doctor answers whether the plugin is current

**Files and integration points**
- `plugins/neurawork-cc-harness/scripts/harness_probe.py` — CREATE the probe functions beside
  `ENGINES`; it already owns discovery for both consumers.
- `plugins/neurawork-cc-harness/scripts/doctor.py:562-588` — UPDATE `run_checks` to call the new
  check first; `:50` — add the section constant; `:593-606` — ensure the new group renders.

**Implementation**
- In `harness_probe.py`, add a resolver for the plugin-install root
  (`${CLAUDE_CONFIG_DIR:-~/.claude}/plugins`) and a function returning a plain dataclass with:
  installed version + `installPath` + `gitCommitSha` (from `installed_plugins.json`, matching the
  entry whose key starts `neurawork-cc-harness@`, `scope == "user"` preferred when several exist);
  the marketplace `installLocation` (from `known_marketplaces.json`, via the marketplace name in that
  key); the available version (from `<installLocation>/.claude-plugin/marketplace.json` → the
  `neurawork-cc-harness` entry's `source.path` → `<installLocation>/<source.path>/.claude-plugin/plugin.json`);
  the running plugin root's own version (`<plugin_root>/.claude-plugin/plugin.json`); and the sibling
  directory names under `installPath`'s parent.
- Read files only, tolerantly: any missing or unparsable artifact yields `None` for that field, never
  an exception. No `subprocess`, no `mkdir`, no writes — the banned-token grep in
  `test_doctor.py:577-586` applies to `doctor.py`; keep `harness_probe.py` equally clean so the same
  guard can be extended to it.
- In `doctor.py`, add `check_plugin(plugin_root)` emitting, under a `plugin` section:
  - **currency** — `compare(installed, available)`: `same` → OK naming the version; `behind` → WARN
    "installed X, marketplace has Y", fix `/plugin update neurawork-cc-harness` then
    `/reload-plugins`; `ahead` → NOTE (a local source checkout ahead of the clone is normal in this
    repo); `unknown`/unreadable → NOTE naming which artifact was missing.
  - **running root** — the plugin root this doctor was loaded from vs. `installPath`. Different path
    or version → NOTE, so "I updated but the session still runs the old cache" is visible.
  - **stale caches** — sibling version dirs other than the installed one → NOTE listing them, with
    no removal command and no implied one.
  - **re-install worth it** — when currency is `behind` **and** any engine's `VERSION` in the running
    plugin differs from the same file under the marketplace clone, add a NOTE that re-running an
    install skill now would still install the older engine, so update the plugin first. This is the
    composition that turns the existing per-engine version check into an actionable order of
    operations; skip the finding when the plugin is current.
- When the plugins dir does not exist at all (CI, a checkout without an install), emit exactly one
  NOTE saying plugin currency was not inspectable and why, and no other plugin findings.

**Tests**
- Temp-dir fixtures (never the live `~/.claude`, per `test_harness_probe.py:8-9`) building a fake
  plugins root: behind → WARN with both versions; same → OK; ahead → NOTE; absent plugins dir → one
  NOTE and no crash; unparsable `installed_plugins.json` → NOTE, report still rendered; leftover
  sibling dirs → NOTE listing exactly the non-installed ones; renamed/multi-scope entries resolved
  to the user-scope install.
- Extend the read-only assertions to cover the new code path: repo byte-identical after a run, and
  the banned-token grep still clean.
- `--json` output includes the new findings with the same `Finding` field names.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`
- `python3 plugins/neurawork-cc-harness/scripts/doctor.py` in this repo — reports installed `0.5.0`
  vs. marketplace `0.5.1` as WARN, and lists `0.1.0 0.2.0 0.3.0 0.3.1` as leftovers.
- `python3 plugins/neurawork-cc-harness/scripts/doctor.py --json` — parses, carries the new findings.

### 6. The credentials finding stops asserting something false

**Files and integration points**
- `plugins/neurawork-cc-harness/scripts/doctor.py:211-219` — UPDATE inside `check_environment`.

**Implementation**
- Three states:
  - either env var set → OK, unchanged message.
  - neither set, but `${CLAUDE_CONFIG_DIR:-~/.claude}/.credentials.json` exists → **NOTE**: no API key
    in the environment; the engines will fall back to the bundled Claude Code CLI's subscription
    login. Keep the API-key fix line, because root `CLAUDE.md` and
    `knowledge/connections/sdk-subprocess-forces-api-key.md` record that subscription credentials are
    not sanctioned for third-party plugin use.
  - neither set and no credentials file → WARN, keeping today's wording (with no auth at all, "cannot
    run" is true).
- Word the NOTE as *will fall back to*, not *is authenticated*: the bundled binary's auth precedence
  cannot be proven by reading Python source. Existence of the file is the observable; the empirical
  confirmation is `flush.log`'s `FLUSH_OK` + cost line, not a claim the doctor should make.
- Check existence only. Never read, parse, or print the contents of `.credentials.json`.

**Tests**
- Env var set → OK. Neither var, credentials file present in a temp `CLAUDE_CONFIG_DIR` → NOTE, exit
  code unaffected. Neither var, no file → WARN, exit 1. Assert the doctor's output never contains any
  substring of the fixture credentials file.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`

### 7. The changes reach installed caches and are documented

**Files and integration points**
- `plugins/neurawork-cc-harness/commands/nw-doctor.md` — UPDATE.
- `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` — UPDATE (version).
- `plugins/neurawork-cc-harness/CHANGELOG.md` — UPDATE.
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/VERSION` — UPDATE (currently `4`).

**Implementation**
- In `nw-doctor.md`'s "common ones and what they mean" list, add the plugin-currency WARN (fix:
  `/plugin update` + `/reload-plugins`) and the queue "stamped but nothing ingested" WARN (fix: run
  the foreground command and read the error). Keep the file's pinned invariants intact: the
  `"${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"` invocation, `python3` in every fenced block, and the
  "never removes a lock" sentence (`test_skill_assets.py:123-163`).
- Bump `engines/claudemd-lerner/VERSION` `4` → `5`: payload behavior changed, so existing installs
  must be nudged to re-install by `hooks/version-check.py` (`harness_probe.find_stale`).
- Bump the plugin version. `0.5.1` → `0.5.2` is patch-level for the doctor changes under the recorded
  rule in `knowledge/concepts/semver-patch-for-reporting-only-change.md`, but Tasks 1–3 change engine
  payload *behavior*, so this is a minor bump: `0.5.1` → `0.6.0`. Add the CHANGELOG entry naming the
  learner import fix, the stamp-on-success change, the update log, and the two new doctor checks.

**Tests**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` — `test_skill_assets.py`
  still passes against the edited command doc.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`
- `uvx ruff check` from the repo root — clean at `line-length = 100`.

## Acceptance

1. **AC1 — the learner actually runs:** `uv run --directory claudemd-lerner python scripts/update.py --dry-run`
   exits 0 and lists the pending daily logs. No `ModuleNotFoundError` on any invocation path,
   including the exact command `cl-session-start.py` builds, with no `PYTHONPATH` help.
2. **AC2 — a failed run does not fake progress:** when every log errors, `last-update.json` is not
   advanced and no log is recorded as ingested; when one of several succeeds, the stamp advances and
   exactly the successful log appears in `state["ingested"]`.
3. **AC3 — the failure is no longer silent:** the update child's stdout and stderr land in
   `claudemd-lerner/scripts/update.log` (gitignored) instead of `/dev/null`, and a failure to open
   that log still lets the hook complete.
4. **AC4 — the doctor names an engine that never ran:** a completion stamp with no ingest state and
   pending logs produces exactly one WARN naming the missing state file and offering the foreground
   command; a fresh install with neither file keeps its current, lower severity.
5. **AC5 — the doctor answers plugin currency:** a run reports installed version vs. the marketplace
   clone's version (WARN with `/plugin update` + `/reload-plugins` when behind, OK when equal, NOTE
   when ahead or unreadable), notes when the running plugin root differs from the installed path,
   lists leftover cache versions without offering to delete them, and — only when behind and an
   engine `VERSION` differs — notes that re-installing first would install the older engine.
6. **AC6 — the credentials finding is accurate:** with no env var but a subscription login present,
   the finding is a NOTE that says the engines fall back to the bundled CLI and still recommends an
   API key; with no auth at all it stays a WARN. The doctor never emits any content of
   `.credentials.json`.
7. **AC7 — the doctor is still read-only and total:** a run leaves the repo byte-identical, spawns no
   process, and produces a full report with a correct exit code when the plugins dir, marketplace
   clone, `settings.json`, or any install dir is missing or unparsable.

## Validation

| Gate | Command or procedure | Proves |
|---|---|---|
| Learner engine | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s claudemd-lerner/tests` | AC1, AC2, AC3 |
| Doctor + probe + command assets | `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | AC4, AC5, AC6, AC7 |
| Unaffected engines | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests` then `-s knowledge-compiler/tests`, `-s compliance-compiler/tests`, `-s stack-compiler/tests` | No regression in the other three engines or the shared helpers |
| Lint | `uvx ruff check` from the repo root | `line-length = 100` clean |
| Runtime — engine | `uv run --directory claudemd-lerner python scripts/update.py --dry-run` | AC1 against the real self-host install; lists pending logs, costs nothing |
| Runtime — doctor | `python3 plugins/neurawork-cc-harness/scripts/doctor.py` and `--json` | AC5 live: `0.5.0` vs. `0.5.1` WARN plus the four leftover cache dirs; AC4 WARN on `claudemd-lerner` |

## Risks and Decisions

| Decision or risk | Recommendation | Evidence / mitigation | Consequence if different |
|---|---|---|---|
| Severity for "no API key but a subscription login exists" | NOTE (exit 0) | It works in practice (`flush.log` `FLUSH_OK` + cost), so a WARN that fails the exit code is noise for a local operator; the unsanctioned-for-distribution point is carried in the message and fix line | WARN keeps the whole run at exit 1 on every developer machine, which is how this check lost its credibility in the first place |
| Tasks 2 and 3 (stamp-on-success, update log) beyond the literal "fix it so ingest state persists" | Include both | Task 2 is the latent second half of the same defect — after the import fix it can still advance the gate with nothing ingested. Task 3 is why the bug survived undetected; without it the next such crash is equally invisible | Dropping Task 2 leaves a silent cost-deferral path; dropping Task 3 leaves the class of failure undetectable at the source, with only the doctor's after-the-fact WARN |
| The doctor reading `~/.claude/plugins` — a new boundary for a repo-scoped tool | Accept, bounded and read-only, every absence degrading to one NOTE | It is the only offline source of the answer the user asked for; `plugin-catalog-cache.json` was checked and holds no `neurawork-cc-harness` entry | Without it, plugin currency cannot be answered at all without network or `subprocess`, both of which the invariant forbids |
| Plugin bump level | Minor: `0.5.1` → `0.6.0` | The recorded patch rule covers reporting-only changes; Tasks 1–3 change payload behavior, which that rule explicitly excludes | A patch bump understates a behavior change in an installed engine |
| The `stack-compiler` drift test does not cover `claudemd-lerner`, so the two `update.py` copies can silently diverge | Assert byte-identity in Task 1's test | `engines/stack-compiler/tests/test_payload_drift.py` is scoped to `stack-compiler` alone; the other three rely on the installer | The self-host copy can be fixed while the shipped payload stays broken, or the reverse |

## Agent Notes

- Live state at planning time (2026-08-27, repo HEAD `505fad7`, plugin source `0.5.1`, installed cache
  `0.5.0`): `claudemd-lerner/scripts/` holds `last-update.json` (12:30), `last-flush.json` (14:50),
  a `cl-update.lock` from 09:24 and `flush.log` — but no `state.json` and no update log. That is the
  fixture shape Task 4's WARN must match.
- The knowledge base has zero prior coverage of the doctor, `harness_probe.py` or `version-check.py`
  (verified by a full-corpus grep) — this is new ground, and worth a compiled article afterwards.
- Do not run a real `update.py` against this repo while implementing: 6 logs, real LLM cost, and it
  rewrites tracked `CLAUDE.md`/`docs/`. `--dry-run` proves AC1 for free.
