# Feature: Compliance Workflow Engine (`compliance-compiler`)

## Summary

Add a third engine — `compliance-compiler` — to the `neurawork-cc-harness` plugin,
self-hosted in this repo exactly like `knowledge-compiler` and `claudemd-lerner`.
It has two halves:

1. **Extraction** — a parallel, fan-out SDK job (~30 agents, one per catalog shard)
   that reads three compliance frameworks (**GDPR/DSGVO**, **SOC 2**, **ISO 27001
   Annex A**) and distils each into a repo-tracked catalog of atomic *constraints*
   ("features"): `{id, framework, title, requirement, applies_when, check}`.
2. **Validator hook** — a `PostToolUse` hook that fires when a PRP plan file
   (`.claude/PRPs/plans/*.plan.md`) is written, loads the catalog, and reports which
   mandatory constraints the plan does not yet address (advisory by default, blocking
   opt-in). A `/neurawork-cc-harness:co-validate` slash command runs the same check
   on demand with a deeper LLM pass.

This is **plan only** — no code is written by this document.

## User Story

As a developer building software in this repo (and any repo that installs the harness),
I want an always-current, machine-readable catalog of GDPR / SOC 2 / ISO 27001 constraints
plus an automatic check of my implementation plans against it,
So that I know exactly which compliance features/conditions a plan must satisfy *before*
I implement, instead of discovering gaps during an audit.

## Problem Statement

Compliance requirements (GDPR articles, SOC 2 Trust Service Criteria, ISO 27001 Annex A
controls) live in dense prose no one re-reads per feature. There is no structured,
queryable list of "what must be true" and no automated gate that checks a plan against it.
Testable: given a PRP plan that stores PII without a data-residency guarantee, the system
must (a) contain a catalog constraint expressing GDPR data-residency, and (b) surface that
the plan does not address it.

## Solution Statement

Mirror the existing engine architecture. A new `compliance-compiler` engine ships in
`plugins/neurawork-cc-harness/engines/`, installs into a repo as `compliance-base/` at the
repo root (never under `.claude/`, per `repo_guard`), and:

- **`scripts/extract.py`** fans out bounded-concurrency `claude_agent_sdk.query()` agents
  (up to ~30 shards) via `asyncio.gather` + a semaphore. Each agent owns one framework shard
  and writes constraints for that shard. This is the one genuinely new pattern — every
  existing script runs a single agent per file, sequentially.
- **`compliance-base/catalog/{gdpr,soc2,iso27001}.json`** + `catalog/index.md` are the
  tracked output.
- **`hooks/co-session-start.py`** injects the catalog index at session start and (age-gated,
  mirroring `session-start.py`) spawns a detached re-extract when stale.
- **`hooks/co-post-tooluse.py`** is the validator: a `PostToolUse` hook matched to `Write|Edit`
  on plan paths. It runs a fast deterministic structural pre-check inline (<1s) and spawns a
  detached `scripts/validate.py` for the deep LLM check that writes `compliance-base/reports/<plan>.md`.

## Metadata

| Field            | Value                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| Type             | NEW_CAPABILITY                                                        |
| Complexity       | HIGH                                                                  |
| Systems Affected | `plugins/neurawork-cc-harness/engines/`, `plugins/neurawork-cc-harness/skills/`, `plugins/neurawork-cc-harness/commands/`, repo-root `compliance-base/`, `.claude/settings.json`, root `CLAUDE.md` |
| Dependencies     | `claude-agent-sdk>=0.2.96`, `python-dotenv>=1.0.0`, `tzdata>=2024.1`, `uv`, Python ≥3.12; LLM auth via `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` |
| Estimated Tasks  | 17                                                                    |

---

## UX Design

