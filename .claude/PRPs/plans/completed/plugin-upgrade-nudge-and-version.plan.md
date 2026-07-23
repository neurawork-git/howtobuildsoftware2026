# Feature: Plugin upgrade UX — staleness nudge + plugin.json version

## Summary

Two related low-risk enhancements that close the plugin-upgrade UX gap identified while
auditing how users upgrade `neurawork-cc-harness`:

- **Feature A — `version` in `plugin.json`.** Add a semver `version` field to the plugin
  manifest so releases are identifiable (currently only per-engine integer `VERSION`
  files exist; the manifest has no version at all).
- **Feature B — staleness nudge.** Add a **plugin-level** `SessionStart` hook that, in any
  repo with a harness install, compares each installed engine's stamped `VERSION` against
  the plugin's currently-shipped engine `VERSION` and, when the install is behind, injects
  a short note telling the user to re-run the installer (ADOPT) to propagate the upgrade.

Feature B is the real gap: because engine machinery is **copied into the target repo** at
install time, `/plugin marketplace update` alone never refreshes it, and today nothing tells
the user their in-repo copy is stale. The check must run from the plugin (not the installed
copy) because only plugin-invoked code has `CLAUDE_PLUGIN_ROOT` and can therefore read the
shipped VERSION to compare against.

## User Story

As a **user who installed the harness into a repo and later ran `/plugin marketplace update`**
I want to **be told when my in-repo engine copy is behind the updated plugin**
So that **I know to re-run the install skill (ADOPT) to actually get the fix, instead of
silently running stale engine code.**

## Problem Statement

- The plugin manifest (`plugins/neurawork-cc-harness/.claude-plugin/plugin.json`) has no
  `version` field — releases are not identifiable from the manifest.
- After `/plugin marketplace update`, a repo whose `knowledge-base/` / `claudemd-lerner/` /
  `compliance-base/` engine copy predates the update keeps running the old code, and the user
  gets **no signal** that an ADOPT re-run is needed. This is testable: install engine at
  VERSION N into a repo, bump the plugin engine to N+1, start a session → today nothing warns;
  after this change → a nudge appears.

## Solution Statement

- **A:** add `"version": "0.1.0"` to the manifest (semver, decoupled from the three
  independent per-engine integer `VERSION` counters — it names the plugin *release*, not any
  one engine). A tiny test guards that the manifest stays valid JSON with a semver `version`.
- **B:** add `plugins/neurawork-cc-harness/hooks/hooks.json` registering a `SessionStart` hook
  that runs `plugins/neurawork-cc-harness/hooks/version-check.py` (stdlib-only, system
  `python3`, no `uv`). The script:
  1. reads `CLAUDE_PROJECT_DIR` (repo root) and `CLAUDE_PLUGIN_ROOT` (plugin root);
  2. parses `<repo>/.claude/settings.json` to locate each engine's installed dir by its unique
     hook-command marker;
  3. for each found engine, compares `<repo>/<dir>/VERSION` (installed) vs
     `$CLAUDE_PLUGIN_ROOT/engines/<engine>/VERSION` (shipped);
  4. if any installed VERSION is behind, prints a `SessionStart` `additionalContext` JSON
     block naming the stale installs and the exact re-install command; otherwise prints
     nothing (silent no-op — including in repos with no harness install).

## Metadata

| Field            | Value |
| ---------------- | ----- |
| Type             | ENHANCEMENT |
| Complexity       | LOW |
| Systems Affected | plugin manifest, NEW plugin-level `hooks/`, docs (INSTALL/ARCHITECTURE), `_shared/tests` |
| Dependencies     | none (stdlib Python ≥ 3.12; no new runtime deps) |
| Estimated Tasks  | 7 |

---

## UX Design

