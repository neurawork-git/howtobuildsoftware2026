# Feature: Remove compliance SessionStart hook + framework-level plan-validation config

## Summary

Two coupled refinements to the `compliance-compiler` engine, shipped byte-identical in both trees (`plugins/neurawork-cc-harness/engines/compliance-compiler/payload/` and the `compliance-base/` self-host). **(1)** Fully remove the `co-session-start.py` SessionStart hook so SessionStart context is reserved for the knowledge-compiler concepts — the catalog is already built at install time and on demand via `/co-extract`, so the lazy inject/bootstrap is redundant. Remove the now-dead extract-gate helpers it alone used. **(2)** Add a framework-level `validate_frameworks` config key that selects which frameworks the PostToolUse plan-validator checks PRP plans against, independent of which frameworks are extracted (default = all extracted frameworks). One plan / one PR.

## User Story

As a NeuraWork engineer using this repo
I want the compliance engine to stop injecting its catalog at SessionStart and to let me choose which frameworks are enforced on plans
So that SessionStart stays free for the knowledge concepts, and plan validation can be scoped (e.g. extract all three but only enforce SOC 2 + ISO 27001).

## Problem Statement

`co-session-start.py` injects the full `index.md` catalog into every SessionStart (competing with the knowledge concepts for the context budget) and lazily bootstraps the catalog "if missing" — but the catalog is already built at install (`install.py --extract`) and rebuildable via `/co-extract`, so the lazy path is dead weight. Separately, the plan-validator always checks against **all** extracted frameworks (`cfg["frameworks"]`) with no way to scope enforcement. Testable: after install, SessionStart must show no compliance catalog; and with `validate_frameworks: ["soc2"]`, `precheck` on a plan must only flag SOC 2 mandatory ids.

## Solution Statement

**(1)** Delete `co-session-start.py` (both trees); drop the SessionStart tuple from `install.py._hooks()` (keep PostToolUse); hand-remove the stale live `.claude/settings.json` SessionStart entry (`merge_hooks` is add-only and never prunes); drop the SessionStart key from `recon.py`; remove the hook-only dead code (`should_extract` + its test class, `catalog_is_missing`, `LOCK_FILE`, `extract_age_hours`) — keep `LAST_EXTRACT_FILE` (extract.py writes it); update tests + docs. **(2)** Add `validation_frameworks(cfg)` to `utils.py` returning `cfg.get("validate_frameworks") or cfg.get("frameworks", [])`, and call it at the two validate read-sites (`precheck.py:39`, `validate.py:74`); add `validate_frameworks: []` to `DEFAULT_CFG` + both config JSONs; `extract.py` untouched.

## Metadata

| Field            | Value                                             |
| ---------------- | ------------------------------------------------- |
| Type             | REFACTOR + ENHANCEMENT                            |
| Complexity       | MEDIUM                                            |
| Systems Affected | compliance-compiler engine (payload + self-host), install/recon, live settings.json, tests, docs |
| Dependencies     | none (stdlib-only paths; no new libs)             |
| Estimated Tasks  | 10                                                |

---

## UX Design

### Before State
```
SessionStart (every session)
  knowledge-base/session-start.py   -> injects concepts   ┐
  claudemd-lerner/cl-session-start  -> injects docs ctx    ├─ shared context budget
  compliance-base/co-session-start  -> injects FULL catalog┘  ← competes, + lazy bootstrap

PRP plan write --PostToolUse--> co-post-tooluse -> precheck(cfg["frameworks"]) + validate.py(cfg["frameworks"])
                                                    ↑ always ALL extracted frameworks, no scoping
```