### Before State

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              BEFORE STATE                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌─────────────┐        ┌──────────────┐        ┌──────────────────┐         ║
║   │ /prp-plan   │ ─────► │  plan.md     │ ─────► │  /prp-implement  │         ║
║   │ writes plan │        │  (no compl.  │        │  (no compliance  │         ║
║   └─────────────┘        │   awareness) │        │   gate)          │         ║
║                          └──────────────┘        └──────────────────┘         ║
║                                                                               ║
║   USER_FLOW: dev plans a feature → implements → compliance checked (if ever)   ║
║              manually, later, by reading GDPR/SOC2/ISO prose.                   ║
║   PAIN_POINT: no structured constraint list; no automatic plan-vs-rules check. ║
║   DATA_FLOW: compliance knowledge lives only in external PDFs / human memory.   ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### After State

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                               AFTER STATE                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌───────────────┐   30 parallel agents   ┌────────────────────────────┐     ║
║   │ scripts/      │ ─────────────────────► │ compliance-base/catalog/   │     ║
║   │ extract.py    │  (asyncio.gather +     │   gdpr.json soc2.json      │     ║
║   │ (~30 shards)  │   semaphore)           │   iso27001.json + index.md │     ║
║   └───────────────┘                        └────────────┬───────────────┘     ║
║                                                          │ (tracked, in repo)  ║
║                                                          ▼                     ║
║   ┌─────────────┐      ┌──────────────┐      ┌──────────────────────────┐     ║
║   │ /prp-plan   │ ───► │  plan.md     │ ───► │ co-post-tooluse.py HOOK   │     ║
║   │ writes plan │      │  written     │      │  (PostToolUse Write|Edit) │     ║
║   └─────────────┘      └──────────────┘      └────────────┬─────────────┘     ║
║                                                           │                    ║
║                          inline <1s structural check ─────┤                    ║
║                          + detached deep LLM validate ────▼                    ║
║                                             ┌──────────────────────────┐       ║
║                                             │ reports/<plan>.md +       │  ◄── new
║                                             │ additionalContext warning │       ║
║                                             │ "GDPR-DR-01 unaddressed"  │       ║
║                                             └──────────────────────────┘       ║
║                                                                               ║
║   USER_FLOW: catalog built once (re-built when stale) → every plan write is    ║
║              checked → dev sees uncovered mandatory constraints immediately.    ║
║   VALUE_ADD: compliance gaps surface at plan time, structured + queryable.      ║
║   DATA_FLOW: framework prose → JSON constraints (repo) → plan validation report.║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### Interaction Changes

| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| Session start | KB + CLAUDE.md context injected | + compliance catalog index injected | Dev sees applicable frameworks up front |
| `.claude/PRPs/plans/*.plan.md` written | nothing happens | `co-post-tooluse.py` runs structural check + spawns deep validate | Immediate "N mandatory constraints unaddressed" feedback |
| CLI | n/a | `uv run --directory compliance-base python scripts/extract.py` | On-demand (re)build of the catalog with ~30 parallel agents |
| Slash command | n/a | `/neurawork-cc-harness:co-validate <plan>` | On-demand deep LLM validation of a specific plan |
| `/neurawork-cc-harness:co-extract` | n/a | slash command | Trigger extraction from inside a session |

---

## Mandatory Reading