### Before State
```
┌──────────────┐   /plugin marketplace update    ┌────────────────────┐
│ user's repo  │ ──────────────────────────────► │ plugin cache bumped │
│ knowledge-   │                                  │ engine VERSION 1→2  │
│ base/ (v1)   │                                  └────────────────────┘
└──────────────┘
        │  next session
        ▼
┌──────────────────────────────────────────────┐
│ SessionStart hooks run from the INSTALLED     │
│ copy (v1). No visibility into plugin (v2).    │
│ → user keeps running stale engine, unaware.   │  ◄── PAIN: silent drift
└──────────────────────────────────────────────┘

USER_FLOW: update plugin → nothing changes in the repo → no signal.
PAIN_POINT: in-repo engine copy is behind the plugin, silently.
DATA_FLOW: plugin VERSION and installed VERSION never compared anywhere.
```

### After State
```
┌──────────────┐   /plugin marketplace update    ┌────────────────────┐
│ user's repo  │ ──────────────────────────────► │ plugin cache bumped │
│ knowledge-   │                                  │ engine VERSION 1→2  │
│ base/ (v1)   │                                  └────────────────────┘
        │  next session
        ▼
┌───────────────────────────────────────────────┐
│ NEW plugin-level SessionStart hook (runs FROM  │  ◄── has CLAUDE_PLUGIN_ROOT
│ the plugin): reads shipped v2, finds installed │
│ dir via settings.json, reads installed v1.     │
│ v1 < v2 → additionalContext nudge:             │
│  "knowledge-compiler in knowledge-base/ is     │
│   behind (installed 1 < shipped 2). Re-run     │
│   /neurawork-cc-harness:knowledge-compiler."   │
└───────────────────────────────────────────────┘

USER_FLOW: update plugin → next session surfaces a nudge for each stale install.
VALUE_ADD: user learns an ADOPT re-run is needed; no more silent stale code.
DATA_FLOW: plugin VERSION ⇄ installed VERSION compared once per session, per engine.
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| Session start, plugin enabled | no version awareness | stale installs listed with re-run command | knows to re-run installer |
| `plugin.json` | no `version` | `"version": "0.1.0"` | releases identifiable |
| Repos with no install | (n/a) | hook is a silent no-op | zero noise |

---

## Mandatory Reading

**Implementation agent MUST read these before starting:**

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `plugins/neurawork-cc-harness/engines/_shared/settings.py` | 23-80 | `merge_hooks` dedup-by-marker contract + atomic write; the settings.json shape the version-check must PARSE (groups → hooks → command) |
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py` | 95-107 | `_scaffold` VERSION stamp (`shutil.copy2(VERSION_FILE, target/"VERSION")`) + `_hooks()` marker `hooks/session-start.py` |
| P0 | `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | 93-97 | compliance `_hooks()` marker `hooks/co-post-tooluse.py` (its only hook — how the nudge finds compliance) |
| P0 | `plugins/neurawork-cc-harness/engines/claudemd-lerner/install.py` | 95-101 | claudemd `_hooks()` marker `hooks/cl-session-start.py` |
| P1 | `knowledge-base/hooks/session-start.py` | 109-118 | the `hookSpecificOutput`/`additionalContext` JSON print shape to mirror |
| P1 | `.claude/settings.json` | all | live example of the command strings to parse (`uv run --directory "$CLAUDE_PROJECT_DIR/<dir>" ...`) |
| P1 | `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` | all | manifest to add `version` to |
| P2 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/tests/test_install_recon.py` | 27-96 | temp-git-repo + subprocess test style to follow |
| P2 | `plugins/neurawork-cc-harness/engines/_shared/tests/test_settings.py` | all | where the new stdlib unit test will sit (discovered by the documented `-s _shared/tests` run) |

**External Documentation:** none required — stdlib Python + plugin `hooks.json`
conventions (already covered by the `plugin-dev:plugin-structure` skill: hooks auto-load
from `hooks/hooks.json`; use `${CLAUDE_PLUGIN_ROOT}` in the command; events include
`SessionStart`).

---

## Patterns to Mirror

**HOOK OUTPUT (additionalContext JSON) — SOURCE: `knowledge-base/hooks/session-start.py:113-118`:**
```python
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": build_context(),
    }
}))
```

