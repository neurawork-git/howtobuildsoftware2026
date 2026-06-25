# Feature: neurawork-cc-harness — claudemd-lerner Skill (Phase 3)

## Summary

Add the `claudemd-lerner` skill to the `neurawork-cc-harness` plugin: a per-repo learner that captures Claude Code sessions into `<ldir>/daily/` logs (SessionEnd/PreCompact hooks) and, on a manual command or a 6-hour SessionStart gate, runs an LLM **update** pass that keeps the repo's **CLAUDE.md hierarchy + `docs/` tree** current. It is a near-mechanical **mirror of the Phase-2 `knowledge-compiler` skill**, with three semantic deltas: (1) it writes `CLAUDE.md` files (root + N subdir levels per recon) and `docs/*.md` **at the repo root**, never a `knowledge/` wiki; (2) `compile.py` is replaced by `update.py` (an editor agent over existing CLAUDE.md/docs, not a wiki builder); (3) its hooks use **`cl-`-prefixed filenames** so its `.claude/settings.json` markers can never collide with `knowledge-compiler`'s when both skills are installed in one repo. All shared infra (`engines/_shared/`) is reused unchanged. Capture, dedup, the worktree redirect, the 6h trigger gate, brownfield seed, and the 3-phase install (recon → ask → execute) all mirror Phase 2 exactly.

## User Story

As a NeuraWork engineer or customer
I want my repo's CLAUDE.md hierarchy and `docs/` to stay current automatically from my Claude Code sessions, and to be seeded sanely on an existing repo
So that I stop fighting doc drift and stop re-explaining established conventions every session.

## Problem Statement

CLAUDE.md and `docs/` go stale or never exist; nobody maintains them by hand, so each session re-primes the agent with context that should already be written down. There is no repo-local mechanism that watches sessions and keeps the doc hierarchy current. (The Phase-2 `knowledge-compiler` builds a *separate wiki*; it does NOT maintain the CLAUDE.md/docs the agent actually reads on startup.)

## Solution Statement

Build `engines/claudemd-lerner/` as a structural mirror of `engines/knowledge-compiler/`, reusing the Phase-1 `engines/_shared/` helpers verbatim. Keep the capture pipeline identical (transcript → `<ldir>/daily/<date>.md` via `flush.py`, text-only SDK call). Replace the wiki compiler with `update.py`: an SDK agent (Read/Write/Edit/Glob/Grep, `acceptEdits`) that reads new/changed daily logs + the current CLAUDE.md tree + `docs/` and **edits those files in place** per a new `AGENTS.md` constitution. Recon asks for: lerner dir name, CLAUDE.md depth, docs dir, language, excluded dirs, timezone, and offers a brownfield seed. The 6h SessionStart gate, lock debounce, dedup, worktree redirect, and write-guard are reused from Phase 2's proven shapes. Hooks get `cl-` filename prefixes so markers are unique per skill.

## Metadata

| Field            | Value                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| Type             | NEW_CAPABILITY (sibling of Phase-2; mirror + semantic deltas)        |
| Complexity       | MEDIUM (structure is a known mirror; the new surface is `update.py`, the CLAUDE.md/docs constitution, multi-level recon, and the marker-collision fix) |
| Systems Affected | Plugin skills/commands; per-repo `<ldir>/`; repo-root `CLAUDE.md` + `docs/`; `.claude/settings.json`; `claude-agent-sdk` |
| Dependencies     | `claude-agent-sdk>=0.2.96`, `python-dotenv>=1.0.0`, `tzdata>=2024.1`; `uv`; git; Phase-1 `engines/_shared/` (unchanged) |
| Estimated Tasks  | 19                                                                    |

---

## UX Design

### Before State
```
╔══════════════════════════════════════════════════════════════════════╗
║                            BEFORE STATE                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  neurawork-cc-harness/ ships ONE skill: knowledge-compiler (Phase 2).  ║
║    It builds a separate knowledge/ wiki — it does NOT touch CLAUDE.md. ║
║                                                                        ║
║  A repo's CLAUDE.md + docs/ drift: edited by hand or not at all.       ║
║  Each session re-explains conventions the docs should already hold.    ║
║  PAIN: doc drift; no automatic CLAUDE.md/docs maintenance.            ║
╚══════════════════════════════════════════════════════════════════════╝
```