### After State
```
SessionStart (every session)
  knowledge-base/session-start.py   -> concepts   ┐  compliance no longer here —
  claudemd-lerner/cl-session-start  -> docs ctx   ┘  SessionStart free for concepts
  (compliance: catalog built at install & via /co-extract, not at SessionStart)

PRP plan write --PostToolUse--> co-post-tooluse -> precheck(validation_frameworks(cfg))
                                                 -> validate.py(validation_frameworks(cfg))
                                                    ↑ validate_frameworks subset if set, else all
extract.py --unchanged--> still uses cfg["frameworks"]  (extract path separate)
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| SessionStart | compliance catalog injected + lazy bootstrap | nothing from compliance | Concepts get full SessionStart budget |
| `config.json` | `frameworks` drives both extract + validate | `validate_frameworks` scopes plan checks | Enforce a subset without changing extraction |
| Catalog build | lazy at SessionStart if missing | install (`--extract`) + `/co-extract` only | Explicit, no surprise recurring cost |

---

## Mandatory Reading

| Priority | File | Lines | Why |
|----------|------|-------|-----|
| P0 | `plugins/neurawork-cc-harness/engines/_shared/settings.py` | 23-81 | `merge_hooks` is ADD-ONLY — proves the live entry must be hand-removed |
| P0 | `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | 1-6, 91-96, 125-127, 42-43 | docstring, `_hooks()`, merge call, `.gitignore` template |
| P0 | `compliance-base/scripts/precheck.py` | 37-50 | validate read-site #1 (`cfg.get("frameworks")`) |
| P0 | `compliance-base/scripts/validate.py` | 31-37, 71-91, 105 | validate read-site #2 (`_catalog_text(cfg.get("frameworks"))`) |
| P0 | `compliance-base/scripts/config.py` | 31-33, 47-54, 57-67 | `LOCK_FILE`/`extract_age_hours` to remove, `DEFAULT_CFG`, `load_cfg` |
| P0 | `compliance-base/scripts/utils.py` | 1-6, 84-108, 79-81 | module docstring, `should_extract` (remove), `catalog_is_missing` (remove) |
| P1 | `.claude/settings.json` | 3-24 | the exact SessionStart array; remove compliance entry (3rd element), keep first two |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/recon.py` | ~23 | `HOOK_EVENTS` SessionStart key to drop |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py` | 46-71 | assertions at 63 + 70-71 to flip |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_shards_precheck.py` | 36-58, 63-99 | `TestShouldExtract` to delete; `TestPrecheck` pattern to mirror for the new test |
| P1 | `compliance-base/hooks/co-post-tooluse.py` | 14-31, 83-98 | confirms the staying hook is independent; loads whole cfg |
| P2 | `compliance-base/scripts/extract.py` | 33, 171-174 | `_stamp_last_extract` — why `LAST_EXTRACT_FILE` must STAY |
| P2 | `CLAUDE.md` (root) | 55-63 | hooks prose to correct |
| P2 | `plugins/neurawork-cc-harness/commands/co-extract.md` | 6-10 | "SessionStart bootstrap gate" prose to reword |

**External Documentation:** none — no third-party libraries involved; the change is internal engine wiring.

---

## Patterns to Mirror

**HOOK TUPLE / `_hooks()` (drop the SessionStart element):**
```python
# SOURCE: plugins/.../compliance-compiler/install.py:91-96 — AFTER: keep only PostToolUse
def _hooks(cdir: str) -> list[tuple[str, str, int, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{cdir}" python'
    return [
        ("PostToolUse", f"{base} hooks/co-post-tooluse.py", 15, "hooks/co-post-tooluse.py"),
    ]
```

**VALIDATE READ-SITE #1 (precheck):**
```python
# SOURCE: compliance-base/scripts/precheck.py:37-40 — AFTER
def precheck(plan_text: str, cfg: dict, catalog_dir: Path | None = None) -> dict:
    frameworks = validation_frameworks(cfg)     # was: cfg.get("frameworks", [])
    constraints = load_constraints(frameworks, catalog_dir)
```

**VALIDATE READ-SITE #2 (validate.py):**
```python
# SOURCE: compliance-base/scripts/validate.py:74 (inside validate_one) — AFTER
    catalog_text = _catalog_text(validation_frameworks(cfg))  # was: cfg.get("frameworks", [])
# add near the top imports: from utils import validation_frameworks
```

**NEW HELPER (mirror the pure-util style of utils.py:69-76):**
```python
# ADD to utils.py (both trees), pure/stdlib, no SDK
def validation_frameworks(cfg: dict) -> list[str]:
    """Frameworks the plan-validator checks against: ``validate_frameworks`` when
    set, else all extracted ``frameworks``. Extraction is unaffected (it keeps
    reading ``frameworks``)."""
    return cfg.get("validate_frameworks") or cfg.get("frameworks", [])
```

**CONFIG DEFAULT (mirror DEFAULT_CFG shape, config.py:47-54):**
```python
# AFTER: drop extract_age_hours (hook-only), add validate_frameworks
DEFAULT_CFG = {
    "catalog_dir": "compliance-base",
    "model": "",
    "frameworks": ["gdpr", "soc2", "iso27001"],
    "validate_frameworks": [],   # empty -> validate against all `frameworks`
    "max_concurrency": 12,
    "validate_mode": "warn",
}
```

**PURE-LOGIC TEST (mirror TestPrecheck, test_shards_precheck.py:63-99):**
```python
# ADD a TestValidationFrameworks: build a temp catalog with gdpr.json + soc2.json,
# precheck a plan with cfg={"frameworks":[...3], "validate_frameworks":["soc2"]},
# assert mandatory_total counts ONLY soc2, and missing_mandatory_ids are soc2-only.
```

**SETTINGS ENTRY TO HAND-REMOVE (merge_hooks never prunes — settings.py:57-75):**
```jsonc
// SOURCE: .claude/settings.json SessionStart[0].hooks — remove ONLY this 3rd element:
{ "type": "command",
  "command": "uv run --directory \"$CLAUDE_PROJECT_DIR/compliance-base\" python hooks/co-session-start.py",
  "timeout": 15 }
// KEEP the knowledge-base/session-start.py and claudemd-lerner/cl-session-start.py entries.
```

---

## Files to Change

Scripts/hooks changes apply to **BOTH** trees byte-identical (payload + compliance-base); `install.py`/`recon.py`/`tests/` exist once (engine only); `.claude/settings.json` + `compliance-base/config.json` + `compliance-base/.gitignore` are self-host live only.

| File | Action | Justification |
|------|--------|---------------|
| `…/payload/hooks/co-session-start.py` | DELETE | The SessionStart hook |
| `compliance-base/hooks/co-session-start.py` | DELETE | Live copy |
| `…/compliance-compiler/install.py` | UPDATE | `_hooks()` drop SessionStart tuple; docstring; `.gitignore` template drop `co-extract.lock` |
| `…/compliance-compiler/recon.py` | UPDATE | Drop SessionStart from `HOOK_EVENTS` |
| `…/payload/scripts/config.py` + `compliance-base/scripts/config.py` | UPDATE | Remove `LOCK_FILE`, `extract_age_hours`; keep `LAST_EXTRACT_FILE` |
| `…/payload/scripts/utils.py` + `compliance-base/scripts/utils.py` | UPDATE | Remove `should_extract`, `catalog_is_missing`; add `validation_frameworks`; fix docstring |
| `…/payload/scripts/precheck.py` + `compliance-base/scripts/precheck.py` | UPDATE | Use `validation_frameworks(cfg)` |
| `…/payload/scripts/validate.py` + `compliance-base/scripts/validate.py` | UPDATE | Use `validation_frameworks(cfg)` + import |
| `…/compliance-compiler/config.default.json` | UPDATE | Remove `extract_age_hours`, add `validate_frameworks: []` |
| `compliance-base/config.json` | UPDATE | Same key changes (live) |
| `…/compliance-compiler/tests/test_install_recon.py` | UPDATE | Flip lines 63 + 70-71 |
| `…/compliance-compiler/tests/test_shards_precheck.py` | UPDATE | Delete `TestShouldExtract`; add `TestValidationFrameworks` |
| `.claude/settings.json` | UPDATE | Hand-remove compliance SessionStart entry |
| `compliance-base/.gitignore` | UPDATE | Remove `scripts/co-extract.lock` line |
| `CLAUDE.md` (root) | UPDATE | Correct hooks prose (SessionStart bootstrap → PostToolUse only; catalog at install/on-demand) |
| `plugins/neurawork-cc-harness/commands/co-extract.md` | UPDATE | Reword "SessionStart bootstrap gate" |

---

## NOT Building (Scope Limits)

- **`merge_hooks` prune capability** — not adding auto-removal of stale hooks to the shared `_shared/settings.py` (used by all engines; out of scope, risk). The live entry is hand-removed; external installs would keep a harmless stale entry until manual cleanup — noted as a known limitation.
- **Removing `LAST_EXTRACT_FILE`** — `extract.py._stamp_last_extract` still writes it; keep the constant + its `.gitignore` line.
- **Per-constraint / per-category validation selection** — decided framework-level only.
- **Changing the extract path** — `extract.py` keeps `cfg["frameworks"]`; extraction scope is unchanged.
- **Touching knowledge-compiler / claudemd-lerner SessionStart hooks** — leave intact.
- **Rewriting archived docs** — the completed/ plan + report that describe the old hook stay as historical record.

---

## Step-by-Step Tasks

Apply every scripts/hooks change to **both trees**; a `diff -q` parity gate validates.

### Task 1: Add `validation_frameworks` to `utils.py` (both trees)
- **ACTION**: Add the pure helper (see Patterns to Mirror) after `referenced_ids`.
- **MIRROR**: `compliance-base/scripts/utils.py:69-76` (pure-util style).
- **VALIDATE**:
  ```bash
  python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import utils; \
print(utils.validation_frameworks({'frameworks':['gdpr','soc2'],'validate_frameworks':['soc2']}), \
utils.validation_frameworks({'frameworks':['gdpr']}))"
  ```
  **EXPECT**: `['soc2'] ['gdpr']`.

### Task 2: Wire `precheck.py` to the helper (both trees)
- **ACTION**: Replace `frameworks = cfg.get("frameworks", [])` (line 39) with `frameworks = validation_frameworks(cfg)`; ensure `from utils import ..., validation_frameworks`.
- **MIRROR**: precheck.py:14 import line, extend it.
- **VALIDATE**: `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests -p 'test_shards_precheck.py'` (existing TestPrecheck still passes — absent `validate_frameworks` ⇒ falls back to `frameworks`).

### Task 3: Wire `validate.py` to the helper (both trees)
- **ACTION**: At line 74 use `validation_frameworks(cfg)`; add `from utils import validation_frameworks` near existing imports.
- **GOTCHA**: `validate.py` imports from `config`; add the `utils` import alongside (utils resolves via the same `sys.path` insert).
- **VALIDATE**: `python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import validate"` (imports clean; SDK import is deferred inside `validate_one`).

### Task 4: Config default — drop `extract_age_hours`, add `validate_frameworks` (both trees + both JSONs)
- **ACTION**: In `config.py` `DEFAULT_CFG`: remove `"extract_age_hours": 168`, add `"validate_frameworks": []`. Same in `engines/compliance-compiler/config.default.json` and `compliance-base/config.json`.
- **VALIDATE**: `python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import config; print('extract_age_hours' not in config.DEFAULT_CFG, 'validate_frameworks' in config.DEFAULT_CFG)"` → `True True`; `python3 -c "import json; json.load(open('compliance-base/config.json'))"`.

### Task 5: Remove `LOCK_FILE` from `config.py` (both trees)
- **ACTION**: Delete the `LOCK_FILE = SCRIPTS_DIR / "co-extract.lock"` line + the "Trigger coordination" comment referencing it. Keep `LAST_EXTRACT_FILE` (extract.py uses it).
- **GOTCHA**: Do NOT remove `LAST_EXTRACT_FILE` — `extract.py:33,171-174` imports/writes it; removal breaks extract import.
- **VALIDATE**: `python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import config, extract; print(hasattr(config,'LAST_EXTRACT_FILE'), not hasattr(config,'LOCK_FILE'))"` → `True True`.

### Task 6: Remove dead gate helpers from `utils.py` (both trees)
- **ACTION**: Delete `should_extract` and `catalog_is_missing` (+ the "Extract trigger gate (pure)" section header and the docstring sentence naming the SessionStart gate). Keep `load_state/save_state/file_hash/load_constraints/mandatory_ids/referenced_ids/catalog_file/validation_frameworks`.
- **GOTCHA**: `co-post-tooluse.py` + `precheck.py` do NOT import these (verified) — safe.
- **VALIDATE**: `grep -rn "should_extract\|catalog_is_missing" compliance-base/scripts plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts` → only nothing (or, before Task 8, the test file).

### Task 7: Delete the hook file (both trees)
- **ACTION**: `rm` `…/payload/hooks/co-session-start.py` and `compliance-base/hooks/co-session-start.py`.
- **VALIDATE**: `ls compliance-base/hooks/` → only `co-post-tooluse.py`.

### Task 8: `install.py` + `recon.py` — drop SessionStart registration
- **ACTION**: `install.py._hooks()` remove the SessionStart tuple (keep PostToolUse); edit docstring line 4-5 ("merges the SessionStart + PostToolUse hooks" → "merges the PostToolUse hook"); in the `.gitignore` template remove the `scripts/co-extract.lock` line (keep `scripts/last-extract.json`). `recon.py` remove the `"SessionStart": "co-session-start.py"` entry from `HOOK_EVENTS`.
- **VALIDATE**: `python3 -c "import ast; ast.parse(open('plugins/neurawork-cc-harness/engines/compliance-compiler/install.py').read())"`; `grep -n "co-session-start\|SessionStart" plugins/neurawork-cc-harness/engines/compliance-compiler/install.py plugins/neurawork-cc-harness/engines/compliance-compiler/recon.py` → no hits.

### Task 9: Update tests
- **ACTION**: `test_install_recon.py`: line 63 — remove the `co-session-start.py` exists-assert (or flip to `assertFalse`); lines 70-71 — since the temp repo installs only compliance, assert `"PostToolUse" in settings["hooks"]` and `"SessionStart" not in settings["hooks"]`. `test_shards_precheck.py`: delete the whole `TestShouldExtract` class (lines 36-58) and its now-unused imports if any; add `TestValidationFrameworks` mirroring `TestPrecheck` — temp catalog with gdpr.json + soc2.json, `precheck(plan, {"frameworks":["gdpr","soc2"], "validate_frameworks":["soc2"]}, catalog)` asserts `mandatory_total` counts soc2 only and `missing_mandatory_ids` are soc2 ids.
- **VALIDATE**: `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests` → OK.

### Task 10: Remove the live SessionStart entry + update docs
- **ACTION**: `.claude/settings.json` — delete the 3rd element of `SessionStart[0].hooks` (the `compliance-base/…/co-session-start.py` object); keep the other two. `compliance-base/.gitignore` — remove the `scripts/co-extract.lock` line. Root `CLAUDE.md` — reword the hooks paragraph: compliance-compiler contributes a PostToolUse plan-validator (no SessionStart); catalog built at install and via `/co-extract`; mention `validate_frameworks`. `commands/co-extract.md` — reword "does not wait for the SessionStart bootstrap gate" (the gate is gone).
- **VALIDATE**:
  ```bash
  python3 -c "import json; s=json.load(open('.claude/settings.json')); \
cmds=[h['command'] for g in s['hooks']['SessionStart'] for h in g['hooks']]; \
print('co-session-start' not in ' '.join(cmds), len(cmds))"
  ```
  **EXPECT**: `True 2` (knowledge + claudemd remain, compliance gone).

---

## Testing Strategy

### Unit Tests
| Test File | Test Cases | Validates |
|-----------|-----------|-----------|
| `tests/test_shards_precheck.py` | remove `TestShouldExtract`; add `TestValidationFrameworks` (subset scopes; fallback when unset) | `validate_frameworks` honored by precheck |
| `tests/test_install_recon.py` | co-session-start absent; SessionStart not registered; PostToolUse present | hook removal |

### Edge Cases Checklist
- [ ] `validate_frameworks` absent → behaves as today (all frameworks)
- [ ] `validate_frameworks: []` → falls back to all frameworks (empty is falsy)
- [ ] `validate_frameworks: ["soc2"]` with `frameworks:[all]` → precheck flags only soc2 mandatory ids
- [ ] `extract.py --dry-run` still lists all `frameworks` (extract path unchanged)
- [ ] `co-post-tooluse.py` imports clean after utils/config trims
- [ ] Fresh install into temp repo registers only PostToolUse (no SessionStart)
- [ ] `should_extract`/`catalog_is_missing`/`LOCK_FILE` gone; `LAST_EXTRACT_FILE` present

---

## Validation Commands

### Level 1: STATIC + IMPORTS
```bash
uvx ruff check compliance-base/scripts plugins/neurawork-cc-harness/engines/compliance-compiler
python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import config, utils, precheck, validate, extract, co_post 2>/dev/null" 2>/dev/null || \
python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import config, utils, precheck, validate, extract"
```
**EXPECT**: exit 0.

### Level 2: UNIT TESTS (per directory)
```bash
cd plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s compliance-compiler/tests
python3 -m unittest discover -s _shared/tests
```
**EXPECT**: OK.

### Level 3: FULL ENGINE SUITE (no regressions)
```bash
cd plugins/neurawork-cc-harness/engines
for d in _shared knowledge-compiler claudemd-lerner compliance-compiler; do python3 -m unittest discover -s $d/tests; done
```

### Level 4: TREE PARITY
```bash
P=plugins/neurawork-cc-harness/engines/compliance-compiler/payload; CB=compliance-base
for f in scripts/config.py scripts/utils.py scripts/precheck.py scripts/validate.py; do
  diff -q "$P/$f" "$CB/$f" || echo "DRIFT: $f"; done
[ ! -e "$P/hooks/co-session-start.py" ] && [ ! -e "$CB/hooks/co-session-start.py" ] && echo "hook deleted both trees ✓"
```
**EXPECT**: no DRIFT; hook gone.

### Level 5: LIVE SETTINGS + BEHAVIOR
```bash
python3 -c "import json; s=json.load(open('.claude/settings.json')); \
print('SessionStart compliance gone:', all('co-session-start' not in h['command'] for g in s['hooks']['SessionStart'] for h in g['hooks']))"
uv run --directory compliance-base python scripts/extract.py --dry-run   # extract still all frameworks
```

### Level 6: MANUAL
- Open a new session in this repo → confirm no "## Compliance Catalog" block appears at SessionStart (concepts only).
- Write a throwaway `.claude/PRPs/plans/x.plan.md` with `validate_frameworks:["soc2"]` set → PostToolUse precheck reports soc2 mandatory only.

---

## Acceptance Criteria
- [ ] `co-session-start.py` deleted (both trees); live SessionStart has no compliance entry, other two intact
- [ ] Fresh install registers only PostToolUse (test green)
- [ ] `validation_frameworks` honored by precheck (unit-tested); `extract.py` still uses `frameworks`
- [ ] Dead code removed (`should_extract`+test, `catalog_is_missing`, `LOCK_FILE`, `extract_age_hours`); `LAST_EXTRACT_FILE` kept
- [ ] Levels 1-5 pass; no sibling-engine regressions; tree parity clean
- [ ] Docs (root CLAUDE.md, co-extract.md) corrected

## Completion Checklist
- [ ] Tasks 1-10 done and validated in order
- [ ] Level 1 static/imports pass
- [ ] Level 2/3 unit suites pass
- [ ] Level 4 parity clean
- [ ] Level 5 live-settings check passes
- [ ] SessionStart shows no compliance context (Level 6 manual)

---

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Removing `LAST_EXTRACT_FILE` by mistake breaks extract.py import | MED | HIGH | Task 5 explicitly keeps it; Level 1 imports `extract` |
| Stale SessionStart entry persists (merge_hooks add-only) | HIGH (external installs) | LOW | Hand-remove live entry (Task 10); document limitation; fresh installs correct |
| Payload/self-host drift | MED | MED | Level 4 `diff -q` gate + "both trees" on every task |
| `validate.py` missing the `utils` import | MED | MED | Task 3 adds it; Level 1 imports `validate` |
| Removing test class hides a still-needed path | LOW | LOW | `should_extract` has no caller after hook removal (verified) |

---

## Compliance

**Scope**: internal engine refactor + a config knob — no personal-data processing, no interface, no runtime data flow. The substantive runtime obligations of GDPR / SOC 2 / ISO 27001 do not apply at this plan's scope. This change *tunes the compliance tooling itself*: it makes plan-validation coverage **configurable** (`validate_frameworks`) while leaving the PostToolUse validator — the mechanism that enforces mandatory-constraint coverage on PRP plans — fully intact. Extraction still covers all frameworks; only which frameworks are *enforced on plans* becomes selectable, defaulting to all (no reduction in default enforcement). Outputs stay inside the repo, never under `.claude/` (`repo_guard`), unchanged.

---

## Notes

- **Why remove, not shrink, the SessionStart hook**: the catalog is built at install (`install.py --extract`) and on demand (`/co-extract`); the lazy "build if missing" never fires once the catalog exists (it's committed), and the injection only competes with the knowledge concepts. Both jobs are redundant here.
- **`validate_frameworks` empty-list semantics**: `cfg.get("validate_frameworks") or cfg.get("frameworks", [])` — `[]`/absent/None all fall back to the full extracted set, so existing installs behave identically until the key is set.
- **merge_hooks limitation**: it only ever adds/updates; it cannot prune. A future improvement (not here) could teach it to remove markers no longer in an engine's `_hooks()`. For now the live entry is removed by hand.
- **Confidence**: 9/10 — both change-surfaces were exhaustively mapped (exact file:line), the validate override is two lines behind a tested helper, and every dead symbol's sole caller was verified. Main residual is doc-prose wording.
