# Feature: neurawork-cc-harness — knowledge-compiler Skill (Phase 2)

## Summary

Add the `knowledge-compiler` skill to the `neurawork-cc-harness` plugin: a per-repo, self-building knowledge base. It captures session transcripts into `daily/` logs (SessionEnd/PreCompact hooks), compiles them with the `claude-agent-sdk` into `knowledge/concepts/`, `knowledge/connections/`, and `knowledge/index.md`, injects the index back at SessionStart, and answers questions against the index (query). **Approach: PORT the upstream `coleam00/claude-memory-compiler` code as the base, then ADAPT.** The user authorized using cole's code; it is NOT the user's own `coding-suite` engine (which we must NOT copy). So: fetch the cole repo, port its scripts/hooks/AGENTS.md into `neurawork-cc-harness`, and apply our deltas — wire to the Phase-1 `engines/_shared/` helpers, swap the trigger to **manual + SessionStart-when-dailies-older-than-6h** (not cole's fixed 18:00 clock), add a **brownfield seed** step (cole lacks one), parameterize away any host-specifics, and apply current `claude-agent-sdk` (2026) conventions (`total_cost_usd`, `setting_sources=[]` isolation, `ANTHROPIC_API_KEY` auth). `coding-suite` is a *conceptual* reference only (it is the user's; do not paste from it).