### After State
```
╔══════════════════════════════════════════════════════════════════════╗
║                             AFTER STATE                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  Install:  /neurawork-cc-harness:claudemd-lerner                       ║
║    recon (read-only) → AskUserQuestion(ldir, CLAUDE.md depth,          ║
║      docs dir, language, excluded dirs, tz, SEED?)                     ║
║      → install.py: copy payload + _shared into <repo>/<ldir>/,         ║
║        scaffold daily/ + scripts/, merge 3 cl- hooks, .gitignore;      ║
║        [optional] run seed.py → initial CLAUDE.md tree + docs/         ║
║    then: uv sync --directory <ldir>                                    ║
║                                                                        ║
║  Per session:                                                          ║
║    SessionEnd / PreCompact ─► capture transcript ─► spawn flush.py     ║
║         flush.py (SDK, text-only) ─► append <ldir>/daily/<date>.md     ║
║    SessionStart ─► inject current root CLAUDE.md + docs/ listing       ║
║                 └─► if last update > 6h AND new daily content:         ║
║                       spawn update.py (detached) ─► EDITS CLAUDE.md    ║
║                                                    + docs/ in REPO ROOT║
║    Manual:  /neurawork-cc-harness:cl-update  ─► update.py --all        ║
║                                                                        ║
║  DATA: daily/ lives in <repo>/<ldir>/; CLAUDE.md + docs/ live at the   ║
║        REPO ROOT (the files the agent already reads). NEVER .claude/.  ║
║  VALUE: self-maintaining CLAUDE.md hierarchy + docs/; brownfield seed. ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| `/neurawork-cc-harness:claudemd-lerner` | n/a | recon→ask→install (+seed) | One-command per-repo install |
| `/neurawork-cc-harness:cl-update` | n/a | manual CLAUDE.md/docs update now | On-demand doc refresh |
| SessionStart | (kc injects wiki index) | also injects current CLAUDE.md + docs/ list; 6h-gated update spawn | Fresh doc context; timely auto-maintenance |
| SessionEnd/PreCompact | (kc captures to its daily/) | lerner captures to ITS daily/ (separate cl- hooks) | Both skills coexist without clobbering |
| repo-root `CLAUDE.md` + `docs/` | drift by hand | edited in place by update/seed agent | Docs stay current automatically |

---

## Mandatory Reading

**CRITICAL — read before any task. This skill is a MIRROR of the completed Phase-2 `knowledge-compiler`. Copy its structure file-for-file, then apply the deltas in the "Naming & Behavior Map" and per-task notes. The Phase-2 files ARE our own first-party code — reuse their shape directly.**

| Priority | File | Lines | Why Read This (what to MIRROR) |
|----------|------|-------|--------------------------------|
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py` | 1-161 | Install design to mirror: path consts, `_is_adopt`, `_copy_code`, `_scaffold`, `_hooks`, `main()`, `--seed`. Adapt `_scaffold` (no `knowledge/`), `_hooks` (cl- filenames + markers), args (`--lerner-dir`). |
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/compile.py` | 1-196 | The template for `update.py`: prompt build, SDK options, `_select` change-detection, `state["ingested"]` hashing, `_stamp_last_*`. Delta: edits CLAUDE.md/docs instead of writing `knowledge/`; no `--file` wiki semantics. |
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/flush.py` | 1-194 | Mirror almost verbatim — only the env var name (`KNOWLEDGE_ROOT`→`LERNER_ROOT`) and the distillation `PROMPT` (doc-relevant) change. |
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/hooks/session-end.py` | 1-70 | Mirror; rename env var to `LERNER_ROOT`; file becomes `cl-session-end.py`. |
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/hooks/session-start.py` | 1-123 | Mirror; `build_context()` injects root CLAUDE.md + docs/ listing (not wiki index); `maybe_spawn_*` calls `update.py`; lock `cl-update.lock`. |
| P0 | `plugins/neurawork-cc-harness/engines/_shared/settings.py` | 57-75 | **Collision root cause.** `merge_hooks` matches first hook whose command CONTAINS the marker. cl- filenames make lerner markers non-substrings of kc commands → no clobber. |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/hooks/pre-compact.py` | 1-70 | Mirror; `MIN_TURNS_TO_FLUSH=5`; `cl-pre-compact.py`; `LERNER_ROOT`. |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/config.py` | 1-68 | Path-constant + `load_cfg` pattern. Delta: drop wiki paths; add `CLAUDEMD_FILE`, `DOCS_DIR`, `REPO_ROOT`; env var `LERNER_ROOT`; keys `lerner_dir`/`update_age_hours`/`claudemd_depth`/`docs_dir`/`language`/`excluded_dirs`. |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/utils.py` | 26-50, 143-163 | Keep `load_state`/`save_state`/`file_hash`/`list_raw_files`; rename `should_compile`→`should_update`; DROP all wiki helpers (wikilinks, index, article listing). |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/seed.py` | 1-142 | Mirror; `_repo_context` reuse; target = root CLAUDE.md + docs/ (not `knowledge/`); `_stamp_last_update`. |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/seed_prompt.txt` | 1-23 | Template for the lerner seed prompt — rewrite to produce a CLAUDE.md hierarchy + docs/, UPDATE existing CLAUDE.md. |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/AGENTS.md` | 1-233 | Template for the lerner constitution — rewrite for CLAUDE.md/docs maintenance (no wiki/wikilinks). |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/recon.py` | 1-115 | Mirror; add CLAUDE.md-depth/docs/language/excluded-dirs detection; `_find_existing_ldir` keys on `hooks/cl-session-end.py`. |
| P1 | `plugins/neurawork-cc-harness/skills/knowledge-compiler/SKILL.md` | 1-61 | Template for the install skill — same 3-phase shape; adapt questions, FQN note, auth note. |
| P1 | `plugins/neurawork-cc-harness/commands/kc-compile.md` | 1-25 | Template for `cl-update.md`. |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/tests/test_install_recon.py` | 1-106 | Test pattern: temp git repo, subprocess install/recon, assert scaffold + hooks + RECON_JSON. Add a both-skills coexistence test. |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/tests/test_utils_trigger.py` | 1-79 | Test pattern for `should_update` truth table + helpers. |
| P0 | `plugins/neurawork-cc-harness/engines/_shared/*.py` | all | Reuse directly (do not copy/modify): `hookio`, `transcript`, `gitctx`, `settings`, `repo_guard`, `recon`. `repo_guard.py:5-9` already names `claudemd-lerner (CLAUDE.md, docs/)` as a consumer. |

**Phase-1 `_shared` public API (import directly — our own code, unchanged):**
- `hookio.recursion_guard()`, `hookio.read_hook_input() -> dict`, `hookio.child_env() -> dict` (sets `CLAUDE_INVOKED_BY="neurawork_cc_harness"`)
- `transcript.extract_turns(path, max_turns=30, max_chars=15000) -> str`
- `gitctx.repo_root(start=None)`, `gitctx.in_worktree(start=None)`, `gitctx.main_checkout_root(start=None)`
- `settings.merge_hooks(repo_root, [(event, command, timeout, marker), ...]) -> bool`, `settings.SettingsError`
- `repo_guard.assert_in_repo_not_dotclaude(target, repo_root) -> Path`, `repo_guard.safe_join(...)`, `repo_guard.WriteGuardError`
- `recon.git_root_or_none(start=None) -> str|None`, `recon.emit_recon_json(info: dict)`, `recon.parse_recon_json(stdout) -> dict|None`, `recon.RECON_DELIMITER`

**External Documentation:**
| Source | Section | Why |
|--------|---------|-----|
| [claude-agent-sdk PyPI](https://pypi.org/project/claude-agent-sdk/) (v0.2.104, Jun 2026) | version | dep `>=0.2.96` — identical to Phase 2 (`payload/pyproject.toml`) |
| [Track cost and usage](https://code.claude.com/docs/en/agent-sdk/cost-tracking) | `ResultMessage.total_cost_usd` | correct cost field (NOT `cost_usd`) |
| [Agent SDK overview — auth](https://code.claude.com/docs/en/agent-sdk/overview) | API key auth | public plugin → `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN`; subscription creds NOT sanctioned for third-party |
| [Python SDK reference](https://code.claude.com/docs/en/agent-sdk/python) | `setting_sources`, `strict_mcp_config` | isolate hook-spawned SDK calls from inherited `.claude/` settings (mirror Phase 2 calls) |

---

## Naming & Behavior Map (knowledge-compiler → claudemd-lerner)

| knowledge-compiler | claudemd-lerner | Note |
|---|---|---|
| `engines/knowledge-compiler/` | `engines/claudemd-lerner/` | |
| `skills/knowledge-compiler/SKILL.md` | `skills/claudemd-lerner/SKILL.md` | |
| `commands/kc-compile.md` | `commands/cl-update.md` | |
| `--knowledge-dir` (default `knowledge-base`) | `--lerner-dir` (default `claudemd-lerner`) | the ldir holds ONLY machinery (no user content) |
| `knowledge_dir` config key | `lerner_dir` | |
| `compile_age_hours` (6) | `update_age_hours` (6) | |
| `KNOWLEDGE_ROOT` env var | `LERNER_ROOT` env var | **must differ** so both skills' hooks point at their own ldir |
| `hooks/session-start.py` | `hooks/cl-session-start.py` | **cl- prefix = marker uniqueness** |
| `hooks/session-end.py` | `hooks/cl-session-end.py` | |
| `hooks/pre-compact.py` | `hooks/cl-pre-compact.py` | |
| hook markers `hooks/session-end.py`… | markers `hooks/cl-session-end.py`… | not substrings of kc commands (and vice-versa) |
| `scripts/compile.py` | `scripts/update.py` | edits CLAUDE.md/docs, not `knowledge/` |
| `kc-compile.lock` | `cl-update.lock` | |
| `last-compile.json` | `last-update.json` | the 6h-gate stamp |
| `_stamp_last_compile()` | `_stamp_last_update()` | |
| `maybe_spawn_compile()` | `maybe_spawn_update()` | |
| `LAST_COMPILE_FILE` | `LAST_UPDATE_FILE` | |
| `should_compile(...)` | `should_update(...)` | identical 6-arg pure gate |
| `neurawork-knowledge` (pyproject name) | `neurawork-claudemd-lerner` | |
| `<kdir>/daily/` (session logs) | `<ldir>/daily/` (session logs) | **kept** — same capture/incremental model |
| `<kdir>/knowledge/{concepts,connections,index.md,log.md}` | **NONE** | write targets move to repo root |
| (writes inside kdir) | repo-root `CLAUDE.md`, depth-N `<subdir>/CLAUDE.md`, `<docs_dir>/*.md` | the files the agent already reads |
| `scripts/query.py`, `scripts/lint.py` | **NONE** | no wiki to query/lint (out of scope) |
| `_is_adopt`: `hooks/session-end.py`+`scripts/flush.py` | `hooks/cl-session-end.py`+`scripts/flush.py` | |
| `test_install_recon.py`, `test_utils_trigger.py` | same names, adapted assertions + a coexistence test | |

**New config keys (recon-driven), in `config.default.json` + `<ldir>/config.json`:**
```json
{
  "lerner_dir": "claudemd-lerner",
  "model": "",
  "update_age_hours": 6,
  "claudemd_depth": 1,
  "docs_dir": "docs",
  "language": "en",
  "excluded_dirs": ["node_modules", ".venv", "dist", "build", ".git"]
}
```
- `claudemd_depth`: `1` = root `CLAUDE.md` only; `2` = root + immediate subdirs; etc. Bounds how deep the update/seed agent maintains CLAUDE.md files.
- `docs_dir`: where longer-form docs live (relative to repo root).
- `language`: prose language for generated docs (`en`/`de`).
- `excluded_dirs`: dirs the agent must ignore when scanning/seeding.

---

## Patterns to Mirror

These are ACTUAL Phase-2 snippets (our own first-party code). Reproduce the shape; apply the documented deltas.

**INSTALL — path consts + `_shared` wiring** (SOURCE: `engines/knowledge-compiler/install.py:21-31`):
```python
ENGINE_DIR = Path(__file__).resolve().parent
PAYLOAD = ENGINE_DIR / "payload"
SHARED_SRC = ENGINE_DIR.parent / "_shared"
DEFAULTS_FILE = ENGINE_DIR / "config.default.json"
VERSION_FILE = ENGINE_DIR / "VERSION"

sys.path.insert(0, str(ENGINE_DIR.parent))  # engines/ for _shared

from _shared.recon import git_root_or_none
from _shared.settings import merge_hooks
from _shared.repo_guard import assert_in_repo_not_dotclaude, WriteGuardError
```

**INSTALL — hook registration (THE COLLISION FIX)** (SOURCE: `engines/knowledge-compiler/install.py:101-107`). cl- filenames give unique markers:
```python
def _hooks(ldir: str) -> list[tuple[str, str, int, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{ldir}" python'
    return [
        ("SessionStart", f"{base} hooks/cl-session-start.py", 15, "hooks/cl-session-start.py"),
        ("PreCompact",   f"{base} hooks/cl-pre-compact.py",   10, "hooks/cl-pre-compact.py"),
        ("SessionEnd",   f"{base} hooks/cl-session-end.py",   10, "hooks/cl-session-end.py"),
    ]
```

**INSTALL — `_scaffold` (no knowledge/ tree)** (ADAPTED from `install.py:80-98`):
```python
def _scaffold(target: Path, ldir: str) -> None:
    """Create data dirs/files only if absent (never clobber)."""
    (target / "daily").mkdir(parents=True, exist_ok=True)
    (target / "scripts").mkdir(parents=True, exist_ok=True)
    config = target / "config.json"
    if not config.exists():
        defaults = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
        defaults["lerner_dir"] = ldir
        config.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE, encoding="utf-8")
    shutil.copy2(VERSION_FILE, target / "VERSION")
```
> Note: NO `knowledge/index.md` seed. The root `CLAUDE.md` already exists (or `seed.py` creates it). `_copy_code` is identical to `install.py:64-77`.

**CONFIG — env-overridable root + repo-root targets** (ADAPTED from `config.py:19-44`):
```python
ROOT_DIR = Path(os.environ.get("LERNER_ROOT") or Path(__file__).resolve().parent.parent)
DAILY_DIR = ROOT_DIR / "daily"
SCRIPTS_DIR = ROOT_DIR / "scripts"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"
CONFIG_FILE = ROOT_DIR / "config.json"
STATE_FILE = SCRIPTS_DIR / "state.json"
LAST_UPDATE_FILE = SCRIPTS_DIR / "last-update.json"
LOCK_FILE = SCRIPTS_DIR / "cl-update.lock"
REPO_ROOT = ROOT_DIR.parent                       # CLAUDE.md/docs live here
CLAUDEMD_FILE = REPO_ROOT / "CLAUDE.md"

DEFAULT_CFG = {
    "lerner_dir": "claudemd-lerner",
    "model": "",
    "update_age_hours": 6,
    "claudemd_depth": 1,
    "docs_dir": "docs",
    "language": "en",
    "excluded_dirs": ["node_modules", ".venv", "dist", "build", ".git"],
}

def docs_dir() -> Path:
    return REPO_ROOT / str(load_cfg().get("docs_dir", "docs"))
```
> `load_cfg`, `now_iso`, `today_iso` copied verbatim from `config.py:47-67`.

**PURE 6h GATE** (SOURCE: `utils.py:145-163`; rename only):
```python
def should_update(now, last_ts, age_hours, has_new_daily, in_wt, lock_fresh) -> bool:
    if in_wt or lock_fresh or not has_new_daily:
        return False
    if last_ts is None:
        return True
    return (now - last_ts) >= age_hours * 3600
```

**SESSION-START — inject CLAUDE.md/docs (not wiki index)** (ADAPTED from `session-start.py:53-64`):
```python
def build_context() -> str:
    today = datetime.now(timezone.utc).astimezone()
    parts = [f"## Today\n{today.strftime('%A, %B %d, %Y')}"]
    if CLAUDEMD_FILE.exists():
        parts.append(f"## Project CLAUDE.md\n\n{CLAUDEMD_FILE.read_text(encoding='utf-8')}")
    else:
        parts.append("## Project CLAUDE.md\n\n(none yet — run seed or let the learner build it)")
    docs = docs_dir()
    if docs.is_dir():
        listing = "\n".join(sorted(str(p.relative_to(REPO_ROOT)) for p in docs.rglob("*.md"))[:50])
        parts.append(f"## docs/ files\n\n{listing or '(none)'}")
    parts.append(f"## Recent Daily Log\n\n{_recent_daily()}")
    context = "\n\n---\n\n".join(parts)
    return context[:MAX_CONTEXT_CHARS] + ("\n\n...(truncated)" if len(context) > MAX_CONTEXT_CHARS else "")
```
> `_recent_daily`, `_last_update_ts` (from `LAST_UPDATE_FILE`), `_newest_daily_mtime`, `maybe_spawn_update` (→ `scripts/update.py --all`, `cl-update.lock`), and `main()` mirror `session-start.py:42-118` exactly (rename compile→update; spawn gate is main-checkout-only).

**SDK QUERY (update) — editor agent** (SOURCE: `compile.py:97-127`; same options):
```python
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
async for message in query(prompt=_build_prompt(log_path), options=ClaudeAgentOptions(
        cwd=str(REPO_ROOT),                 # agent edits CLAUDE.md/docs at repo root
        system_prompt={"type": "preset", "preset": "claude_code"},
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=30,
        setting_sources=[],
        strict_mcp_config=True,
        model=(cfg.get("model") or None),
)):
    if isinstance(message, ResultMessage):
        cost = message.total_cost_usd or 0.0
```

**SDK QUERY (flush) — text-only** (SOURCE: `flush.py:121-130`): identical options (`allowed_tools=[]`, `max_turns=2`, isolation, model). Only the `PROMPT` text changes to extract doc-relevant insights.

**CAPTURE HOOK entrypoint** (SOURCE: `session-end.py:15-26`, `61`): mirror exactly; only the env var differs:
```python
KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))
from _shared.hookio import recursion_guard, read_hook_input, child_env
recursion_guard()
from _shared.transcript import extract_turns
from _shared.gitctx import in_worktree, main_checkout_root
...
env = {**child_env(), "LERNER_ROOT": str(root)}   # was KNOWLEDGE_ROOT
```

**WRITE-GUARD on doc targets** (SOURCE: `seed.py:69-74`): guard the repo-root targets before the agent runs:
```python
from _shared.repo_guard import assert_in_repo_not_dotclaude, WriteGuardError
assert_in_repo_not_dotclaude(CLAUDEMD_FILE, REPO_ROOT)   # raises if under .claude/
assert_in_repo_not_dotclaude(docs_dir(), REPO_ROOT)
```

**TEST harness** (SOURCE: `tests/test_install_recon.py:27-44`): unittest + tempfile + real git, `@unittest.skipUnless(shutil.which("git"), ...)`, subprocess with `sys.executable`.

---

## Files to Change

Paths relative to plugin root `plugins/neurawork-cc-harness/`. Every file is **written fresh** by mirroring the named Phase-2 file. `plugin.json` already references `claudemd-lerner` — no change. `engines/_shared/` is reused unchanged.

| File | Action | Justification |
|------|--------|---------------|
| `engines/claudemd-lerner/VERSION` | CREATE | engine version stamp (`1`) |
| `engines/claudemd-lerner/config.default.json` | CREATE | new keys: `lerner_dir`, `model`, `update_age_hours`, `claudemd_depth`, `docs_dir`, `language`, `excluded_dirs` |
| `engines/claudemd-lerner/recon.py` | CREATE | mirror kc recon; add depth/docs/language/excluded detection; detect existing ldir via `hooks/cl-session-end.py` |
| `engines/claudemd-lerner/install.py` | CREATE | mirror kc install; `_scaffold` (no knowledge/); cl- hooks/markers; `--lerner-dir`; optional seed |
| `engines/claudemd-lerner/payload/pyproject.toml` | CREATE | name `neurawork-claudemd-lerner`; same deps as kc |
| `engines/claudemd-lerner/payload/AGENTS.md` | CREATE | NEW constitution: CLAUDE.md hierarchy + docs/ maintenance rules (no wiki) |
| `engines/claudemd-lerner/payload/scripts/config.py` | CREATE | path consts (repo-root targets); `LERNER_ROOT`; new config keys; `load_cfg`/`now_iso`/`today_iso` |
| `engines/claudemd-lerner/payload/scripts/utils.py` | CREATE | `load_state`/`save_state`/`file_hash`/`list_raw_files`/`should_update`; no wiki helpers |
| `engines/claudemd-lerner/payload/scripts/flush.py` | CREATE | mirror kc flush; `LERNER_ROOT`; doc-relevant `PROMPT`; appends `daily/<date>.md` |
| `engines/claudemd-lerner/payload/scripts/update.py` | CREATE | replaces compile.py: SDK editor over CLAUDE.md/docs; change-detection; `last-update.json` stamp |
| `engines/claudemd-lerner/payload/scripts/seed.py` | CREATE | brownfield seed → CLAUDE.md tree + docs/; UPDATE existing CLAUDE.md; `_stamp_last_update` |
| `engines/claudemd-lerner/payload/scripts/seed_prompt.txt` | CREATE | seed agent instructions (CLAUDE.md + docs/, respect depth/language/excluded) |
| `engines/claudemd-lerner/payload/hooks/cl-session-end.py` | CREATE | mirror kc; `LERNER_ROOT`; cl- name |
| `engines/claudemd-lerner/payload/hooks/cl-pre-compact.py` | CREATE | mirror kc; `MIN_TURNS_TO_FLUSH=5`; cl- name |
| `engines/claudemd-lerner/payload/hooks/cl-session-start.py` | CREATE | inject CLAUDE.md+docs; 6h-gated `update.py` spawn; `cl-update.lock` |
| `skills/claudemd-lerner/SKILL.md` | CREATE | 3-phase install; FQN/collision note; auth note |
| `commands/cl-update.md` | CREATE | manual update slash-command |
| `engines/claudemd-lerner/tests/__init__.py` | CREATE | test package marker |
| `engines/claudemd-lerner/tests/test_install_recon.py` | CREATE | install/recon + **both-skills coexistence** (no clobber) |
| `engines/claudemd-lerner/tests/test_utils_trigger.py` | CREATE | `should_update` truth table + helpers |

---

## NOT Building (Scope Limits)

- **No knowledge wiki** — no `knowledge/`, `concepts/`, `connections/`, `index.md`, wikilinks, `query.py`, or `lint.py`. That is the Phase-2 skill; lerner only maintains CLAUDE.md + docs/.
- **No changes to `engines/_shared/` or `plugin.json`** — both already support this skill (`repo_guard.py` already names it; `plugin.json` already describes it).
- **No git-diff capture in v1** — capture mirrors Phase-2 (transcript turns only). The update agent grounds edits in the live repo via Read/Glob/Grep. Adding a `git diff` summary to the captured context is a documented future refinement (see Notes), not in scope here.
- **No shared `daily/` between the two skills** — PRD default is separate stores (each independently installable). Lerner keeps its own `<ldir>/daily/`.
- **No LLM-call unit tests** — flush/update/seed are validated by manual smoke with real auth; only non-LLM logic (install, recon, utils, gate, collision-safety) is unit-tested.
- **No global store** — daily lives in `<repo>/<ldir>/`; CLAUDE.md/docs at repo root; never `.claude/`.
- **Validators (Phases 5–6)** — Session 2.

---

## Step-by-Step Tasks

Execute in order. Each is atomic and verifiable. "MIRROR" = copy the structure of the named Phase-2 file, then apply the listed deltas. All `<plugin>` paths are under `plugins/neurawork-cc-harness/`. Run validation from the plugin root.

### Task 1: CREATE `engines/claudemd-lerner/VERSION`
- **IMPLEMENT**: single line `1`
- **MIRROR**: `engines/knowledge-compiler/VERSION`
- **VALIDATE**: `test -f engines/claudemd-lerner/VERSION`

### Task 2: CREATE `engines/claudemd-lerner/config.default.json`
- **IMPLEMENT**: the 7-key object from "New config keys" above (`lerner_dir`, `model`, `update_age_hours`, `claudemd_depth`, `docs_dir`, `language`, `excluded_dirs`)
- **MIRROR**: `engines/knowledge-compiler/config.default.json`
- **VALIDATE**: `python3 -c "import json;json.load(open('engines/claudemd-lerner/config.default.json'))"`

### Task 3: CREATE `engines/claudemd-lerner/payload/pyproject.toml`
- **IMPLEMENT**: `name="neurawork-claudemd-lerner"`, `requires-python=">=3.12"`, deps `claude-agent-sdk>=0.2.96`, `python-dotenv>=1.0.0`, `tzdata>=2024.1`
- **MIRROR**: `engines/knowledge-compiler/payload/pyproject.toml`
- **GOTCHA**: SDK lower bound `>=0.2.96` (mcp<2.0.0 pin)
- **VALIDATE**: `python3 -c "import tomllib;tomllib.load(open('engines/claudemd-lerner/payload/pyproject.toml','rb'))"`

### Task 4: CREATE `engines/claudemd-lerner/payload/AGENTS.md`
- **ACTION**: write a NEW constitution (no wiki concepts)
- **IMPLEMENT**: sections covering — (a) the model: sessions → `daily/` logs → the learner edits CLAUDE.md/docs; (b) **what goes where**: root `CLAUDE.md` = build/test/lint commands, high-level architecture, repo-wide conventions, key decisions; subdir `<area>/CLAUDE.md` (only up to `claudemd_depth`) = area-specific notes; `docs/*.md` = longer-form guides/design docs; (c) the daily-log format (copy kc's `## Sessions` / `### Session (HH:MM)` shape so flush output is consistent); (d) **update rules**: prefer surgical Edit over rewrite; keep existing structure/headings; respect `claudemd_depth`, `docs_dir`, `language`, `excluded_dirs`; never invent facts — ground every change in the daily log or the live repo; **never write under `.claude/`**; (e) conventions: ISO dates, factual neutral prose
- **MIRROR**: structure/length of `engines/knowledge-compiler/payload/AGENTS.md` (drop article/wikilink/no-RAG sections)
- **GOTCHA**: this text is fed to the update + seed LLM — it must fully define the CLAUDE.md/docs contract since there is no wiki schema to lean on
- **VALIDATE**: file present with `##` sections for CLAUDE.md layout + update rules; `grep -L "knowledge/\|wikilink\|\[\[" engines/claudemd-lerner/payload/AGENTS.md` (no wiki leftovers)

### Task 5: CREATE `engines/claudemd-lerner/payload/scripts/config.py`
- **IMPLEMENT**: `ROOT_DIR` honoring `LERNER_ROOT`; `DAILY_DIR`, `SCRIPTS_DIR`, `AGENTS_FILE`, `CONFIG_FILE`, `STATE_FILE`, `LAST_UPDATE_FILE`, `LOCK_FILE` (= `cl-update.lock`), `REPO_ROOT = ROOT_DIR.parent`, `CLAUDEMD_FILE = REPO_ROOT/"CLAUDE.md"`, `docs_dir()` helper; `DEFAULT_CFG` (7 keys); `load_cfg()`, `now_iso()`, `today_iso()` verbatim from kc
- **MIRROR**: `engines/knowledge-compiler/payload/scripts/config.py:19-67`
- **GOTCHA**: NO hardcoded timezone; NO wiki path constants
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/scripts/config.py`

### Task 6: CREATE `engines/claudemd-lerner/payload/scripts/utils.py`
- **IMPLEMENT**: `load_state()` (skeleton `{"ingested":{},"updated_count":0,"total_cost":0.0}`), `save_state()` (atomic tmp+os.replace), `file_hash()` (sha256[:16]), `list_raw_files()` (sorted `DAILY_DIR.glob("*.md")`), `should_update(now,last_ts,age_hours,has_new_daily,in_wt,lock_fresh)` (the pure gate)
- **MIRROR**: `engines/knowledge-compiler/payload/scripts/utils.py:26-50,107-111,145-163`
- **GOTCHA**: import only the config constants that exist here (no `INDEX_FILE`/`KNOWLEDGE_DIR`); drop ALL wiki helpers
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/scripts/utils.py`

### Task 7: CREATE `engines/claudemd-lerner/payload/scripts/flush.py`
- **IMPLEMENT**: set `CLAUDE_INVOKED_BY` before SDK import; resolve `ROOT` via `LERNER_ROOT`; 60s dedup (`last-flush.json`); `PROMPT` distils the session into a daily entry emphasizing **doc-relevant** signal (conventions established, architecture/decisions, commands, gotchas, anything that should land in CLAUDE.md/docs); return `FLUSH_OK` if nothing worth saving; `query()` text-only (`allowed_tools=[]`, `max_turns=2`, isolation, `model` from cfg); `append_to_daily()` guarded via `assert_in_repo_not_dotclaude`
- **MIRROR**: `engines/knowledge-compiler/payload/scripts/flush.py` (near-verbatim)
- **GOTCHA**: env var is `LERNER_ROOT`; do NOT trigger an update from flush (update is gated by SessionStart/manual)
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/scripts/flush.py`

### Task 8: CREATE `engines/claudemd-lerner/payload/scripts/update.py`
- **ACTION**: the editor agent (replaces compile.py)
- **IMPLEMENT**: `_build_prompt(log_path)` = AGENTS.md + current root `CLAUDE.md` (if any) + a listing of existing subdir `CLAUDE.md` files (bounded by `claudemd_depth`, excluding `excluded_dirs`) + `docs/` listing + the daily log; task = "apply what this session implies to the CLAUDE.md hierarchy and docs/, surgically; respect depth/language/excluded; never touch `.claude/`". `query()` with `cwd=REPO_ROOT`, `[Read,Write,Edit,Glob,Grep]`, `permission_mode="acceptEdits"`, `max_turns=30`, isolation, `model`; CLI `--all`/`--dry-run`; `_select` by SHA-256[:16] vs `state["ingested"]`; record `{hash, updated_at, cost_usd}`; **`_stamp_last_update()` writes `last-update.json` `{"ts": <float>}` atomically on success** (the SessionStart gate contract); pre-flight `assert_in_repo_not_dotclaude(CLAUDEMD_FILE, REPO_ROOT)`
- **MIRROR**: `engines/knowledge-compiler/payload/scripts/compile.py` (prompt, `_select`, state, stamp, `main`)
- **GOTCHA**: `cwd=REPO_ROOT` (not the ldir) so the agent edits the real CLAUDE.md/docs; no `--file` wiki semantics needed (keep `--all`/`--dry-run` only)
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/scripts/update.py`

### Task 9: CREATE `engines/claudemd-lerner/payload/scripts/seed_prompt.txt`
- **IMPLEMENT**: instruct the agent to (1) read README + existing CLAUDE.md (root + any subdir) + `docs/` + top-level source map, ignoring `excluded_dirs`; (2) produce/UPDATE the root `CLAUDE.md` (purpose, build/test/lint commands, architecture, conventions, key decisions) and, up to `claudemd_depth`, area `CLAUDE.md` files; (3) create/refresh `docs/` entries for longer-form material; write in `language`. Hard constraints: write ONLY CLAUDE.md files + under `docs_dir`; never under `.claude/`; UPDATE existing CLAUDE.md rather than clobbering; ground every statement in files read — no invention
- **MIRROR**: `engines/knowledge-compiler/payload/scripts/seed_prompt.txt`
- **VALIDATE**: file present, non-empty; `grep -i "claude.md" engines/claudemd-lerner/payload/scripts/seed_prompt.txt`

### Task 10: CREATE `engines/claudemd-lerner/payload/scripts/seed.py`
- **IMPLEMENT**: precondition — git repo + working tree clean **except** the ldir (reuse `_dirty_outside_kdir` shape keyed on `ROOT_DIR.name`); `_repo_context(root)` (README + existing CLAUDE.md files + docs/ listing + top-level map, honoring excluded_dirs); prompt = seed_prompt.txt + AGENTS.md + repo context + `claudemd_depth`/`docs_dir`/`language` directives; FOREGROUND `query()` with `cwd=root`, `[Read,Write,Edit,Glob,Grep]`, `acceptEdits`, `max_turns≈40`, isolation, `model`; guard targets via `assert_in_repo_not_dotclaude`; `_stamp_last_update()` on success
- **MIRROR**: `engines/knowledge-compiler/payload/scripts/seed.py`
- **GOTCHA**: this repo already HAS a root CLAUDE.md — seed must UPDATE, not overwrite; confine writes to CLAUDE.md files + docs_dir
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/scripts/seed.py`

### Task 11: CREATE `engines/claudemd-lerner/payload/hooks/cl-session-end.py`
- **IMPLEMENT**: `recursion_guard()`; `read_hook_input()` → session_id/transcript_path; skip if no transcript; `extract_turns()` → write context under `scripts/`; Popen `uv run --directory <root> python scripts/flush.py <ctx> <session_id>` with `env={**child_env(), "LERNER_ROOT": str(root)}`; worktree redirect via `main_checkout_root()/KDIR.name`
- **MIRROR**: `engines/knowledge-compiler/payload/hooks/session-end.py` (`MIN_TURNS_TO_FLUSH=1`, prefix `session-flush-`)
- **GOTCHA**: filename MUST be `cl-session-end.py` (marker uniqueness); env var `LERNER_ROOT`
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/hooks/cl-session-end.py`

### Task 12: CREATE `engines/claudemd-lerner/payload/hooks/cl-pre-compact.py`
- **IMPLEMENT**: same as Task 11 with `MIN_TURNS_TO_FLUSH=5`, prefix `flush-context-`, log tag `[cl-pre-compact]`
- **MIRROR**: `engines/knowledge-compiler/payload/hooks/pre-compact.py`
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/hooks/cl-pre-compact.py`

### Task 13: CREATE `engines/claudemd-lerner/payload/hooks/cl-session-start.py`
- **IMPLEMENT**: `recursion_guard()`; if `repo_root()` and not `in_worktree()`: `maybe_spawn_update(update_age_hours)` → read `LAST_UPDATE_FILE` ts, newest daily mtime, `cl-update.lock` freshness, `should_update(...)` → Popen detached `uv run --directory <ldir> python scripts/update.py --all` (`start_new_session=True`, `env=child_env()`, DEVNULL), then write `cl-update.lock`; always print `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext": build_context()}}` where `build_context()` injects root CLAUDE.md + docs/ listing + recent daily (per the snippet above)
- **MIRROR**: `engines/knowledge-compiler/payload/hooks/session-start.py`
- **GOTCHA**: Popen returns immediately; print JSON after; never block the 15s hook; worktree → inject-only
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/payload/hooks/cl-session-start.py`

### Task 14: CREATE `engines/claudemd-lerner/recon.py`
- **IMPLEMENT**: `git_root_or_none()` (NOT_A_GIT_REPO path); branch/clean; `_find_existing_ldir()` keyed on `hooks/cl-session-end.py` + `scripts/flush.py`; `_existing_hooks()` keyed on the cl- markers; detect `has_root_claudemd`, `claudemd_count` (number of CLAUDE.md files found, depth hint), `has_docs`, suggested `language` (best-effort from README/existing CLAUDE.md, else "en"), suggested `excluded_dirs` (those present among the defaults), tz; `seed_recommended = existing_ldir is None and (has_readme or has_docs or has_root_claudemd)`; `emit_recon_json(info)`
- **MIRROR**: `engines/knowledge-compiler/recon.py`
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/recon.py`

### Task 15: CREATE `engines/claudemd-lerner/install.py`
- **IMPLEMENT**: `_is_adopt` (cl- detection); `_copy_code` (hooks/*.py incl. cl- names, scripts/*.py+*.txt, pyproject.toml, AGENTS.md, `_shared/`); `_scaffold` (daily/ + scripts/ + config.json + .gitignore + VERSION — NO knowledge/); `_hooks(ldir)` (cl- commands + markers); `merge_hooks`; CLI `--lerner-dir` (default `claudemd-lerner`), `--seed`; guard ldir via `assert_in_repo_not_dotclaude`; print `uv sync` + commit guidance
- **MIRROR**: `engines/knowledge-compiler/install.py`
- **GOTCHA**: `GITIGNORE` drops `knowledge/log.md`; keeps `daily/`, `scripts/state.json`, `scripts/last-update.json`, `scripts/last-flush.json`, `scripts/cl-update.lock`, `scripts/*.log`, `scripts/session-flush-*.md`, `scripts/flush-context-*.md`. ADOPT must not clobber `daily/`.
- **VALIDATE**: `python3 -m py_compile engines/claudemd-lerner/install.py`

### Task 16: CREATE `skills/claudemd-lerner/SKILL.md`
- **IMPLEMENT**: frontmatter `name: claudemd-lerner` + trigger-rich `description` (e.g. "claudemd lerner", "install claudemd lerner", "keep CLAUDE.md current", "update my project docs automatically", "CLAUDE.md aktuell halten"). Phase A recon (`python3 "${CLAUDE_PLUGIN_ROOT}/engines/claudemd-lerner/recon.py"`). Phase B AskUserQuestion: lerner dir (default `claudemd-lerner`/detected), CLAUDE.md depth (default 1), docs dir (default `docs`), language (confirm detected), excluded dirs (confirm suggested), timezone, seed? (offer when `seed_recommended` and clean). Phase C `install.py --lerner-dir <NAME> [--seed]` then `uv sync --directory <NAME>`. Auth note (`ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN`; subscription creds not sanctioned for third-party). FQN note: `claudemd-lerner` is collision-free as a name, but always invoke as `neurawork-cc-harness:claudemd-lerner`; mention it coexists with `knowledge-compiler` (separate cl- hooks).
- **MIRROR**: `skills/knowledge-compiler/SKILL.md`
- **VALIDATE**: YAML frontmatter parses; plugin-validator (Task 19)

### Task 17: CREATE `commands/cl-update.md`
- **IMPLEMENT**: frontmatter `description` + `argument-hint: "[--all|--dry-run]"`; body locates the ldir (dir containing `scripts/update.py` + `hooks/cl-session-end.py`), else tells the user to install via `/neurawork-cc-harness:claudemd-lerner`; runs `uv run --directory <ldir> python scripts/update.py $ARGUMENTS`; reports what changed + cost
- **MIRROR**: `commands/kc-compile.md`
- **VALIDATE**: file present; frontmatter parses

### Task 18: CREATE unit tests (non-LLM)
- **IMPLEMENT**: `tests/__init__.py`; `tests/test_install_recon.py` and `tests/test_utils_trigger.py`
  - install/recon: temp git repo → install FRESH (`--lerner-dir lc`) → assert `lc/daily/` dir, `lc/scripts/update.py`, `lc/hooks/cl-session-start.py`, `lc/_shared/hookio.py`, `lc/config.json`, `lc/.gitignore`, and that **no `lc/knowledge/`** exists; 3 hooks merged under SessionStart/PreCompact/SessionEnd; re-install idempotent (a hand-added `daily/keep.md` survives ADOPT; no duplicate hook entry); recon emits parseable RECON_JSON with `status=="OK"`, `existing_ldir is None`, `seed_recommended is True` when a README exists
  - **COEXISTENCE (the collision fix)**: in one temp repo run BOTH installers — first `engines/knowledge-compiler/install.py --knowledge-dir kb`, then `engines/claudemd-lerner/install.py --lerner-dir lc` — and assert the resulting `.claude/settings.json` has **two** distinct hook entries per event (one containing `kb`/`hooks/session-end.py`, one containing `lc`/`hooks/cl-session-end.py`); neither command was overwritten
  - utils/trigger: `file_hash` stable+16-char; `should_update` truth table (fresh→no, stale+new→yes, no-new-daily→no, worktree→no, lock-fresh→no, missing-stamp+new→yes, missing-stamp+no-daily→no)
- **MIRROR**: `engines/knowledge-compiler/tests/test_install_recon.py` + `test_utils_trigger.py`
- **VALIDATE**: `python3 -m unittest discover -s engines/claudemd-lerner/tests -v`

### Task 19: VALIDATE plugin + manual smoke
- **IMPLEMENT**: run `plugin-dev:plugin-validator`; document manual SDK smoke (requires `ANTHROPIC_API_KEY`): install into a throwaway repo with a README, `uv sync`, fabricate `lc/daily/<today>.md` describing a convention, `update.py --all` → root `CLAUDE.md` gains/updates a section + `lc/scripts/last-update.json` written; `seed.py` on a small repo → CLAUDE.md (+ docs/) created/updated; new session SessionStart injects CLAUDE.md
- **VALIDATE**: validator clean; smoke documented in the report (gated on auth)

---

## Testing Strategy

### Unit Tests to Write (non-LLM)
| Test File | Cases | Validates |
|-----------|-------|-----------|
| `tests/test_install_recon.py` | FRESH scaffold (no knowledge/), idempotent ADOPT, `_shared` copied, cl- hooks merged, recon JSON, **both-skills coexistence** | install.py + recon.py + collision fix |
| `tests/test_utils_trigger.py` | `file_hash`; `should_update` truth table | utils.py + 6h gate |

### Edge Cases Checklist
- [ ] Not a git repo → recon prints `NOT_A_GIT_REPO`, install refuses
- [ ] Re-install (ADOPT) → never clobbers `daily/`; refreshes `_shared` + hooks; no duplicate hook entry
- [ ] **Both skills installed in one repo → 2 distinct hook entries per event; neither command overwritten** (cl- markers)
- [ ] Worktree session → capture redirects to main checkout (`LERNER_ROOT`); SessionStart skips update spawn
- [ ] `last-update.json` absent → age=∞ (eligible) but only with new daily content
- [ ] Lock fresh (<6h) → no duplicate update spawn
- [ ] ldir is NOT `.claude`; CLAUDE.md/docs writes never land under `.claude/` (repo_guard + AGENTS.md)
- [ ] Seed on a repo that already has a root CLAUDE.md → UPDATE, not overwrite
- [ ] Missing `ANTHROPIC_API_KEY` → SDK call fails loudly; documented
- [ ] Empty/short session → flush returns FLUSH_OK, nothing appended

---

## Validation Commands

### Level 1: STATIC_ANALYSIS
```bash
cd plugins/neurawork-cc-harness
python3 -m py_compile engines/claudemd-lerner/*.py \
  engines/claudemd-lerner/payload/scripts/*.py \
  engines/claudemd-lerner/payload/hooks/*.py \
  engines/claudemd-lerner/tests/*.py
python3 -c "import json;json.load(open('engines/claudemd-lerner/config.default.json'))"
python3 -c "import tomllib;tomllib.load(open('engines/claudemd-lerner/payload/pyproject.toml','rb'))"
# No wiki leftovers and no kc env var leaked into lerner:
grep -RnE "knowledge/|wikilink|\[\[|KNOWLEDGE_ROOT|compile_age_hours" engines/claudemd-lerner && echo "LEAK" || echo "clean"
# All three hooks are cl- prefixed:
ls engines/claudemd-lerner/payload/hooks/ | grep -E '^cl-(session-start|session-end|pre-compact)\.py$' | wc -l   # expect 3
```
**EXPECT**: exit 0; `clean`; count `3`.

### Level 2: UNIT_TESTS
```bash
cd plugins/neurawork-cc-harness
python3 -m unittest discover -s engines/claudemd-lerner/tests -v
python3 -m unittest discover -s engines/knowledge-compiler/tests -v   # no Phase-2 regression
python3 -m unittest discover -s engines/_shared/tests -v              # no Phase-1 regression
```
**EXPECT**: all pass (git tests SKIP if no git).

### Level 3: FULL_SUITE
```bash
cd plugins/neurawork-cc-harness && python3 -m unittest discover -s engines -v
```
**EXPECT**: all pass.

### Level 4 / 5: N/A (no DB, no UI).

### Level 6: MANUAL_VALIDATION (gated on `ANTHROPIC_API_KEY`)
1. `plugin-dev:plugin-validator` → no errors.
2. Throwaway git repo with a README: `python3 .../claudemd-lerner/install.py --lerner-dir lc` → scaffold (daily/, scripts/, _shared/, cl- hooks) + settings hooks present; no `lc/knowledge/`.
3. `uv sync --directory lc`; write `lc/daily/<today>.md` (a convention/decision); `uv run --directory lc python scripts/update.py --all` → root `CLAUDE.md` updated + `lc/scripts/last-update.json`.
4. `uv run --directory lc python scripts/seed.py` on a small repo → root `CLAUDE.md` (+ `docs/`) created/updated, existing CLAUDE.md preserved.
5. Install kc AND lerner in the same repo → `.claude/settings.json` shows both hook sets; both fire independently.

---

## Acceptance Criteria
- [ ] All engine/payload/test files present and compile (Level 1).
- [ ] `clean` grep: no wiki constructs, no `KNOWLEDGE_ROOT`/`compile_age_hours` in lerner; exactly 3 `cl-` hooks.
- [ ] Hooks import from `_shared`; install copies `_shared` into ldir; `_shared`/`plugin.json` unchanged.
- [ ] update.py edits repo-root CLAUDE.md/docs (`cwd=REPO_ROOT`); stamps `last-update.json`; no knowledge/ created.
- [ ] `total_cost_usd` used; `setting_sources=[]`+`strict_mcp_config=True` on SDK calls; dep `>=0.2.96`.
- [ ] `seed.py` + `seed_prompt.txt` exist; install `--seed` runs them; UPDATE (not clobber) on existing CLAUDE.md.
- [ ] Unit tests pass (Level 2/3); Phase-1 + Phase-2 tests still pass.
- [ ] **Coexistence test passes**: both skills installed → distinct hook entries, no clobber.
- [ ] SKILL.md documents auth + FQN/coexistence note.
- [ ] plugin-validator clean.

## Completion Checklist
- [ ] Tasks 1–19 in order, each validated.
- [ ] Level 1/2/3 pass.
- [ ] Manual smoke documented (run if auth available).
- [ ] PRD Phase 3 → complete; Phase 4 (self-host + docs + license) unblocks (depends on 2 + 3, both then complete).

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Hook marker collision** overwrites kc's hooks when both installed | (was HIGH) | HIGH | cl- filenames → markers are non-substrings of kc commands both ways; explicit coexistence unit test (Task 18) |
| `update.py` agent edits the wrong files / writes under `.claude/` | MED | HIGH | `cwd=REPO_ROOT`; AGENTS.md forbids `.claude/`; pre-flight `assert_in_repo_not_dotclaude`; `claudemd_depth`/`excluded_dirs` bound the scope |
| Seed clobbers an existing root CLAUDE.md | MED | HIGH | seed_prompt + AGENTS.md mandate UPDATE; clean-tree precondition; foreground so the user sees the diff before commit |
| `_shared` import path wrong in `uv run` hooks | MED | HIGH | `sys.path.insert(parent.parent)` (proven in Phase 2); unit-test imports after simulated install |
| Wiki constructs accidentally carried over from kc | MED | MED | Level-1 grep gate (`knowledge/`, `[[`, `KNOWLEDGE_ROOT`); AGENTS.md grep |
| SDK auth missing on customer machines | MED | HIGH | Document `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` in SKILL+report |
| 6h trigger never fires / fires too often | LOW | MED | reuse proven `should_update`; lock debounce; atomic stamp; unit-tested truth table |
| Detached update blocks the 15s hook | LOW | MED | Popen returns immediately; print JSON after spawn |

---

## Notes

- **Why a mirror, not a fresh design**: Phase 2 already proved the capture→trigger→SDK→write loop on this exact infra. Phase 3's real novelty is small and bounded: `update.py` (editor over CLAUDE.md/docs), the CLAUDE.md/docs constitution, multi-level recon, and the marker-collision fix. Everything else is a rename.
- **The collision fix is the load-bearing decision.** `merge_hooks` (settings.py:59-60) recognizes "our" hook by a marker substring of the command. The relative command tail (`python hooks/<file>.py`) is the only stable, dir-name-independent place to differentiate skills, so the hook FILENAMES must differ. `cl-` prefix does it cleanly in both directions and survives any user-chosen ldir name.
- **`daily/` is kept** (not replaced by a transient staging buffer) so the incremental-by-hash `_select` + `should_update` machinery transfers unchanged from compile.py. Simplicity-first: reuse beats a new concept.
- **git-diff capture deferred**: PRD mentions "git-diff + conversation". v1 captures conversation (mirror of Phase 2) and the update agent grounds edits by reading the live repo (Read/Glob/Grep). A future refinement can append `git diff --stat`/short diff to the captured context in the hook (gitctx already shells git) — out of scope here to keep the mirror tight and low-risk.
- **Default ldir name `claudemd-lerner`**: unlike kc's `knowledge-base` (which holds tracked content), the lerner dir holds ONLY machinery (hooks/scripts/_shared/daily) — the user-facing output is the repo-root CLAUDE.md/docs. Named after the skill for clarity; user can rename in recon.
- **Auth**: subscription creds not sanctioned for third-party plugins → public/customer installs use `ANTHROPIC_API_KEY` (same posture as Phase 2; answers PRD open-question #6).
- **Confidence**: 9/10 — a structural mirror of a completed, tested skill on shared infra, with the one genuine hazard (marker collision) identified, fixed by design, and pinned by an explicit coexistence test. −1 only because the update/seed LLM behavior on CLAUDE.md hierarchies needs live-auth smoke to fully verify edit quality.
```