**The implementation agent MUST read these before starting any task.** Paths are relative
to repo root `/home/felix/projects/howtobuildsoftware2026`.

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py` | all (~160) | Install machinery to MIRROR verbatim (`_copy_code`, `_scaffold`, `_hooks`, `main`, `_is_adopt`) |
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/compile.py` | 45-189 | SDK call path + `main()` loop. Extraction MODIFIES this into a parallel fan-out |
| P0 | `plugins/neurawork-cc-harness/engines/_shared/settings.py` | 23-81 | `merge_hooks(root, [(event, command, timeout, marker)])` — how hooks land idempotently in settings.json |
| P0 | `plugins/neurawork-cc-harness/engines/_shared/repo_guard.py` | all (51) | `assert_in_repo_not_dotclaude` / `safe_join` — catalog write target must pass these |
| P1 | `knowledge-base/hooks/session-start.py` | all (~123) | Hook shape to mirror: `recursion_guard`, age-gate `maybe_spawn_*`, `build_context`, JSON `additionalContext` output |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/hooks/session-start.py` | all | Payload copy of the same hook (edit this one; the root `knowledge-base/` copy is a live install) |
| P1 | `plugins/neurawork-cc-harness/engines/_shared/hookio.py` | 19-57 | `read_hook_input`, `recursion_guard`, `child_env`, `INVOKED_BY_VALUE` — required at top of every hook |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/tests/test_install_recon.py` | all | Test pattern: temp git repo + subprocess, fresh-scaffold + idempotent-reinstall assertions |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/utils.py` | (gate fn `should_compile`) | Pure age-gate to mirror as `should_extract` |
| P1 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/config.default.json` | all | Config template shape |
| P2 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/AGENTS.md` | all | Constitution style to mirror for the extractor/validator constitution |
| P2 | `.claude/PRPs/plans/neurawork-cc-harness-exemplary-docs-selfhost.plan.md` | 1-30 | Real plan file — the exact structure the validator must parse |
| P2 | `/home/felix/.claude/plugins/marketplaces/prp-marketplace/plugins/prp-core/commands/prp-implement.md` | 69-103 | Which plan sections downstream tools parse (Summary, Files to Change, Tasks, Validation Commands, Acceptance Criteria) |
| P2 | `plugins/CLAUDE.md` | all | Engine/payload split rules; `sys.path` resolution of payload scripts |
| P2 | `knowledge-base/CLAUDE.md` | 9-30 | Tracked-vs-machinery split for a self-host dir |

**External Documentation:**

| Source | Section | Why Needed |
|--------|---------|------------|
| [claude-agent-sdk (Python) — `query` + `ClaudeAgentOptions`](https://docs.claude.com/en/api/agent-sdk/python) | streaming `query`, options | Confirm parallel `query()` coroutines under one `asyncio.gather` is supported; option names match `compile.py` |
| [Python `asyncio` — Semaphore + gather](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore) | bounded concurrency | Cap in-flight agents (~10–16) while enqueuing ~30 shards |
| [Claude Code hooks — events + matchers](https://docs.claude.com/en/docs/claude-code/hooks) | `PostToolUse`, matcher, `hookSpecificOutput` | `PostToolUse` is NOT used anywhere in this repo — verify event name, `Write\|Edit` matcher syntax, and how to emit an advisory-vs-blocking decision |
| GDPR / DSGVO — Regulation (EU) 2016/679, official text | Articles 1–99, Chapters I–XI | Source catalog for extraction shards |
| AICPA SOC 2 — Trust Services Criteria (2017, rev. 2022) | CC1–CC9 + Availability/Confidentiality/Processing Integrity/Privacy | Source catalog for extraction shards |
| ISO/IEC 27001:2022 Annex A | 93 controls in 4 themes (Organizational/People/Physical/Technological) | Source catalog for extraction shards |

> GOTCHA (licensing): The full ISO 27001 and SOC 2 texts are copyrighted and not freely
> redistributable. Extraction agents must be given the source text by the operator (local
> files / paid access) or restricted to the publicly enumerable *control identifiers +
> titles + paraphrased intent* — the catalog stores paraphrased requirements, not verbatim
> standard text. GDPR full text is public. See NOT Building.

---

## Patterns to Mirror

**INSTALL_MACHINERY** — copy payload + refresh `_shared`, scaffold data only if absent:
```python
# SOURCE: plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py:64-77
def _copy_code(target: Path) -> None:
    (target / "hooks").mkdir(parents=True, exist_ok=True)
    (target / "scripts").mkdir(parents=True, exist_ok=True)
    for src in (PAYLOAD / "hooks").glob("*.py"):
        shutil.copy2(src, target / "hooks" / src.name)
    for src in (PAYLOAD / "scripts").iterdir():
        if src.suffix in (".py", ".txt"):
            shutil.copy2(src, target / "scripts" / src.name)
    shutil.copy2(PAYLOAD / "pyproject.toml", target / "pyproject.toml")
    shutil.copy2(PAYLOAD / "AGENTS.md", target / "AGENTS.md")
    shutil.copytree(SHARED_SRC, target / "_shared",
                    ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
```

**HOOK_REGISTRATION** — the tuple list handed to `merge_hooks`:
```python
# SOURCE: plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py:101-107
def _hooks(kdir: str) -> list[tuple[str, str, int, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{kdir}" python'
    return [
        ("SessionStart", f"{base} hooks/session-start.py", 15, "hooks/session-start.py"),
        ("PreCompact",   f"{base} hooks/pre-compact.py",   10, "hooks/pre-compact.py"),
        ("SessionEnd",   f"{base} hooks/session-end.py",   10, "hooks/session-end.py"),
    ]
# COMPLIANCE VARIANT: co- prefixed markers, disjoint from both existing engines:
#   ("SessionStart", f"{base} hooks/co-session-start.py", 15, "hooks/co-session-start.py"),
#   ("PostToolUse",  f"{base} hooks/co-post-tooluse.py",  15, "hooks/co-post-tooluse.py"),  # NEW event
```

**SDK_CALL_PATH** — the single-agent shape each extraction shard reuses:
```python
# SOURCE: plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/scripts/compile.py:106-119
async for message in query(
    prompt=_build_prompt(log_path),
    options=ClaudeAgentOptions(
        cwd=str(ROOT_DIR),
        system_prompt={"type": "preset", "preset": "claude_code"},
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=30,
        setting_sources=[],
        strict_mcp_config=True,
        model=(cfg.get("model") or None),
    ),
):
```

**PARALLEL_FAN_OUT** — the ONE new pattern (not present in repo). Bounded concurrency:
```python
# NEW in scripts/extract.py — mirror compile_one() body per shard, but run concurrently.
async def extract_all(shards: list[Shard], cfg: dict) -> float:
    sem = asyncio.Semaphore(int(cfg.get("max_concurrency", 12)))
    async def run(shard):
        async with sem:
            return await extract_one(shard, cfg)   # body mirrors compile_one():95-139
    results = await asyncio.gather(*(run(s) for s in shards), return_exceptions=True)
    # sum costs; log any Exception results (do NOT swallow — per silent-failure policy)
    ...
# main(): total = asyncio.run(extract_all(build_shards(cfg), cfg))  # ONE asyncio.run, ~30 shards
```

**HOOK_SHAPE** — recursion guard + age-gated detached spawn + JSON context:
```python
# SOURCE: knowledge-base/hooks/session-start.py (structure)
def maybe_spawn_extract(age_hours: float) -> None:
    if not should_extract(now, last_ts, age_hours, has_new_source, in_wt=False, lock_fresh):
        return
    cmd = ["uv", "run", "--directory", str(KDIR), "python", "scripts/extract.py"]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env=child_env(), start_new_session=True)
    LOCK_FILE.write_text(str(now), encoding="utf-8")

def main() -> None:
    recursion_guard()   # _shared/hookio.py — no-op if spawned by our own claude -p
    if repo_root(str(KDIR)) and not in_worktree(str(KDIR)):
        try: maybe_spawn_extract(float(load_cfg().get("extract_age_hours", 168)))
        except Exception: pass  # injection must always proceed
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": build_context()}}))
```

**WRITE_GUARD** — validate every write target before writing the catalog:
```python
# SOURCE: plugins/neurawork-cc-harness/engines/_shared/repo_guard.py:26-44
def assert_in_repo_not_dotclaude(target_path, repo_root) -> Path:
    ...  # raises WriteGuardError if outside repo, or at/under <root>/.claude/
# CALL before writing compliance-base/catalog/*.json  (mirror update.py:194-195)
```

**TEST_STRUCTURE** — temp git repo + subprocess, no network:
```python
# SOURCE: plugins/neurawork-cc-harness/engines/knowledge-compiler/tests/test_install_recon.py:38-102
@unittest.skipUnless(shutil.which("git"), "git not available")
class TestInstall(unittest.TestCase):
    def test_fresh_scaffold_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp); _init_repo(repo)
            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)
            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            for event in ("SessionStart", "PostToolUse"):
                self.assertIn(event, settings["hooks"])