**settings.json PARSE shape — SOURCE: `engines/_shared/settings.py:57-62` (how entries are stored, so how to read them back):**
```python
groups = hooks_obj.setdefault(event, [])
existing = next((h for g in groups for h in g.get("hooks", [])
                 if marker in str(h.get("command", ""))), None)
```
The version-check reads the same structure: `settings["hooks"]["SessionStart"|"PreCompact"|"SessionEnd"|"PostToolUse"] → [group] → group["hooks"] → [ {command} ]`, then substring-matches each engine's marker in `command`.

**VERSION stamp (proves installed==shipped only right after install) — SOURCE: `engines/knowledge-compiler/install.py:98`:**
```python
shutil.copy2(VERSION_FILE, target / "VERSION")   # unconditional, even on ADOPT
```

**Config default-merge safety (never-raise file read) — SOURCE: `knowledge-compiler/payload/scripts/config.py:50-57`** — mirror this defensive `try/except (JSONDecodeError, OSError)` style when reading settings.json / VERSION files so the hook never breaks a session.

**Temp-git-repo subprocess test — SOURCE: `engines/knowledge-compiler/tests/test_install_recon.py:27-44`** (git init + subprocess). For the pure-function unit test, prefer importing `version-check.py` by path and calling its helpers directly.

---

## Files to Change

| File | Action | Justification |
| ---- | ------ | ------------- |
| `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` | UPDATE | Add `"version": "0.1.0"` (Feature A) |
| `plugins/neurawork-cc-harness/hooks/hooks.json` | CREATE | Register the plugin-level `SessionStart` hook (Feature B) |
| `plugins/neurawork-cc-harness/hooks/version-check.py` | CREATE | Stdlib staleness-check script (Feature B) |
| `plugins/neurawork-cc-harness/engines/_shared/tests/test_version_check.py` | CREATE | Unit tests for the check's pure helpers (import by path) |
| `plugins/neurawork-cc-harness/engines/_shared/tests/test_manifest.py` | CREATE | Assert manifest is valid JSON with a semver `version` |
| `docs/INSTALL.md` | UPDATE | Document the nudge in the Upgrading section |
| `docs/ARCHITECTURE.md` | UPDATE | Note the plugin-level SessionStart hook + version field |

**No changes to any `install.py`, `payload/`, or installed engine copies** — Feature B works
retroactively on already-installed repos precisely because it lives in the plugin, not the
copied payload.

---

## NOT Building (Scope Limits)

- **Auto-upgrade / auto-ADOPT.** The nudge only *informs*; it never mutates the user's repo
  (installs are tracked artifacts — the user re-runs the installer deliberately).
- **Switching engine `VERSION` files to semver.** They stay independent integers; only the
  manifest gets a semver. Coupling them is out of scope.
- **Pinning the marketplace `version`.** `.claude-plugin/marketplace.json` keeps tracking the
  latest commit; the manifest `version` is descriptive metadata, not a marketplace pin.
- **A new `co-`/`cl-` installed session-start hook for the nudge.** Rejected — installed hooks
  can't see the plugin VERSION (no `CLAUDE_PLUGIN_ROOT` at runtime). The plugin-level hook is
  the only correct home.
- **Blocking the session** when stale. `additionalContext` only; never a `decision:"block"`.

---

## Step-by-Step Tasks

Execute in order. Each task is atomic and independently verifiable.