**License**: settled — this is a public, openly-promoted approach (Karpathy's LLM-wiki architecture; cole actively invites rebuilds). Port freely. Credit lineage (Karpathy / coleam00) in `AGENTS.md` + README as courtesy attribution. No blocker.

## User Story

As a NeuraWork engineer or customer
I want to install a per-repo knowledge base that builds itself from my Claude Code sessions and seeds from my existing repo
So that knowledge stops evaporating at session end and I stop re-explaining the same context.

## Problem Statement

Knowledge from sessions is lost at session end; new/existing repos start with no accumulated knowledge. A working design for the capture→compile→inject loop exists (the user's `coding-suite` engine, and coleam00), but the user wants an *independent* implementation in the public `neurawork-cc-harness` — one that does not embed his existing code — that is repo-local, triggered on a 6h SessionStart gate rather than a rigid clock, and can seed an existing repo on install.

## Solution Statement

Clone `coleam00/claude-memory-compiler` to a reference checkout, then port its `scripts/` (flush, compile, query, lint, config, utils), `hooks/` (session-start, session-end, pre-compact), and `AGENTS.md` into `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/`, restructuring to our layout. Reuse Phase-1 `engines/_shared/` for stdin/transcript/git/settings/recon/write-guard (replacing cole's equivalents — one source of truth). Replace cole's 18:00 compile trigger with the PRD's manual slash-command + SessionStart 6h age-gate. Add `seed.py` for brownfield analysis (cole has none). Apply 2026 SDK conventions. Knowledge/daily always written inside the repo's knowledge-dir, never under `.claude/`.

## Metadata

| Field            | Value                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| Type             | NEW_CAPABILITY (concept reimplementation)                            |
| Complexity       | HIGH (LLM pipeline, hooks, trigger logic, seed — all written fresh)  |
| Systems Affected | Plugin skills/commands; per-repo `<kdir>/`; `.claude/settings.json`; `claude-agent-sdk` |
| Dependencies     | `claude-agent-sdk>=0.2.96`, `python-dotenv>=1.0.0`, `tzdata>=2024.1`; `uv`; git; Phase-1 `engines/_shared/` |
| Estimated Tasks  | 21                                                                    |

---

## UX Design

### Before State
```
╔══════════════════════════════════════════════════════════════════════╗
║                            BEFORE STATE                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  neurawork-cc-harness/ has only the Phase-1 scaffold:                   ║
║    .claude-plugin/plugin.json, engines/_shared/, empty skills/         ║
║                                                                        ║
║  A repo using the plugin gets NO knowledge capture. Sessions end and   ║
║  their context is lost. Existing repos have no knowledge base.         ║
║  PAIN: re-explanation every session; knowledge evaporates.             ║
╚══════════════════════════════════════════════════════════════════════╝
```

### After State
```
╔══════════════════════════════════════════════════════════════════════╗
║                             AFTER STATE                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  Install:  /neurawork-cc-harness:knowledge-compiler                    ║
║    recon (read-only) → AskUserQuestion(kdir name, tz, SEED?)           ║
║      → install.py: copy payload + _shared into <repo>/<kdir>/,         ║
║        scaffold daily/ + knowledge/{concepts,connections,index.md},    ║
║        merge 3 hooks, write .gitignore;  [optional] run seed.py        ║
║    then: uv sync --directory <kdir>                                    ║
║                                                                        ║
║  Per session:                                                          ║
║    SessionEnd / PreCompact ─► capture transcript ─► spawn flush.py     ║
║         flush.py (claude-agent-sdk) ─► append <kdir>/daily/<date>.md   ║
║    SessionStart ─► inject knowledge/index.md + recent daily            ║
║                 └─► if last compile > 6h AND new daily content:        ║
║                       spawn compile.py (detached) ─► knowledge/*       ║
║    Manual:  /neurawork-cc-harness:kc-compile  ─► compile.py --all      ║
║                                                                        ║
║  DATA: daily/, knowledge/ live INSIDE <repo>/<kdir>/ — never .claude/  ║
║  VALUE: self-building, repo-local knowledge; brownfield seed on day 1. ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| `/neurawork-cc-harness:knowledge-compiler` | n/a | recon→ask→install (+seed) | One-command per-repo install |
| `/neurawork-cc-harness:kc-compile` | n/a | manual compile now | On-demand knowledge build |
| SessionStart | nothing | injects index + maybe-compiles (6h gate) | Fresh context + timely compiles, no 18:00 wait |
| SessionEnd/PreCompact | nothing | captures transcript → daily log | Sessions accrue knowledge |

---

## Mandatory Reading

**CRITICAL — read before any task.**

**PRIMARY COPY-FROM SOURCE = the upstream cole repo** (fetched in Task 0). Port these files, adapting to our layout/deltas:
- `scripts/flush.py`, `scripts/compile.py`, `scripts/query.py`, `scripts/lint.py`, `scripts/config.py`, `scripts/utils.py`
- `hooks/session-start.py`, `hooks/session-end.py`, `hooks/pre-compact.py`
- `AGENTS.md`, `pyproject.toml`, `.claude/settings.json` (hook shapes)
Repo: `https://github.com/coleam00/claude-memory-compiler` (cloned to `/tmp/claude-memory-compiler-ref` in Task 0).

**SECONDARY (conceptual reference only — the user's code; do NOT paste):**
`/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/engines/knowledge-compiler/` — consult for how it already adapted cole (e.g. install.py ADOPT/FRESH, `uv run` hooks, recon). Use its *ideas*, write our own.

| Priority | File | Study for (then reimplement) |
|----------|------|------------------------------|
| P0 | `…/knowledge-compiler/install.py` | install design: ADOPT/FRESH detection, payload copy, scaffold, .gitignore, settings merge |
| P0 | `…/knowledge-compiler/payload/scripts/flush.py` | flush design: SDK text-only call, daily append format, dedup (NOTE: we drop its 18:00 trigger) |
| P0 | `…/knowledge-compiler/payload/scripts/compile.py` | compile design: prompt shape, tools, change detection, state.json |
| P0 | `…/knowledge-compiler/payload/hooks/session-end.py` | hook design: transcript capture → spawn flush (NOTE: we remove the homeserver hardcode entirely) |
| P0 | `…/knowledge-compiler/payload/hooks/session-start.py` | additionalContext injection shape |
| P0 | `…/continuous-learner/learn_session_start.py` | SessionStart age-gate + detached spawn + lock pattern (the 6h trigger model) |
| P1 | `…/knowledge-compiler/payload/hooks/pre-compact.py` | pre-compact variant (min-turns, prefix) |
| P1 | `…/knowledge-compiler/payload/scripts/config.py` | path-constant layout (NOTE: no hardcoded timezone) |
| P1 | `…/knowledge-compiler/payload/scripts/utils.py` | helper set to reimplement (file_hash, slugify, wikilinks, index entry) |
| P1 | `…/knowledge-compiler/payload/scripts/query.py` | index-guided Q&A design |
| P1 | `…/knowledge-compiler/payload/scripts/lint.py` | the 7 health checks (reimplement) |
| P1 | `…/knowledge-compiler/payload/AGENTS.md` | the article/compile SCHEMA — write our own constitution covering the same structure (concepts/connections/index, frontmatter, compile rules, no-RAG rationale) |
| P1 | `…/knowledge-compiler/recon.py` | recon design + RECON_JSON contract |
| P1 | `…/continuous-learner/bootstrap.py` + `bootstrap_prompt.txt` | SEED design (clean-tree precondition, foreground agent, repo analysis) |
| P0 | `plugins/neurawork-cc-harness/engines/_shared/*.py` | Phase-1 helpers to IMPORT (these we reuse directly — they are our own from Phase 1) |
| P1 | `…/coding-suite/skills/knowledge-compiler/SKILL.md` | install-skill flow (3-phase recon→ask→execute) to reimplement |

**IP hygiene**: the only code we reuse verbatim is our own Phase-1 `engines/_shared/`. Everything in `engines/knowledge-compiler/` is written fresh. Do not copy comments, identifiers, or prose from the reference engines; express the same behavior in our own words/structure. Acknowledge conceptual lineage (Karpathy-style LLM KB / coleam00) in `AGENTS.md` prose.

**Phase-1 `_shared` public API (import directly — our own code):**
- `hookio.recursion_guard()`, `hookio.read_hook_input() -> dict`, `hookio.child_env() -> dict`, const `hookio.INVOKED_BY_VALUE`
- `transcript.extract_turns(path, max_turns=30, max_chars=15000) -> str`
- `gitctx.repo_root(start=None)`, `gitctx.in_worktree(start=None)`, `gitctx.main_checkout_root(start=None)`, `gitctx.state_home(local_dir, start=None)`
- `settings.merge_hooks(repo_root, [(event, command, timeout, marker), ...]) -> bool`, `settings.SettingsError`
- `repo_guard.assert_in_repo_not_dotclaude(target, repo_root) -> Path`, `repo_guard.safe_join(repo_root, *parts) -> Path`, `repo_guard.WriteGuardError`
- `recon.git_root_or_none(start=None) -> str|None`, `recon.emit_recon_json(info: dict)`, `recon.parse_recon_json(stdout) -> dict|None`, const `recon.RECON_DELIMITER`

**External Documentation:**
| Source | Section | Why |
|--------|---------|-----|
| [claude-agent-sdk PyPI](https://pypi.org/project/claude-agent-sdk/) (v0.2.104, Jun 2026) | version | dep `>=0.2.96` (mcp<2.0.0 pin); 0.1.29-era API still valid |
| [Track cost and usage](https://code.claude.com/docs/en/agent-sdk/cost-tracking) | `ResultMessage.total_cost_usd` | correct cost field (NOT `cost_usd`) |
| [Agent SDK overview — auth](https://code.claude.com/docs/en/agent-sdk/overview) | API key auth | public plugin → `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`; subscription creds NOT sanctioned for third-party |
| [Python SDK reference](https://code.claude.com/docs/en/agent-sdk/python) | `setting_sources`, `strict_mcp_config` | isolate hook-spawned SDK calls from inherited `.claude/` settings |
| [Model configuration](https://code.claude.com/docs/en/model-config) | `model=` option | default `claude-opus-4-8`/alias; make configurable |

---

## Patterns to Mirror

These show the SHAPE/behavior to reproduce in our own code — reimplement, don't paste.

**SESSION-START AGE-GATE + DETACHED SPAWN** (behavior to reproduce for the 6h trigger):
```python
# CONCEPT (from learn_session_start.py:74-163) — write our own version:
# recursion_guard(); root = repo_root(); return if None; if in_worktree(): inject-only, no spawn.
# age = now - last_compile_ts();  spawn-eligible iff: new daily content exists
#   AND age >= compile_age_hours*3600  AND lock not fresh.
# spawn detached: start_new_session=True (POSIX), stdout/stderr=DEVNULL, env=child_env();
# write LOCK (mtime-checked) only after a successful spawn.
```

**SDK QUERY (compile) — 2026 conventions, our own code**:
```python
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
async for message in query(prompt=prompt, options=ClaudeAgentOptions(
        cwd=str(ROOT_DIR),
        system_prompt={"type": "preset", "preset": "claude_code"},
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=30,
        setting_sources=[],            # isolate from inherited .claude/ settings
        strict_mcp_config=True,        # no inherited MCP servers
        model=(cfg.get("model") or None),  # configurable; None = tier default
)):
    if isinstance(message, ResultMessage):
        cost = message.total_cost_usd or 0.0   # NOT message.cost_usd
```

**SDK QUERY (flush) — text-only**:
```python
ClaudeAgentOptions(cwd=str(ROOT), allowed_tools=[], max_turns=2,
                   setting_sources=[], strict_mcp_config=True,
                   model=(cfg.get("model") or None))
```

**HOOK ENTRYPOINT (wired to _shared)**:
```python
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # <kdir> on path
from _shared.hookio import recursion_guard, read_hook_input, child_env
recursion_guard()
from _shared.transcript import extract_turns
from _shared.gitctx import in_worktree, main_checkout_root, state_home
data = read_hook_input(); session_id = data.get("session_id", "unknown")
# kdir name derived from ROOT.name — NEVER a hardcoded literal.
```

**INSTALL settings merge (via _shared)**:
```python
from _shared.settings import merge_hooks
HOOKS = [
  ("SessionStart", f'uv run --directory "$CLAUDE_PROJECT_DIR/{kdir}" python hooks/session-start.py', 15, "hooks/session-start.py"),
  ("PreCompact",   f'uv run --directory "$CLAUDE_PROJECT_DIR/{kdir}" python hooks/pre-compact.py',   10, "hooks/pre-compact.py"),
  ("SessionEnd",   f'uv run --directory "$CLAUDE_PROJECT_DIR/{kdir}" python hooks/session-end.py',   10, "hooks/session-end.py"),
]
merge_hooks(repo_root, HOOKS)
```

**WRITE-GUARD on daily append + scaffold**:
```python
from _shared.repo_guard import assert_in_repo_not_dotclaude
assert_in_repo_not_dotclaude(daily_file, repo_root)   # raises if under .claude/
```

**SEED (NET-NEW; design from bootstrap.py)**:
```python
# precondition: git repo, working tree clean except knowledge-compiler artifacts.
# foreground query() with allowed_tools=[Read,Write,Edit,Glob,Grep], permission_mode=acceptEdits,
# max_turns~40, prompt = seed_prompt.txt + repo context (README, docs/, top-level source map).
# OUTPUT: initial knowledge/concepts/*.md + index.md; stamp last-compile.json on success.
```

---

## Files to Change

Paths relative to plugin root `plugins/neurawork-cc-harness/`. Every file below is **written fresh** (our own authorship).

| File | Action | Justification |
|------|--------|---------------|
| `engines/knowledge-compiler/VERSION` | CREATE | engine version stamp (`1`) |
| `engines/knowledge-compiler/config.default.json` | CREATE | `knowledge_dir`, `model`, `compile_age_hours` (6) |
| `engines/knowledge-compiler/recon.py` | CREATE | uses `_shared.recon`; adds `seed_recommended` signal |
| `engines/knowledge-compiler/install.py` | CREATE | copies payload + `_shared`; uses `_shared.settings.merge_hooks`; optional seed |
| `engines/knowledge-compiler/payload/pyproject.toml` | CREATE | name `neurawork-knowledge`; `claude-agent-sdk>=0.2.96` |
| `engines/knowledge-compiler/payload/AGENTS.md` | CREATE | our own compile/article schema constitution |
| `engines/knowledge-compiler/payload/scripts/config.py` | CREATE | path constants; `LAST_COMPILE_FILE`, `LOCK_FILE`; `load_cfg()`; no hardcoded tz |
| `engines/knowledge-compiler/payload/scripts/utils.py` | CREATE | reimplemented helpers |
| `engines/knowledge-compiler/payload/scripts/flush.py` | CREATE | SDK text-only daily append; NO compile trigger; `total_cost_usd`; `_shared`; isolation |
| `engines/knowledge-compiler/payload/scripts/compile.py` | CREATE | SDK compile; `last-compile.json` stamp; `total_cost_usd`; isolation; `model` |
| `engines/knowledge-compiler/payload/scripts/query.py` | CREATE | index-guided Q&A; `total_cost_usd`; isolation; `model` |
| `engines/knowledge-compiler/payload/scripts/lint.py` | CREATE | 7 health checks (reimplemented) |
| `engines/knowledge-compiler/payload/scripts/seed.py` | CREATE | brownfield seed |
| `engines/knowledge-compiler/payload/scripts/seed_prompt.txt` | CREATE | seed agent instructions |
| `engines/knowledge-compiler/payload/hooks/session-end.py` | CREATE | `_shared`; no homeserver hardcode |
| `engines/knowledge-compiler/payload/hooks/pre-compact.py` | CREATE | same; `MIN_TURNS_TO_FLUSH=5` |
| `engines/knowledge-compiler/payload/hooks/session-start.py` | CREATE | inject context + 6h-gated detached compile spawn |
| `skills/knowledge-compiler/SKILL.md` | CREATE | 3-phase install; namespace; ANTHROPIC_API_KEY note; FQN note |
| `commands/kc-compile.md` | CREATE | manual compile slash-command |
| `engines/knowledge-compiler/tests/test_install_recon.py` | CREATE | install merge + recon JSON (no LLM) |
| `engines/knowledge-compiler/tests/test_utils_trigger.py` | CREATE | utils + 6h age-gate logic (no LLM) |

---

## NOT Building (Scope Limits)

- **claudemd-lerner** (CLAUDE.md + docs/) — Phase 3.
- **No copying of the user's `coding-suite` engine** — port cole's upstream instead (explicit user instruction: "nimm cole's code", "nicht meinen"). `coding-suite` is conceptual reference only.
- **No vector/RAG** — index-based retrieval only (same design rationale).
- **No LLM-call unit tests** — the SDK pipeline (flush/compile/query/seed) is validated by manual smoke with real auth; only non-LLM logic (install, recon, utils, trigger gate) is unit-tested.
- **No global store** — knowledge stays in `<repo>/<kdir>/`, never `.claude/`.
- **Validators** — Session 2.

---

## Step-by-Step Tasks

Execute in order. Each is atomic and verifiable. "PORT" = start from the cole source file, restructure to our layout, apply the listed deltas. Replace cole's stdin/transcript/git helpers with `_shared` imports.

### Task 0: FETCH the cole reference repo
- **ACTION**: clone upstream to a reference path (NOT inside the plugin)
- **IMPLEMENT**: `git clone --depth 1 https://github.com/coleam00/claude-memory-compiler /tmp/claude-memory-compiler-ref` ; read its actual `scripts/`, `hooks/`, `AGENTS.md`, `pyproject.toml`
- **GOTCHA**: do not commit the clone into our repo; it is a read source only. Record the cloned commit SHA in the report for attribution.
- **VALIDATE**: `/tmp/claude-memory-compiler-ref/scripts/compile.py` exists

### Task 1: CREATE `engines/knowledge-compiler/VERSION`
- **IMPLEMENT**: single line `1`
- **VALIDATE**: file exists

### Task 2: CREATE `engines/knowledge-compiler/config.default.json`
- **IMPLEMENT (fresh)**: `{ "knowledge_dir": "knowledge-base", "model": "", "compile_age_hours": 6 }` — `model: ""` = SDK tier default; `compile_age_hours`=6 drives the SessionStart gate
- **VALIDATE**: `python3 -c "import json;json.load(open('engines/knowledge-compiler/config.default.json'))"`

### Task 3: CREATE `engines/knowledge-compiler/payload/pyproject.toml`
- **IMPLEMENT (fresh)**: `name="neurawork-knowledge"`, `requires-python=">=3.12"`, deps `claude-agent-sdk>=0.2.96`, `python-dotenv>=1.0.0`, `tzdata>=2024.1`, `[tool.ruff] line-length=100`
- **GOTCHA**: SDK lower bound `>=0.2.96` (mcp<2.0.0 pin)
- **VALIDATE**: `python3 -c "import tomllib;tomllib.load(open('engines/knowledge-compiler/payload/pyproject.toml','rb'))"`

### Task 4: CREATE `engines/knowledge-compiler/payload/AGENTS.md`
- **IMPLEMENT (fresh)**: our own constitution covering the SAME structure as the reference — concept article frontmatter (`title, aliases, tags, sources[], created, updated` + `## Key Points / ## Details / ## Related Concepts / ## Sources`); connection article (`connects: []` + `## The Connection / ## Key Insight / ## Evidence`); `index.md` table (`| Article | Summary | Compiled From | Updated |`); compile rules (3–7 concepts/log, prefer UPDATE, `[[wikilinks]]` no `.md`, every article cites sources); no-RAG rationale; scale ceiling note. Write in our own prose; credit lineage (Karpathy LLM-KB / coleam00) in one line.
- **GOTCHA**: this text is fed to the compiler LLM — must be self-consistent and complete; do not lift sentences from the reference.
- **VALIDATE**: file present with `##` sections for concepts + connections + index

### Task 5: CREATE `engines/knowledge-compiler/payload/scripts/utils.py`
- **IMPLEMENT (fresh)**: `file_hash(path)` (sha256[:16]), `slugify(text)`, `extract_wikilinks(content)`, `wiki_article_exists(link)`, `read_all_wiki_content()`, `list_wiki_articles()`, `list_raw_files()`, `count_inbound_links(target)`, `get_article_word_count(path)` (strip YAML frontmatter), `build_index_entry(...)`, `save_state(state)` (atomic tmp+os.replace)
- **VALIDATE**: `python3 -m py_compile .../utils.py`

### Task 6: CREATE `engines/knowledge-compiler/payload/scripts/config.py`
- **IMPLEMENT (fresh)**: `ROOT_DIR` honoring `KNOWLEDGE_ROOT` env; path constants `DAILY_DIR, KNOWLEDGE_DIR, CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR, SCRIPTS_DIR, AGENTS_FILE, INDEX_FILE, LOG_FILE, STATE_FILE`; ADD `LAST_COMPILE_FILE=SCRIPTS_DIR/"last-compile.json"`, `LOCK_FILE=SCRIPTS_DIR/"kc-compile.lock"`; `now_iso()`, `today_iso()`; `load_cfg()` merging `<kdir>/config.json` over defaults (`model`, `compile_age_hours`). NO hardcoded timezone.
- **VALIDATE**: `python3 -m py_compile .../config.py`

### Task 7: CREATE `engines/knowledge-compiler/payload/scripts/flush.py`
- **IMPLEMENT (fresh)**: set `CLAUDE_INVOKED_BY` before imports (recursion guard); resolve `ROOT` via `KNOWLEDGE_ROOT`; 60s dedup (`last-flush.json`); build a distillation prompt (Context/Key Exchanges/Decisions/Lessons/Action Items; return `FLUSH_OK` if nothing worth saving); `query()` text-only (`allowed_tools=[]`, `max_turns=2`, `setting_sources=[]`, `strict_mcp_config=True`, `model` from cfg); append to `daily/<date>.md` (create header on first write); read `total_cost_usd` if tracking. **NO compile trigger.** Guard daily write via `repo_guard.assert_in_repo_not_dotclaude`.
- **GOTCHA**: do NOT detach with DETACHED_PROCESS (breaks SDK subprocess I/O); the hook already Popen-spawned flush.
- **VALIDATE**: `python3 -m py_compile .../flush.py`

### Task 8: CREATE `engines/knowledge-compiler/payload/scripts/compile.py`
- **IMPLEMENT (fresh)**: build compile prompt (AGENTS.md + current index + existing articles + the daily log); `query()` with `[Read,Write,Edit,Glob,Grep]`, `permission_mode="acceptEdits"`, `max_turns=30`, isolation opts, `model` from cfg; CLI `--all/--file/--dry-run`; SHA-256[:16] change detection vs `state.json["ingested"]`; update state with `{hash, compiled_at, cost_usd: total_cost_usd}`; **write `LAST_COMPILE_FILE` `{"ts": <unix float>}` atomically on success** (the SessionStart gate's contract).
- **VALIDATE**: `python3 -m py_compile .../compile.py`

### Task 9: CREATE `engines/knowledge-compiler/payload/scripts/query.py`
- **IMPLEMENT (fresh)**: read index + relevant articles, answer; read-only tools + `--file-back` (adds Write/Edit → `knowledge/qa/<slug>.md`); isolation opts; `model` from cfg; `total_cost_usd`
- **VALIDATE**: `python3 -m py_compile .../query.py`

### Task 10: CREATE `engines/knowledge-compiler/payload/scripts/lint.py`
- **IMPLEMENT (fresh)**: 7 checks — broken wikilinks, orphan pages, orphan sources, stale articles, missing backlinks (suggestion/auto-fixable), sparse (<200 words), contradictions (LLM, no tools, `max_turns=2`, isolation opts). Markdown report to `reports/lint-<date>.md`; update `state["last_lint"]`.
- **VALIDATE**: `python3 -m py_compile .../lint.py`

### Task 11: CREATE `engines/knowledge-compiler/payload/scripts/seed_prompt.txt`
- **IMPLEMENT (fresh)**: instruct the agent to (1) read README + docs/ + top-level source map; (2) extract 5–15 foundational concepts of THIS repo into `knowledge/concepts/<slug>.md` per the AGENTS.md schema; (3) build connections; (4) write `knowledge/index.md`. Hard constraints: only write under `knowledge/`; no invented facts; cite the files read as sources.
- **VALIDATE**: file present, non-empty

### Task 12: CREATE `engines/knowledge-compiler/payload/scripts/seed.py`
- **IMPLEMENT (fresh; design from bootstrap.py)**: precondition — git repo + working tree clean except knowledge-compiler artifacts (else abort with stash/commit guidance); prompt = seed_prompt.txt + repo context (README, docs/ listing, top-level dir/file map); FOREGROUND `query()` with `[Read,Write,Edit,Glob,Grep]`, `permission_mode="acceptEdits"`, `max_turns≈40`, isolation opts, `model` from cfg; stamp `LAST_COMPILE_FILE` on success; confine writes to `knowledge/` via `repo_guard`.
- **GOTCHA**: foreground (install context), not detached; long timeout; prefer UPDATE if `knowledge/` already populated.
- **VALIDATE**: `python3 -m py_compile .../seed.py`

### Task 13: CREATE `engines/knowledge-compiler/payload/hooks/session-end.py`
- **IMPLEMENT (fresh)**: `sys.path.insert` kdir root; import from `_shared` (hookio/transcript/gitctx); `recursion_guard()`; `read_hook_input()` → session_id/transcript_path; skip if no transcript; `extract_turns(...)` → write context file under `scripts/`; Popen `uv run --directory <kdir> python scripts/flush.py <ctx> <session_id>` with `env=child_env()`; worktree redirect via `KNOWLEDGE_ROOT = main_checkout_root()/ROOT.name` (derive kdir name from `ROOT.name`, never a literal).
- **VALIDATE**: `python3 -m py_compile .../session-end.py`

### Task 14: CREATE `engines/knowledge-compiler/payload/hooks/pre-compact.py`
- **IMPLEMENT (fresh)**: same as Task 13; `MIN_TURNS_TO_FLUSH=5`; log tag `[pre-compact]`; context prefix `flush-context-`; tolerate empty `transcript_path`
- **VALIDATE**: `python3 -m py_compile .../pre-compact.py`

### Task 15: CREATE `engines/knowledge-compiler/payload/hooks/session-start.py`
- **IMPLEMENT (fresh)**: (a) build additionalContext = today date + `knowledge/index.md` + last 30 lines of most-recent daily; emit `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":ctx}}`. (b) before emitting: `recursion_guard()`; if `repo_root()` and not `in_worktree()`: read `LAST_COMPILE_FILE` ts; if a daily log is newer than ts AND `now-ts > compile_age_hours*3600` AND lock not fresh → Popen detached `uv run --directory <kdir> python scripts/compile.py --all` (`start_new_session=True`, `env=child_env()`, DEVNULL); write `LOCK_FILE` after spawn. In a worktree: inject-only, no spawn.
- **GOTCHA**: Popen returns immediately; print JSON after; never block the 15s hook.
- **VALIDATE**: `python3 -m py_compile .../session-start.py`

### Task 16: CREATE `engines/knowledge-compiler/recon.py`
- **IMPLEMENT (fresh)**: use `_shared.recon.git_root_or_none()` (NOT_A_GIT_REPO path); inspect branch/clean, existing knowledge-dir (structural: `hooks/session-end.py`+`scripts/flush.py`), existing hooks per event, tz; ADD `seed_recommended` = knowledge dir absent/empty AND repo has README/docs; `recon.emit_recon_json(info)`
- **VALIDATE**: `python3 -m py_compile engines/knowledge-compiler/recon.py`

### Task 17: CREATE `engines/knowledge-compiler/install.py`
- **IMPLEMENT (fresh)**: ADOPT vs FRESH (structural detection); copy_payload (hooks/*, scripts/*, pyproject.toml, AGENTS.md, config.json from defaults); **copy `engines/_shared/` → `<kdir>/_shared/`**; scaffold daily/ + knowledge/{concepts,connections} + index.md seed; write `.gitignore` (daily/, scripts state/logs, `__pycache__`, knowledge/log.md); `_shared.settings.merge_hooks(repo_root, HOOKS)`; stamp VERSION; CLI `--knowledge-dir NAME`, `--seed` (→ run seed.py); print venv-prime + commit guidance; assert kdir not `.claude/` via `repo_guard`.
- **GOTCHA**: ADOPT must not clobber existing `knowledge/`/scripts — only ensure hooks + gitignore + refresh `_shared`.
- **VALIDATE**: `python3 -m py_compile engines/knowledge-compiler/install.py`

### Task 18: CREATE `skills/knowledge-compiler/SKILL.md`
- **IMPLEMENT (fresh)**: frontmatter `name: knowledge-compiler` + trigger-rich `description`. 3 phases: A recon (`python3 "${CLAUDE_PLUGIN_ROOT}/engines/knowledge-compiler/recon.py"`); B AskUserQuestion (kdir name default `knowledge-base`; confirm tz; offer SEED if `seed_recommended`); C execute (`install.py [--knowledge-dir N] [--seed]` then `uv sync --directory <kdir>`). ADD Auth note (`ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN`; subscription creds not sanctioned for third-party). ADD FQN/collision note (`coding-suite:knowledge-compiler` also exists → use `neurawork-cc-harness:knowledge-compiler`).
- **VALIDATE**: YAML frontmatter parses; plugin-validator (Task 21)

### Task 19: CREATE `commands/kc-compile.md`
- **IMPLEMENT (fresh)**: frontmatter `description` + `argument-hint: "[--all|--file <daily>]"`; body locates the knowledge-dir (structural detection / config) then runs `uv run --directory <kdir> python scripts/compile.py --all`; reports result + cost
- **VALIDATE**: file present; frontmatter parses

### Task 20: CREATE unit tests (non-LLM only)
- **IMPLEMENT (fresh)**: `tests/test_install_recon.py` + `tests/test_utils_trigger.py` (+ `__init__.py`)
  - install/recon: temp git repo → install FRESH → assert `<kdir>/` scaffolded (daily/, knowledge/concepts, index.md), `_shared/` copied, 3 hooks merged idempotently, `.gitignore` written; re-run idempotent; recon emits parseable RECON_JSON (`recon.parse_recon_json`)
  - utils/trigger: `slugify`/`file_hash`/`extract_wikilinks`/`build_index_entry`; a PURE `should_compile(now, last_ts, age_hours, has_new_daily, in_wt, lock_fresh) -> bool` truth table (fresh→no, stale+new→yes, worktree→no, lock fresh→no)
- **MIRROR**: Phase-1 `engines/_shared/tests/` (unittest + tempfile + real git; `shutil.which("git")` skip-guard)
- **VALIDATE**: `python3 -m unittest discover -s engines/knowledge-compiler/tests -v`

### Task 21: VALIDATE plugin + manual smoke
- **IMPLEMENT**: run `plugin-dev:plugin-validator`; document manual SDK smoke (requires `ANTHROPIC_API_KEY`): install into throwaway repo, `uv sync`, fabricate `daily/<today>.md`, `compile.py --all` → `knowledge/concepts/*.md` + `index.md` + `last-compile.json`; `seed.py` on a small repo → initial concepts
- **VALIDATE**: validator clean; smoke documented in report (gated on auth)

---

## Testing Strategy

### Unit Tests to Write (non-LLM)
| Test File | Cases | Validates |
|-----------|-------|-----------|
| `tests/test_install_recon.py` | FRESH scaffold, idempotent re-install, `_shared` copied, hooks merged, recon JSON keys | install.py + recon.py |
| `tests/test_utils_trigger.py` | slugify/file_hash/wikilinks/index-entry; `should_compile` truth table | utils.py + 6h gate |

### Edge Cases Checklist
- [ ] Not a git repo → recon prints `NOT_A_GIT_REPO`, install refuses
- [ ] Re-install (ADOPT) → never clobbers existing `knowledge/`/scripts; refreshes `_shared` + hooks
- [ ] Worktree session → capture redirects to main checkout; SessionStart skips compile spawn
- [ ] `last-compile.json` absent → age=∞ (eligible) but only with new daily content
- [ ] Lock fresh (<6h) → no duplicate compile spawn
- [ ] kdir is NOT `.claude`; writes never land under `.claude/` (repo_guard)
- [ ] Missing `ANTHROPIC_API_KEY` → SDK call fails loudly; documented
- [ ] Empty/short session → flush returns FLUSH_OK, nothing meaningful appended

---

## Validation Commands

### Level 1: STATIC_ANALYSIS
```bash
cd plugins/neurawork-cc-harness
python3 -m py_compile engines/knowledge-compiler/*.py \
  engines/knowledge-compiler/payload/scripts/*.py \
  engines/knowledge-compiler/payload/hooks/*.py \
  engines/knowledge-compiler/tests/*.py
python3 -c "import json;json.load(open('engines/knowledge-compiler/config.default.json'))"
python3 -c "import tomllib;tomllib.load(open('engines/knowledge-compiler/payload/pyproject.toml','rb'))"
grep -RnE "homeserver-knowledge|America/Chicago" engines/knowledge-compiler && echo "LEAK" || echo "clean"
```
**EXPECT**: exit 0; `clean`.

### Level 2: UNIT_TESTS
```bash
cd plugins/neurawork-cc-harness
python3 -m unittest discover -s engines/knowledge-compiler/tests -v
python3 -m unittest discover -s engines/_shared/tests -v   # no Phase-1 regression
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
2. Throwaway git repo: `python3 .../install.py --knowledge-dir kb` → scaffold + hooks present.
3. `uv sync --directory kb`; write `kb/daily/<today>.md`; `uv run --directory kb python scripts/compile.py --all` → `kb/knowledge/concepts/*.md` + `index.md` + `kb/scripts/last-compile.json`.
4. `uv run --directory kb python scripts/seed.py` on a small repo → initial concepts.
5. New session → SessionStart injects index; after 6h+new daily → compile auto-spawns.

---

## Acceptance Criteria
- [ ] All engine/payload files present and compile (Level 1).
- [ ] No reference-engine code pasted in; no homeserver hardcodes (`grep` → `clean`).
- [ ] Hooks import from `_shared`; install copies `_shared` into kdir.
- [ ] No compile-in-flush; compile via manual command + SessionStart 6h gate.
- [ ] `total_cost_usd` used; `setting_sources=[]`+`strict_mcp_config=True` on SDK calls; dep `>=0.2.96`.
- [ ] `seed.py` + `seed_prompt.txt` exist; install `--seed` runs them.
- [ ] Unit tests pass (Level 2/3); Phase-1 tests still pass.
- [ ] SKILL.md documents `ANTHROPIC_API_KEY` auth + FQN/collision note.
- [ ] plugin-validator clean.

## Completion Checklist
- [ ] Tasks 1–21 in order, each validated.
- [ ] Level 1/2/3 pass.
- [ ] Manual smoke documented (run if auth available).
- [ ] PRD Phase 2 → complete; Phase 3 remains parallel-ready; Phase 4 unblocks after 2+3.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `_shared` import path wrong in `uv run` hooks | MED | HIGH | `sys.path.insert(parent.parent)`; unit-test imports after simulated install |
| SDK auth missing on customer machines | MED | HIGH | Document `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` in SKILL+README |
| Port introduces subtle pipeline bugs while adapting | MED | MED | Diff against cole reference; manual smoke against real SDK; keep article schema faithful |
| 6h trigger never fires / fires too often | MED | MED | Pure `should_compile` unit-tested; lock debounce; atomic last-compile stamp |
| Host-specifics leak from a coding-suite glance | LOW | MED | Port from cole upstream (clean), not coding-suite; grep gate for `homeserver-knowledge`/`America/Chicago` |
| Detached compile blocks the 15s hook | LOW | MED | Popen returns immediately; print JSON after spawn |
| Seed corrupts a dirty tree | LOW | MED | Clean-tree precondition; writes confined to `knowledge/` via repo_guard |

---

## Notes

- **Why port cole, not coding-suite**: the user authorized cole's upstream and excluded his own `coding-suite` engine. cole = copy-from base; coding-suite = conceptual reference only. First-party reused code = our Phase-1 `_shared/`.
- **License**: settled — public Karpathy-style LLM-wiki approach, cole invites rebuilds. Attribution-only (Karpathy/coleam00) in AGENTS.md + README. Not a blocker.
- **Single source of truth for `_shared`**: install.py copies `engines/_shared/` into each kdir at install time (no static duplicate in the payload).
- **Trigger is the main behavioral delta** vs the reference: it compiles inside flush at ≥18:00; we compile via manual command + SessionStart when dailies are >6h stale (interval=6h, mtime+last-compile gated).
- **Auth**: subscription creds not sanctioned for third-party plugins → public/customer installs use `ANTHROPIC_API_KEY`. Answers PRD open-question #6.
- **Confidence**: 8/10 — porting cole's working code (not rewriting) lowers bug surface; non-LLM parts unit-tested; the new deltas (6h trigger, seed, `_shared` wiring) are bounded. −2 only because the LLM pipeline needs live-auth smoke to fully verify.
```