```

---

## Files to Change

| File | Action | Justification |
|------|--------|---------------|
| `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | CREATE | Install machinery (mirror knowledge-compiler) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/recon.py` | CREATE | Read-only pre-install recon (mirror) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/config.default.json` | CREATE | `{catalog_dir, model, extract_age_hours, frameworks, max_concurrency, validate_mode}` |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/VERSION` | CREATE | `0.1.0` |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/pyproject.toml` | CREATE | Same deps + ruff line-length 100 |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/AGENTS.md` | CREATE | Extraction + validation constitution |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/extract.py` | CREATE | Parallel fan-out extractor (NEW pattern) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/validate.py` | CREATE | Deep LLM plan-vs-catalog validator |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/shards.py` | CREATE | Builds ~30 framework shards |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/precheck.py` | CREATE | Fast deterministic structural plan check (no LLM) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/config.py` | CREATE | Path/const resolution (mirror) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/utils.py` | CREATE | `should_extract` age-gate (mirror `should_compile`) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/hooks/co-session-start.py` | CREATE | Inject catalog index + age-gated re-extract spawn |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/hooks/co-post-tooluse.py` | CREATE | Validator hook (NEW event) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py` | CREATE | Fresh + idempotent install assertions incl. PostToolUse |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_shards_precheck.py` | CREATE | Pure-logic tests: shard count, precheck parsing |
| `plugins/neurawork-cc-harness/skills/compliance-compiler/SKILL.md` | CREATE | Installable skill entry (mirror existing SKILL.md) |
| `plugins/neurawork-cc-harness/commands/co-extract.md` | CREATE | `/neurawork-cc-harness:co-extract` slash command |
| `plugins/neurawork-cc-harness/commands/co-validate.md` | CREATE | `/neurawork-cc-harness:co-validate <plan>` slash command |
| `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` | UPDATE | Register the new skill + commands |
| `.claude/settings.json` | UPDATE (via install) | Add `SessionStart` + `PostToolUse` co- hook entries |
| `CLAUDE.md` (root) | UPDATE | Document the third engine + `compliance-base/` self-host + commands |
| `compliance-base/` (repo root, self-host install) | CREATE (via install) | Live install: machinery + `catalog/` + `reports/` |

---

## NOT Building (Scope Limits)

- **Not running the extraction in this task.** Plan only. Extraction (the ~30 agents) runs
  when the operator invokes `/neurawork-cc-harness:co-extract` or `scripts/extract.py`.
- **Not shipping verbatim ISO 27001 / SOC 2 standard text.** Copyright. Catalog stores
  paraphrased requirements + official control IDs/titles; operator supplies source text.
- **Not validating code or diffs.** Validator targets `.claude/PRPs/plans/*.plan.md` only
  (per the decision). Code/diff validation is a future engine mode.
- **Not blocking by default.** `validate_mode: "warn"` — advisory `additionalContext`.
  `"block"` is opt-in config; a hook that hard-blocks writes is out of scope for v1.
- **Not embeddings / RAG / a vector DB.** Catalog is JSON + an LLM reasoning over it, matching
  the repo's "no RAG at repo scale" decision.
- **Not a legal-compliance guarantee.** Advisory tooling; it flags likely gaps, not a
  certification.
- **Not auto-installing into other repos.** Self-host into this repo; distribution stays via
  the existing marketplace manifest.

---

## Step-by-Step Tasks

Execute in order. Each task is atomic and independently verifiable. `ENGINE` =
`plugins/neurawork-cc-harness/engines/compliance-compiler`.

### Task 1: CREATE `$ENGINE/VERSION` and `$ENGINE/config.default.json`
- **ACTION**: CREATE version stamp + default config.
- **IMPLEMENT**: `VERSION` = `0.1.0`. `config.default.json`:
  `{"catalog_dir": "compliance-base", "model": "", "extract_age_hours": 168, "frameworks": ["gdpr","soc2","iso27001"], "max_concurrency": 12, "validate_mode": "warn"}`
- **MIRROR**: `plugins/neurawork-cc-harness/engines/knowledge-compiler/config.default.json`
- **VALIDATE**: `python3 -c "import json,pathlib; json.loads(pathlib.Path('$ENGINE/config.default.json').read_text())"`

### Task 2: CREATE `$ENGINE/payload/pyproject.toml`
- **ACTION**: CREATE payload project file.
- **IMPLEMENT**: name `neurawork-compliance`, `requires-python = ">=3.12"`, deps
  `claude-agent-sdk>=0.2.96`, `python-dotenv>=1.0.0`, `tzdata>=2024.1`; `[tool.ruff] line-length = 100`.
- **MIRROR**: `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/pyproject.toml`
- **VALIDATE**: `uvx ruff check $ENGINE/payload/pyproject.toml` (parses)

### Task 3: CREATE `$ENGINE/payload/scripts/config.py`
- **ACTION**: CREATE path/const resolution.
- **IMPLEMENT**: `ROOT_DIR`, `CATALOG_DIR = ROOT_DIR/"catalog"`, `REPORTS_DIR`, `LAST_EXTRACT_FILE`,
  `LOCK_FILE = scripts/co-extract.lock`, `STATE_FILE`, `load_cfg()`. Disjoint filenames from other engines.
- **MIRROR**: `knowledge-base/scripts/config.py:30-40`
- **GOTCHA**: payload scripts resolve siblings via `sys.path`, not package imports (see `plugins/CLAUDE.md`).
- **VALIDATE**: `python3 -c "import sys; sys.path.insert(0,'$ENGINE/payload/scripts'); import config"`

### Task 4: CREATE `$ENGINE/payload/scripts/utils.py`
- **ACTION**: CREATE pure age-gate + helpers.
- **IMPLEMENT**: `should_extract(now, last_ts, age_hours, has_new_source, in_wt, lock_fresh) -> bool`
- **MIRROR**: `knowledge-compiler/.../scripts/utils.py` `should_compile` (same truth table)
- **VALIDATE**: covered by Task 16 unit test

### Task 5: CREATE `$ENGINE/payload/scripts/shards.py`
- **ACTION**: CREATE shard builder for ~30 parallel units.
- **IMPLEMENT**: `build_shards(cfg) -> list[Shard]` where `Shard = {framework, key, title, scope_hint}`.
  Sharding target ~30:
  - **GDPR**: by chapter/article-group → ~10 shards (Ch. I–XI; e.g. principles Art.5–11, rights Art.12–23, controller/processor Art.24–43, transfers Art.44–50).
  - **SOC 2**: CC1–CC9 + Availability + Confidentiality + Processing Integrity + Privacy → ~9 shards.
  - **ISO 27001 Annex A (2022)**: Organizational (37) split ×2, People (8), Physical (14), Technological (34) split ×3 → ~11 shards.
  - Filter to `cfg["frameworks"]`.
- **GOTCHA**: shard granularity drives agent count; keep total ≈30, each shard small enough for one `max_turns=30` agent.
- **VALIDATE**: unit test asserts `len(build_shards(default_cfg))` is in `[27, 33]` and shards are unique.

### Task 6: CREATE `$ENGINE/payload/AGENTS.md`
- **ACTION**: CREATE the extractor/validator constitution.
- **IMPLEMENT**: constraint schema (`{id, framework, title, requirement, applies_when, check, source_ref}`),
  ID convention (`GDPR-ART5-01`, `SOC2-CC6-03`, `ISO-A8-12`), paraphrase-not-verbatim rule (copyright),
  `applies_when` predicate style (so the validator can decide applicability to a plan), and dedup rules.
- **MIRROR**: `plugins/neurawork-cc-harness/engines/knowledge-compiler/payload/AGENTS.md` (tone/structure)
- **VALIDATE**: markdown lints clean; reviewed against schema used in extract.py.

### Task 7: CREATE `$ENGINE/payload/scripts/extract.py`
- **ACTION**: CREATE the parallel fan-out extractor.
- **IMPLEMENT**: `extract_one(shard, cfg)` mirroring `compile_one()` (query + `ClaudeAgentOptions`),
  writing `catalog/<framework>.json` entries for its shard; `extract_all(shards, cfg)` with
  `asyncio.Semaphore(cfg["max_concurrency"])` + `asyncio.gather(..., return_exceptions=True)`;
  `main()` calls `assert_in_repo_not_dotclaude` on `CATALOG_DIR`, runs one `asyncio.run(extract_all(...))`,
  merges shard outputs into per-framework JSON + rebuilds `catalog/index.md`, writes completion stamp.
- **MIRROR**: `compile.py:95-189` for the agent body + stamp; NEW: gather/semaphore fan-out.
- **GOTCHA**: concurrent agents writing the SAME `<framework>.json` will race — each agent writes a
  per-shard temp file (`catalog/.shards/<framework>-<key>.json`); `main()` merges after gather. Do NOT
  let 30 agents `Edit` one file.
- **GOTCHA**: `return_exceptions=True` — a failed shard must be logged loudly and cause non-zero exit if
  any shard failed (per silent-failure policy), not silently dropped.
- **VALIDATE**: `uvx ruff check $ENGINE/payload/scripts/extract.py` + `python3 -c "import ast,pathlib; ast.parse(pathlib.Path('$ENGINE/payload/scripts/extract.py').read_text())"`

### Task 8: CREATE `$ENGINE/payload/scripts/precheck.py`
- **ACTION**: CREATE fast deterministic (no-LLM) structural plan check.
- **IMPLEMENT**: `precheck(plan_path, catalog_dir) -> {frameworks_expected, has_compliance_section, referenced_ids, missing_mandatory_ids}`.
  Parses the plan markdown (reuse section names from prp-implement's parse list), detects whether a
  `## Compliance` section exists and which constraint IDs are referenced.
- **GOTCHA**: read-only; plan lives under `.claude/PRPs/` — `repo_guard` does NOT block reads (verified),
  but never WRITE under `.claude/`.
- **VALIDATE**: unit test with a fixture plan asserting missing-ID detection.

### Task 9: CREATE `$ENGINE/payload/scripts/validate.py`
- **ACTION**: CREATE deep LLM validator (spawned detached by the hook / slash command).
- **IMPLEMENT**: single `query()` agent (mirror compile_one) given the plan text + catalog + AGENTS.md
  validation rules; writes `compliance-base/reports/<plan-stem>.md` listing addressed vs uncovered
  mandatory constraints with rationale. Accepts plan path as argv.
- **MIRROR**: `claudemd-lerner/.../scripts/update.py` argv+spawn shape; `compile_one` SDK body.
- **VALIDATE**: `uvx ruff check` + ast parse (no LLM call in test).

### Task 10: CREATE `$ENGINE/payload/hooks/co-session-start.py`
- **ACTION**: CREATE session-start injector + age-gated re-extract spawn.
- **IMPLEMENT**: `recursion_guard()`; `build_context()` = `catalog/index.md` tail + applicable-framework
  note; `maybe_spawn_extract(age_hours)` mirroring `maybe_spawn_update`; emit `hookSpecificOutput`.
- **MIRROR**: `knowledge-base/hooks/session-start.py`
- **VALIDATE**: `python3 hooks/co-session-start.py < /dev/null` prints valid JSON with `hookEventName: SessionStart` (no crash when catalog absent).

### Task 11: CREATE `$ENGINE/payload/hooks/co-post-tooluse.py`
- **ACTION**: CREATE validator hook (NEW `PostToolUse` event).
- **IMPLEMENT**: `recursion_guard()`; `read_hook_input()`; proceed only if tool ∈ {Write, Edit} and target
  path matches `.claude/PRPs/plans/*.plan.md`; run `precheck()` inline; if `validate_mode == "warn"` emit
  `additionalContext` summarizing `missing_mandatory_ids`; spawn detached `scripts/validate.py <plan>` for
  the deep report; if `validate_mode == "block"` and mandatory gaps exist, emit the blocking decision per
  the hooks doc. No-op fast when tool/path doesn't match.
- **MIRROR**: input handling from `session-end.py` (`read_hook_input`, worktree guard, detached `Popen`).
- **GOTCHA**: `PostToolUse` payload shape (tool name + tool input path) is NOT exemplified in this repo —
  verify field names against the hooks doc before parsing.
- **GOTCHA**: hard 15s timeout — inline path must stay deterministic + fast; all LLM work is the detached spawn.
- **VALIDATE**: feed a synthetic PostToolUse JSON on stdin (Write to a plan path) → asserts JSON output / exit 0.

### Task 12: CREATE `$ENGINE/recon.py`
- **ACTION**: CREATE read-only recon (fresh vs adopt, catalog presence).
- **MIRROR**: `plugins/neurawork-cc-harness/engines/knowledge-compiler/recon.py` + `_shared/recon.py` RECON_JSON contract.
- **VALIDATE**: `python3 $ENGINE/recon.py` in a temp repo emits parseable RECON_JSON (covered by Task 15).

### Task 13: CREATE `$ENGINE/install.py`
- **ACTION**: CREATE install machinery.
- **IMPLEMENT**: `_is_adopt`, `_copy_code` (incl. `_shared` refresh), `_scaffold` (create `catalog/`,
  `reports/`, `.shards/`, `.gitignore` for state/reports only if absent), `_hooks(cdir)` returning
  `SessionStart` + `PostToolUse` co- tuples, `main()` with `assert_in_repo_not_dotclaude` + `merge_hooks`.
- **MIRROR**: `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py` end-to-end.
- **GOTCHA**: `catalog_dir` default `compliance-base` at repo ROOT — never under `.claude/`.
- **VALIDATE**: Task 15 subprocess install test.

### Task 14: CREATE skill + commands + register in plugin.json
- **ACTION**: CREATE `skills/compliance-compiler/SKILL.md`, `commands/co-extract.md`, `commands/co-validate.md`;
  UPDATE `.claude-plugin/plugin.json`.
- **MIRROR**: existing `skills/knowledge-compiler/SKILL.md`, `commands/kc-compile.md`, and the `plugin.json` entries.
- **GOTCHA**: use fully-qualified skill/command names; keep `co-` prefix disjoint.
- **VALIDATE**: `python3 -c "import json,pathlib; json.loads(pathlib.Path('plugins/neurawork-cc-harness/.claude-plugin/plugin.json').read_text())"`

### Task 15: CREATE `$ENGINE/tests/test_install_recon.py`
- **ACTION**: CREATE install/recon tests.
- **IMPLEMENT**: temp git repo + subprocess `install.py`; assert `compliance-base/catalog/` scaffolded,
  `.claude/settings.json` has `SessionStart` AND `PostToolUse` co- entries, idempotent reinstall adds no
  duplicate hooks and does not clobber an existing catalog file.
- **MIRROR**: `plugins/neurawork-cc-harness/engines/knowledge-compiler/tests/test_install_recon.py:38-102`
- **VALIDATE**: `python3 -m unittest discover -s compliance-compiler/tests` (from `engines/`)

### Task 16: CREATE `$ENGINE/tests/test_shards_precheck.py`
- **ACTION**: CREATE pure-logic tests.
- **IMPLEMENT**: `build_shards` count/uniqueness/framework-filter; `should_extract` truth table;
  `precheck` missing-ID detection on a fixture plan.
- **MIRROR**: `test_utils_trigger.py` parametrized style.
- **VALIDATE**: `python3 -m unittest discover -s compliance-compiler/tests`

### Task 17: UPDATE root `CLAUDE.md`
- **ACTION**: UPDATE architecture + commands sections to document the third engine, `compliance-base/`
  self-host, `/co-extract` + `/co-validate`, and the `co-` hook prefix decision.
- **MIRROR**: existing engine bullets in `CLAUDE.md:54-104`.
- **GOTCHA**: surgical edit — do not restructure unrelated sections.
- **VALIDATE**: `git diff CLAUDE.md` shows only additive engine documentation.

---

## Testing Strategy

### Unit Tests to Write

| Test File | Test Cases | Validates |
|-----------|-----------|-----------|
| `compliance-compiler/tests/test_install_recon.py` | fresh scaffold, hooks present (SessionStart+PostToolUse), idempotent reinstall, catalog not clobbered | Install machinery |
| `compliance-compiler/tests/test_shards_precheck.py` | shard count ≈30, unique, framework filter; `should_extract` gate; `precheck` missing-ID detection | Pure logic |

### Edge Cases Checklist

- [ ] Catalog absent → `co-session-start.py` injects gracefully, no crash
- [ ] `PostToolUse` fires on a NON-plan write → hook no-ops fast
- [ ] `PostToolUse` fires on a plan with no `## Compliance` section → all mandatory IDs reported missing
- [ ] One extraction shard's agent fails → logged loudly, non-zero exit, other shards still written
- [ ] Two shards target same framework → per-shard temp files, no write race, correct merge
- [ ] `frameworks` config subset (e.g. only `gdpr`) → only GDPR shards built
- [ ] Reinstall (ADOPT) → code refreshed, existing `catalog/*.json` preserved
- [ ] Worktree session → no re-extract spawned (mirror worktree guard)
- [ ] Plan path under `.claude/` → validator READS it (allowed), never writes there

---

## Validation Commands

Run from `plugins/neurawork-cc-harness/engines/` unless noted.

### Level 1: STATIC_ANALYSIS
```bash
cd plugins/neurawork-cc-harness/engines && uvx ruff check
```
**EXPECT**: Exit 0, no errors.

### Level 2: UNIT_TESTS
```bash
cd plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s _shared/tests
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: All pass. No network/LLM calls.

### Level 3: FULL_SUITE (no regressions in the other two engines)
```bash
cd plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s knowledge-compiler/tests
python3 -m unittest discover -s claudemd-lerner/tests
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: All pass.

### Level 4: INSTALL SMOKE (self-host into this repo)
```bash
python3 plugins/neurawork-cc-harness/engines/compliance-compiler/install.py --catalog-dir compliance-base
python3 -c "import json,pathlib; s=json.loads(pathlib.Path('.claude/settings.json').read_text()); assert 'PostToolUse' in s['hooks']; assert 'SessionStart' in s['hooks']"
uv sync --directory compliance-base
```
**EXPECT**: `compliance-base/catalog/` created; both hook events registered; deps resolve.

### Level 5: EXTRACTION DRY-RUN (LLM — operator-run, needs API key; NOT in CI)
```bash
ANTHROPIC_API_KEY=... uv run --directory compliance-base python scripts/extract.py --frameworks gdpr --dry-run
```
**EXPECT**: builds GDPR shards, prints agent plan (dry-run makes no LLM call). Full run produces `catalog/gdpr.json`.

### Level 6: MANUAL_VALIDATION
1. Run full extraction: `uv run --directory compliance-base python scripts/extract.py` → inspect `catalog/index.md` + the three JSONs for coverage.
2. Write a throwaway plan with a PII-storing feature and no `## Compliance` section under `.claude/PRPs/plans/` → confirm `co-post-tooluse.py` reports uncovered GDPR data-residency constraint and a `reports/` file appears.

---

## Acceptance Criteria

- [ ] `compliance-compiler` engine mirrors the two existing engines' structure exactly
- [ ] `scripts/extract.py` fans out ~30 shard agents via `asyncio.gather` + semaphore; per-shard temp files, merged without races
- [ ] Catalog written to `compliance-base/catalog/` at repo root (passes `repo_guard`), tracked in git
- [ ] Constraints follow the AGENTS.md schema with stable IDs across the three frameworks
- [ ] `co-post-tooluse.py` runs on plan-file writes: inline structural check + detached deep validate + advisory report
- [ ] `/co-extract` and `/co-validate` commands + skill registered in `plugin.json`
- [ ] Level 1–4 validation pass with exit 0; no regressions in the other two engines' tests
- [ ] Root `CLAUDE.md` documents the third engine
- [ ] No verbatim copyrighted standard text committed; paraphrase + IDs only

---

## Completion Checklist

- [ ] All 17 tasks completed in order
- [ ] Level 1: `ruff` clean
- [ ] Level 2: compliance-compiler unit tests pass
- [ ] Level 3: all three engines' suites pass (no regressions)
- [ ] Level 4: install smoke registers both hook events, deps resolve
- [ ] Level 5/6: operator-run extraction + validator manual check done
- [ ] Acceptance criteria met

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 30 agents race-writing one catalog file | HIGH | HIGH | Per-shard temp files in `catalog/.shards/`; single-threaded merge in `main()` after `gather` |
| `PostToolUse` payload shape unknown (no repo example) | MED | HIGH | Read Claude Code hooks doc first; unit-test with synthetic stdin; fail-open (no-op) on unexpected shape |
| ISO/SOC2 copyright — can't ship source text | HIGH | MED | Paraphrase-only + control IDs; operator supplies source; documented in NOT Building + AGENTS.md |
| LLM cost/time of ~30 agents | MED | MED | `max_concurrency` cap; `extract_age_hours=168` (weekly) gate; `--frameworks` subset; `--dry-run` |
| Hook 15s timeout vs LLM validation | HIGH | MED | Inline = deterministic precheck only; all LLM work detached via `Popen` (mirror existing spawn pattern) |
| Validator false "gap" noise annoys devs | MED | MED | `validate_mode: "warn"` default (advisory, non-blocking); `applies_when` predicates scope constraints to relevant plans |
| Catalog drift from evolving standards | LOW | MED | Age-gated re-extract + `co-extract` command; catalog is tracked/reviewable in git |
| Silent shard failure hides missing constraints | MED | HIGH | `return_exceptions=True` results logged loudly; any failure → non-zero exit (silent-failure policy) |

---

## Notes

- **Why a new engine, not a Workflow-tool script**: the user asked for it to *belong to the
  neurawork coding harness* and live in this repo. The harness's unit of distribution is an
  engine (payload + hooks + skill + commands), so the extraction fan-out lives inside
  `scripts/extract.py` using `claude-agent-sdk` — the same SDK the other engines already use —
  rather than the interactive `Workflow` tool. This keeps it installable, testable, and hook-driven.
- **Prefix decision**: `co-` for hooks/commands (disjoint from bare `knowledge-compiler` and
  `cl-` `claudemd-lerner` markers) so `merge_hooks` never treats them as the same entry. The
  validator additionally uses a brand-new event (`PostToolUse`) not touched by the other engines.
- **Self-host dir**: `compliance-base/` at repo root, mirroring `knowledge-base/`. Tracked:
  `catalog/*.json` + `catalog/index.md`. Gitignored: `catalog/.shards/`, `reports/`, `scripts/*.lock`,
  `scripts/last-extract.json`, `scripts/state.json`.
- **Validator scope is plans only** per the decision. Extending to code/diffs (a `PreToolUse`
  or `SessionEnd` mode over the git diff) is a clean future addition — same catalog, new checker.
- **Open item for implementation**: confirm the exact `PostToolUse` JSON field names (tool name +
  tool-input file path) from the Claude Code hooks doc before writing `co-post-tooluse.py` — this
  repo has no existing example to copy.
```