### Task 1: UPDATE `plugins/neurawork-cc-harness/.claude-plugin/plugin.json`
- **ACTION**: Add a `"version"` field.
- **IMPLEMENT**: Insert `"version": "0.1.0",` immediately after the `"name"` line (semver;
  0.x signals the README's "early stage" maturity).
- **GOTCHA**: Keep valid JSON (comma placement, double quotes). Do not touch other keys.
- **VALIDATE**: `python3 -c "import json;v=json.load(open('plugins/neurawork-cc-harness/.claude-plugin/plugin.json'))['version'];print(v)"` → prints `0.1.0`.

### Task 2: CREATE `plugins/neurawork-cc-harness/hooks/version-check.py`
- **ACTION**: Stdlib-only staleness check, structured as importable pure helpers + a thin `main()`.
- **IMPLEMENT** (functions, all stdlib):
  - `ENGINES = {"knowledge-compiler": "hooks/session-start.py", "claudemd-lerner": "hooks/cl-session-start.py", "compliance-compiler": "hooks/co-post-tooluse.py"}` — engine → unique settings.json command marker.
  - `installed_dir_for(settings: dict, marker: str) -> str | None`: iterate every event's groups→hooks, find a `command` containing `marker`, extract the dir after `$CLAUDE_PROJECT_DIR/` (regex `\$CLAUDE_PROJECT_DIR/([^"\s]+)`); return the dir segment (e.g. `knowledge-base`). Return `None` if not found.
  - `read_version(path: Path) -> str | None`: return stripped file text or `None` (never raise; `try/except OSError`).
  - `is_behind(installed: str, shipped: str) -> bool`: `int(installed) < int(shipped)` when both parse as int, else `installed != shipped`.
  - `find_stale(repo_root, plugin_root, settings) -> list[dict]`: for each engine, resolve installed dir → read `<repo>/<dir>/VERSION` and `<plugin>/engines/<engine>/VERSION`; if both present and `is_behind`, append `{"engine", "dir", "installed", "shipped"}`.
  - `main()`: read `CLAUDE_PROJECT_DIR` + `CLAUDE_PLUGIN_ROOT` from env (both required — if either missing, exit 0 silently); load `<repo>/.claude/settings.json` defensively (missing/invalid → exit 0); `stale = find_stale(...)`; if empty, exit 0 with no output; else print one `hookSpecificOutput`/`additionalContext` JSON block (mirror `session-start.py:113-118`) whose text lists each stale engine as `"<engine> in <dir>/ is behind (installed <i> < shipped <s>) — re-run /neurawork-cc-harness:<engine> to upgrade."`.
- **MIRROR**: output JSON shape from `knowledge-base/hooks/session-start.py:113-118`; defensive read style from `payload/scripts/config.py:50-57`.
- **GOTCHA**: runs under **system `python3`, not `uv`** — stdlib only, no imports from `_shared` or third-party. Never raise from `main()` (wrap body; a hook crash must not break session start). Silent (no stdout) when nothing is stale or when not in a harness repo.
- **VALIDATE**: `python3 plugins/neurawork-cc-harness/hooks/version-check.py </dev/null` with no env set → exit 0, no output.

### Task 3: CREATE `plugins/neurawork-cc-harness/hooks/hooks.json`
- **ACTION**: Register the `SessionStart` hook.
- **IMPLEMENT**:
  ```json
  {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/version-check.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
  ```
- **MIRROR**: hooks.json structure per the `plugin-dev:plugin-structure` skill (auto-discovered from `hooks/hooks.json`; `${CLAUDE_PLUGIN_ROOT}` for portability).
- **GOTCHA**: This registers a hook that fires in EVERY repo where the plugin is enabled — Task 2's silent-no-op behavior is what keeps that safe.
- **VALIDATE**: `python3 -c "import json;json.load(open('plugins/neurawork-cc-harness/hooks/hooks.json'))"` → exit 0 (valid JSON).

### Task 4: CREATE `plugins/neurawork-cc-harness/engines/_shared/tests/test_version_check.py`
- **ACTION**: Unit-test the pure helpers by importing the script by file path.
- **IMPLEMENT** (stdlib `unittest`, `importlib.util` to load `hooks/version-check.py` from its path):
  - `installed_dir_for`: given a settings dict with a `knowledge-base` command → returns `"knowledge-base"`; renamed dir (`my-kb`) → returns `"my-kb"`; missing marker → `None`.
  - `is_behind`: `("1","2")` True; `("2","2")` False; `("2","1")` False; non-int `("a","b")` → `a!=b` True.
  - `find_stale`: build a temp repo dir with `.claude/settings.json` + `knowledge-base/VERSION=1`, and a temp plugin dir with `engines/knowledge-compiler/VERSION=2` → one stale entry; bump installed to `2` → empty.
  - `main` no-op: with `CLAUDE_PROJECT_DIR`/`CLAUDE_PLUGIN_ROOT` unset → run and assert no stdout (capture) / no exception.
- **MIRROR**: temp-dir + assertion style from `test_install_recon.py:27-96` and `test_settings.py`.
- **VALIDATE**: `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/_shared/tests` (run from `plugins/neurawork-cc-harness/engines/`) → OK.

### Task 5: CREATE `plugins/neurawork-cc-harness/engines/_shared/tests/test_manifest.py`
- **ACTION**: Guard the manifest (Feature A regression test).
- **IMPLEMENT**: load `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` (resolve path relative to the test file), assert it parses, has `name == "neurawork-cc-harness"`, and a `version` matching `^\d+\.\d+\.\d+$`.
- **GOTCHA**: resolve the manifest path from `__file__` (tests run with cwd = `engines/`), not a relative literal.
- **VALIDATE**: same discover command as Task 4 → OK.

### Task 6: UPDATE `docs/INSTALL.md`
- **ACTION**: Extend the **Upgrading** section.
- **IMPLEMENT**: After the existing "re-invoke the install skill … ADOPT …" text, add a short paragraph: a plugin-level `SessionStart` check now surfaces a nudge at session start when an in-repo engine copy is behind the updated plugin, naming the stale install and the re-run command; the nudge is informational only and silent when everything is current.
- **VALIDATE**: `grep -n "nudge\|behind the" docs/INSTALL.md` → matches.

### Task 7: UPDATE `docs/ARCHITECTURE.md`
- **ACTION**: Document the new plugin surface.
- **IMPLEMENT**: In the plugin-source-layout section, add `hooks/hooks.json` + `hooks/version-check.py` (the plugin's only code that runs FROM the plugin with `CLAUDE_PLUGIN_ROOT`); in the runtime section, one line that the plugin-level `SessionStart` hook compares installed vs shipped engine `VERSION` and nudges on drift. Note the manifest now carries a semver `version` distinct from the per-engine integer `VERSION` counters.
- **VALIDATE**: `grep -n "version-check\|plugin-level SessionStart" docs/ARCHITECTURE.md` → matches.

---

## Testing Strategy

### Unit Tests to Write
| Test File | Test Cases | Validates |
|-----------|-----------|-----------|
| `_shared/tests/test_version_check.py` | dir parse (default/renamed/missing), is_behind (int/non-int), find_stale (stale/current), main no-op | Feature B logic |
| `_shared/tests/test_manifest.py` | valid JSON, name, semver version | Feature A |

### Edge Cases Checklist
- [ ] Repo with **no** harness install → hook silent (no markers found).
- [ ] Engine installed under a **renamed** dir → still found via settings.json command.
- [ ] Installed dir present but `VERSION` file missing/removed → skipped, no crash.
- [ ] `CLAUDE_PROJECT_DIR` or `CLAUDE_PLUGIN_ROOT` unset → exit 0 silently.
- [ ] Malformed `.claude/settings.json` → caught, exit 0.
- [ ] All three installs current → no output.
- [ ] compliance-compiler (no session-start of its own) detected via `hooks/co-post-tooluse.py` marker.

---

## Validation Commands

### Level 1: STATIC_ANALYSIS
```bash
cd plugins/neurawork-cc-harness/engines && uvx ruff check
python3 -c "import json; json.load(open('plugins/neurawork-cc-harness/hooks/hooks.json')); json.load(open('plugins/neurawork-cc-harness/.claude-plugin/plugin.json'))"
```
**EXPECT**: exit 0, valid JSON.

### Level 2: UNIT_TESTS
```bash
cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests
```
**EXPECT**: all pass (existing + 2 new files).

### Level 3: FULL_SUITE
```bash
cd plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s _shared/tests
python3 -m unittest discover -s knowledge-compiler/tests
python3 -m unittest discover -s claudemd-lerner/tests
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: all pass (no regressions).

### Level 6: MANUAL_VALIDATION
1. In a scratch git repo, install the knowledge-compiler (or hand-craft `.claude/settings.json` + `knowledge-base/VERSION` = `1`).
2. Set `CLAUDE_PLUGIN_ROOT` to the plugin dir whose `engines/knowledge-compiler/VERSION` = `1` → run `version-check.py` → no output.
3. Bump `engines/knowledge-compiler/VERSION` to `2` → run again → prints the `additionalContext` nudge naming `knowledge-base/` and the re-run command.

---

## Acceptance Criteria
- [ ] `plugin.json` has a semver `version`; `test_manifest.py` passes.
- [ ] Plugin-level `SessionStart` hook registered via `hooks/hooks.json`.
- [ ] `version-check.py` prints a nudge only when an installed engine VERSION < shipped, silent otherwise, never raises.
- [ ] Works for all three engines (incl. compliance via its PostToolUse marker) and for renamed install dirs.
- [ ] Levels 1–3 pass; no regressions in existing engine tests.
- [ ] INSTALL.md + ARCHITECTURE.md document the nudge and the version field.

---

## Completion Checklist
- [ ] Tasks 1–7 done in order, each validated.
- [ ] Level 1 static + JSON checks pass.
- [ ] Level 2 + 3 unittest discovery green.
- [ ] Manual nudge reproduced (Level 6).

---

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
| ---- | ---------- | ------ | ---------- |
| Plugin hook fires in unrelated repos and adds noise | MED | LOW | Silent no-op when no markers found; only prints on real drift |
| `version-check.py` crashes and breaks SessionStart | LOW | MED | Wrap `main()` body; every file read is `try/except`; exit 0 on any doubt; 10s timeout |
| System `python3` unavailable / too old | LOW | LOW | Stdlib-only, no f-string-newer features; `python3` is the documented baseline; hook failure is non-fatal to the session |
| Install dir can't be inferred (user hand-edited settings.json) | LOW | LOW | Marker-substring match tolerates edits; unresolved engine simply skipped |
| Single manifest `version` misread as an engine version | LOW | LOW | Doc note: manifest version = release; engine `VERSION` counters stay independent |

---

## Compliance

Applicable mandatory constraints: **none**. This plan adds developer-tooling to a
Claude Code plugin — a stdlib `SessionStart` hook that reads local `VERSION` files and
prints a text nudge, plus a `version` field in a manifest. It processes, stores, and
transmits **no personal data**, exposes no network surface, handles no authentication,
and touches no user/customer records. The GDPR/SOC2/ISO27001 constraints in the catalog
target a product that processes personal data; they do not apply to this build. (The
automatic precheck flags all mandatory constraints as unreferenced by design — recorded
here as a deliberate not-applicable determination, not an omission.)

## Notes

- **Why a plugin-level hook, not an installed one (core decision):** installed hooks run via
  `uv run --directory "$CLAUDE_PROJECT_DIR/<dir>"` and derive all paths from `__file__` inside
  the copied engine — they have no reference to the plugin and no `CLAUDE_PLUGIN_ROOT`, so they
  cannot read the shipped VERSION. Only plugin-registered hooks get `CLAUDE_PLUGIN_ROOT`. Agent
  trace: `session-start.py:19-21` (path resolution), `_shared/hookio.py:53-55` (`child_env`
  adds only `CLAUDE_INVOKED_BY`), `plugin.json` (no `hooks` key today).
- **Retroactive by design:** because the check lives in the plugin, it works on repos installed
  before this change — no re-install needed to gain the nudge itself.
- **Precedent:** `compliance-compiler/install.py:_prune_removed()` is the existing "detect drift
  vs what we now ship" pattern, but it runs at install time; the nudge covers the *between-installs*
  window that prune cannot.
- **Version pick:** `0.1.0` matches README "early stage." Bump on each release; the marketplace
  entry stays commit-tracking (unchanged).
