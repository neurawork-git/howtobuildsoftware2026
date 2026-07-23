# Feature: Capability-derivation engine (`capabilities.py`)

## Summary

Turn this session's one-off ultracode capability extraction into a repeatable, tracked script in the `compliance-compiler` engine. `capabilities.py` reads the constraint catalog (`catalog/{gdpr,soc2,iso27001}.json`), fans out parallel Claude Agent SDK agents to (a) cluster each framework's constraints into capabilities and (b) recommend greenfield-2026 stack components per capability, then applies a **deterministic** mandatory-coverage gate (pure set math, no LLM) and writes `catalog/capabilities.json` + `catalog/capabilities.md` and refreshes the "Derived capabilities" section of `catalog/index.md`. It mirrors `extract.py`'s fan-out and `precheck.py`'s deterministic-gate patterns exactly, adds content-hash idempotency (skip a framework whose catalog is unchanged), and ships in both the `payload/` source tree and the live `compliance-base/` self-host.

## User Story

As a NeuraWork engineer standing up a compliant greenfield service
I want a re-runnable engine that derives capabilities + stack recommendations from the tracked constraint catalog and fails if any mandatory constraint is uncovered
So that the capability catalog is a reproducible, verifiable artifact instead of a hand-run workflow output.

## Problem Statement

`catalog/capabilities.json` and `capabilities.md` exist but are **produced by no code** — their `method` field records "ultracode workflow … 83 agents", a one-off interactive run. Regenerating them after a constraint changes currently means re-running an ad-hoc multi-agent workflow by hand. There is no gate proving the capability layer still covers every mandatory constraint. Testable failure: change a constraint in `catalog/gdpr.json`, and nothing regenerates or re-verifies `capabilities.json`.

## Solution Statement

Add `scripts/capabilities.py` (+ a pure-logic `scripts/cap_lib.py`) to the engine, mirroring `extract.py`. Flow: **cluster** (one SDK agent per framework reads `catalog/<fw>.json`, writes a candidate-capability shard) → assemble unique capabilities in Python → **stack** (one SDK agent per unique capability writes a component-rec shard) → join in Python → **verify** (deterministic: `mandatory_ids − ⋃satisfies`; non-empty ⇒ record `uncovered_mandatory_ids` and exit 1) → write `capabilities.json`, `capabilities.md`, and refresh `index.md`. Idempotency via `file_hash(catalog/<fw>.json)` stored in `scripts/state.json`. Everything is written in both the `payload/` and `compliance-base/` trees, kept byte-identical.

## Metadata

| Field            | Value                                                              |
| ---------------- | ----------------------------------------------------------------- |
| Type             | NEW_CAPABILITY                                                    |
| Complexity       | MEDIUM                                                            |
| Systems Affected | `compliance-compiler` engine (payload + self-host), tests         |
| Dependencies     | `claude-agent-sdk>=0.2.96` (already declared); Python ≥3.12; `uv` |
| Estimated Tasks  | 8                                                                 |

---

## UX Design

### Before State
```
┌────────────────────┐     one-off, interactive      ┌──────────────────────┐
│ catalog/*.json      │  ── ultracode Workflow ─────► │ capabilities.json/.md │
│ (359 constraints)   │     (83 agents, by hand)      │ (untracked provenance)│
└────────────────────┘                                └──────────────────────┘
        │
        └─ constraint changes ─► NOTHING regenerates; no coverage gate

USER_FLOW: engineer hand-runs a multi-agent workflow; assembles JSON manually.
PAIN_POINT: not reproducible, no `uv run` entry, no mandatory-coverage verification.
DATA_FLOW: catalog → (manual agents) → manual Python assembly → files.
```

### After State
```
┌────────────────────┐   uv run … scripts/capabilities.py                     ┌──────────────────────┐
│ catalog/*.json      │ ─► cluster (3 SDK agents, 1/fw) ─► .shards/cap-<fw>.json │
│ (source of truth)   │        │  file_hash idempotency skips unchanged fw       │
└────────────────────┘        ▼                                                  │
                       assemble unique caps (Python)                             │
                              │                                                  │
                              ▼                                                  │
                       stack (N SDK agents, 1/cap) ─► .shards/stack-<slug>.json  │
                              │                                                  ▼
                              ▼                                     ┌──────────────────────┐
                       join + VERIFY (deterministic set math) ────► │ capabilities.json/.md │
                              │  uncovered mandatory ⇒ exit 1        │ + index.md section    │
                              ▼                                      └──────────────────────┘
                       state.json (per-fw catalog_hash)

USER_FLOW: `uv run --directory compliance-base python scripts/capabilities.py`.
VALUE_ADD: reproducible, idempotent, gated (fails on any uncovered mandatory constraint).
DATA_FLOW: catalog → cluster agents → Python assemble → stack agents → Python join+verify → files.
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| `scripts/capabilities.py` | absent | `uv run … scripts/capabilities.py [--frameworks a,b] [--all] [--dry-run]` | Re-run the derivation on demand |
| `catalog/capabilities.json` | hand-run | script output with `generated`/hashes | Trustworthy provenance |
| Coverage | none | deterministic gate, exit 1 on uncovered mandatory | Regression caught immediately |
| Re-run on unchanged catalog | n/a | skipped via `file_hash` | Cheap no-op |

---

## Mandatory Reading

**CRITICAL: Implementation agent MUST read these before any task.**

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `compliance-base/scripts/extract.py` | 1-239 | The exact fan-out to MIRROR: `_build_prompt`, `extract_one`, `extract_all`, `_merge_framework`, `_write_index`, `main` |
| P0 | `compliance-base/scripts/cap_lib.py` target schema → `compliance-base/catalog/capabilities.json` | 1-40 | Output schema ORACLE the engine must reproduce |
| P0 | `compliance-base/catalog/capabilities.md` | 1-30 | Markdown render ORACLE |
| P1 | `compliance-base/scripts/precheck.py` | 41-50 | Deterministic-gate pattern for `coverage_gap` |
| P1 | `compliance-base/scripts/utils.py` | 18, 23-38, 48-76, 86-108 | `load_constraints`, `mandatory_ids`, `load_state`/`save_state`, `should_extract`, `CONSTRAINT_ID_RE` |
| P1 | `knowledge-base/scripts/utils.py` | 48-50 | `file_hash` to COPY into compliance `utils.py` |
| P1 | `compliance-base/scripts/config.py` | 19-67 | Path constants, `DEFAULT_CFG`, `load_cfg`, `FRAMEWORK_TITLES`, `now_iso`/`today_iso` |
| P1 | `plugins/neurawork-cc-harness/engines/_shared/repo_guard.py` | 26-50 | `assert_in_repo_not_dotclaude` write guard |
| P1 | `compliance-base/scripts/validate.py` | 31-37, 71-91 | Single-agent SDK shape + `_catalog_text` catalog-loading |
| P2 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_shards_precheck.py` | 1-75 | Pure-logic test template |
| P2 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py` | 1-104 | Install-copy assertion template |
| P2 | `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | 57-70 | Confirms `.py` files auto-copied — no install.py edit needed |
| P2 | `compliance-base/AGENTS.md` | all | Constitution to extend with a capability-derivation section |

**External Documentation:** none required — the Claude Agent SDK surface used (`query`, `ClaudeAgentOptions`, `ResultMessage`) is already used verbatim in `extract.py`/`validate.py`. No new library, no version research.

---

## Patterns to Mirror

**SDK_FAN_OUT (semaphore + gather, never raises):**
```python
# SOURCE: compliance-base/scripts/extract.py:119-129 — COPY THIS PATTERN
async def extract_all(shards: list[dict], cfg: dict) -> list:
    sem = asyncio.Semaphore(int(cfg.get("max_concurrency", 12)))
    async def run(shard: dict):
        async with sem:
            label = f"{shard['framework']}-{shard['key']}"
            print(f"  → extracting {label} ...")
            return await extract_one(shard, cfg)
    return await asyncio.gather(*(run(s) for s in shards), return_exceptions=True)
```

**SINGLE_AGENT_SDK_CALL (deferred import, query, write-then-verify):**
```python
# SOURCE: compliance-base/scripts/extract.py:78-116 — COPY THIS PATTERN
async def extract_one(shard: dict, cfg: dict) -> dict:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    shard_path = _shard_path(shard)
    if shard_path.exists():
        shard_path.unlink()  # existence proves this run wrote it
    cost = 0.0
    async for message in query(
        prompt=_build_prompt(shard, shard_path),
        options=ClaudeAgentOptions(
            cwd=str(ROOT_DIR),
            system_prompt={"type": "preset", "preset": "claude_code"},
            allowed_tools=["Read", "Write"],
            permission_mode="acceptEdits",
            max_turns=30,
            setting_sources=[],
            strict_mcp_config=True,
            model=(cfg.get("model") or None),
        ),
    ):
        if isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0
    if not shard_path.exists():
        raise RuntimeError(f"{shard['framework']}-{shard['key']}: agent wrote no shard file")
    parsed = json.loads(shard_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise RuntimeError("shard is not a JSON array")
    return {"shard": shard, "cost": cost, "count": len(parsed)}
```

**DETERMINISTIC_GATE (the verify stage — no LLM):**
```python
# SOURCE: compliance-base/scripts/precheck.py:41-50 + utils.py:69-76 — MIRROR
def precheck(plan_text, cfg, catalog_dir=None):
    constraints = load_constraints(cfg.get("frameworks", []), catalog_dir)
    mand = mandatory_ids(constraints)          # {c["id"] for c if c.get("mandatory", True)}
    refs = referenced_ids(plan_text)           # CONSTRAINT_ID_RE.findall over text
    return {"missing_mandatory_ids": sorted(mand - refs) if constraints else []}
```

**PROMPT_BUILDING (constitution interpolation + write-one-file instruction):**
```python
# SOURCE: compliance-base/scripts/extract.py:50-75 — MIRROR
def _build_prompt(shard, shard_path):
    constitution = AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""
    return f"""... {constitution} ...
Write a single JSON array ... to exactly this file, using the Write tool, and nothing else:
    {shard_path}
Output only the JSON array as the file's content — no surrounding prose, no other files."""
```

**MERGE / INDEX RENDER (pure Python, single write):**
```python
# SOURCE: compliance-base/scripts/extract.py:132-167 — MIRROR shape
def _merge_framework(fw): ...   # dedup by key into sorted dict, compute counts
def _write_index(catalogs):     # build markdown table line-by-line, one write_text
    lines = ["# Compliance Catalog", "", "| Framework | Constraints | Mandatory | Generated |", "|...|"]
    for cat in catalogs: lines.append(f"| {cat['framework']} | {cat['count']} | ...")
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")
```

**IDEMPOTENCY (content-hash skip + atomic state):**
```python
# SOURCE: knowledge-base/scripts/utils.py:48-50 — COPY into compliance utils.py
def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]

# SOURCE: knowledge-base/scripts/compile.py:142-162 — selection shape
#   for fw: if state["capabilities"].get(fw, {}).get("catalog_hash") != file_hash(catalog/<fw>.json): rerun

# SOURCE: compliance-base/scripts/utils.py:33-38 — atomic state write
def save_state(state):
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)
```

**REPO_GUARD (before any write):**
```python
# SOURCE: compliance-base/scripts/extract.py:188-193 — MIRROR
repo_root = ROOT_DIR.parent
try:
    assert_in_repo_not_dotclaude(CATALOG_DIR, repo_root)
except WriteGuardError as e:
    print(f"Refusing to write catalog: {e}")
    return 1
```

**MAIN / CLI (argparse, asyncio.run once, SystemExit):**
```python
# SOURCE: compliance-base/scripts/extract.py:177-239 — MIRROR
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frameworks"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ...
    results = asyncio.run(cluster_all(...))
    ...
    return 1 if failures or uncovered else 0
if __name__ == "__main__":
    raise SystemExit(main())
```

**PURE-LOGIC TEST TEMPLATE:**
```python
# SOURCE: tests/test_shards_precheck.py:1-16 — MIRROR
SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import cap_lib  # noqa: E402
import utils    # noqa: E402
```

---

## Files to Change

Every CREATE/UPDATE under `scripts/` or `AGENTS.md` must be applied to **BOTH** trees, byte-identical:
`plugins/neurawork-cc-harness/engines/compliance-compiler/payload/` (source of truth) **and** `compliance-base/` (live self-host). `install.py` needs no edit (it globs `.py`).

| File | Action | Justification |
|------|--------|---------------|
| `…/payload/scripts/cap_lib.py` | CREATE | Pure (SDK-free) logic: slug, assemble, coverage_gap, renderers — testable |
| `compliance-base/scripts/cap_lib.py` | CREATE | Live copy (byte-identical) |
| `…/payload/scripts/capabilities.py` | CREATE | The engine: cluster/stack SDK fan-out + deterministic verify + main() |
| `compliance-base/scripts/capabilities.py` | CREATE | Live copy (byte-identical) |
| `…/payload/scripts/utils.py` | UPDATE | Add `file_hash` (mirror knowledge-base utils) |
| `compliance-base/scripts/utils.py` | UPDATE | Live copy |
| `…/payload/AGENTS.md` | UPDATE | Add "Capability derivation" constitution section |
| `compliance-base/AGENTS.md` | UPDATE | Live copy |
| `…/tests/test_capabilities.py` | CREATE | Pure-logic tests for `cap_lib` |
| `…/tests/test_install_recon.py` | UPDATE | Assert `capabilities.py` + `cap_lib.py` copied on install |

Note: `catalog/.shards/` already exists and is gitignored; cluster/stack shards (`cap-<fw>.json`, `stack-<slug>.json`) land there and are not committed.

---

## NOT Building (Scope Limits)

- **LLM merge stage** — v1 used chunk-then-LLM-merge; this engine clusters **one agent per framework** (72–160 constraints fit one context), so no semantic merge agent. Simpler, and the deterministic gate catches any dropped id.
- **LLM verify agent** — coverage is pure set math; no adversarial agent in the script.
- **Auto-repair of uncovered constraints** — v1 fails and prints the gap; operator re-runs. (Future `Could`.)
- **Stack file / gap report** — that is PRD Phase 2, separate plan.
- **`validate.py` capability gate** — PRD Phase 3, separate plan.
- **New config keys / `config.default.json` changes** — reuse existing `model` + `max_concurrency`; avoids the "old installs don't get new default keys" trap.
- **New slash command / hook (`/co-capabilities`, SessionStart bootstrap)** — PRD Phase 4.
- **Live web research of component currency** — recs come from model knowledge (Jan-2026 cutoff), matching v1.

---

## Step-by-Step Tasks

Execute in order. Apply every `scripts/`+`AGENTS.md` change to **both trees**; a diff check validates parity.

### Task 1: UPDATE `utils.py` — add `file_hash` (both trees)
- **ACTION**: Add `file_hash` and its `hashlib` import to compliance `utils.py`.
- **IMPLEMENT**: copy verbatim from `knowledge-base/scripts/utils.py:48-50`:
  ```python
  def file_hash(path: Path) -> str:
      """First 16 hex chars of a file's SHA-256."""
      return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
  ```
- **MIRROR**: `knowledge-base/scripts/utils.py:48-50`. Ensure `import hashlib` present at top.
- **APPLY TO**: `…/payload/scripts/utils.py` and `compliance-base/scripts/utils.py`.
- **VALIDATE**:
  ```bash
  diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/utils.py compliance-base/scripts/utils.py
  python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import utils; print(utils.file_hash('compliance-base/catalog/gdpr.json'))"
  uvx ruff check compliance-base/scripts/utils.py
  ```

### Task 2: CREATE `cap_lib.py` — pure logic (both trees)
- **ACTION**: Create an SDK-free module holding all testable logic.
- **IMPLEMENT**:
  - `capability_slug(name: str) -> str` — lowercase, strip trailing parenthetical/`—` suffix (agents append these, seen this session), non-alnum → `-`, collapse. Used for stack-shard filenames AND the stack↔capability join key.
  - `assemble_catalog(clusters: dict[str,list], stacks: dict[str,dict], constraints_by_fw: dict[str,list], generated: str) -> dict` — build the exact `capabilities.json` schema: top-level `generated/source/method/stack_target/structure` + `frameworks.<fw>.{capability_count, mandatory_covered, mandatory_total, uncovered_mandatory_ids, capabilities:[{name,category,description,satisfies,stack,stack_notes}]}`. Join stack recs by `capability_slug`.
  - `coverage_gap(capabilities: list[dict], constraints: list[dict]) -> list[str]` — `sorted(mandatory_ids(constraints) - {id for cap in capabilities for id in cap["satisfies"]})`. **The verify gate.**
  - `render_capabilities_md(catalog: dict) -> str` — reproduce `catalog/capabilities.md` structure (summary table + per-`##`-framework, per-`###`-capability sections, `**Stack (greenfield 2026):**` line, `<sub>` id line).
  - `render_index(catalogs, capability_catalog) -> str` — full `index.md`: the constraints table (mirror `extract.py._write_index`) **plus** the "Derived capabilities" section.
- **MIRROR**: schema from `compliance-base/catalog/capabilities.json:1-40`; md from `compliance-base/catalog/capabilities.md`; index section from `compliance-base/catalog/index.md:9-17`; `mandatory_ids` import from `utils`.
- **CONSTRAINT**: no `claude_agent_sdk` import; stdlib + `utils`/`config` only (so tests need no SDK).
- **APPLY TO**: both trees (byte-identical).
- **VALIDATE**:
  ```bash
  diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/cap_lib.py compliance-base/scripts/cap_lib.py
  python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import cap_lib; print(cap_lib.capability_slug('Audit logging (SOC2 CC7)'))"
  uvx ruff check compliance-base/scripts/cap_lib.py
  ```
  **EXPECT**: slug prints `audit-logging`.

### Task 3: CREATE `capabilities.py` — the engine (both trees)
- **ACTION**: Create the SDK fan-out script.
- **IMPLEMENT**:
  - Imports mirror `extract.py:28-43` (from `config`: `AGENTS_FILE, CATALOG_DIR, ROOT_DIR, SHARDS_DIR, FRAMEWORK_TITLES, load_cfg, now_iso, today_iso`; from `utils`: `load_state, save_state, load_constraints, file_hash`; from `_shared.repo_guard`; `import cap_lib`).
  - `_cluster_shard_path(fw)` → `SHARDS_DIR/f"cap-{fw}.json"`; `_stack_shard_path(slug)` → `SHARDS_DIR/f"stack-{slug}.json"`.
  - `_build_cluster_prompt(fw, shard_path)` — instruct agent to **Read `catalog/<fw>.json`**, cluster ALL its constraints into capabilities (every id in exactly one `satisfies`; category from the fixed list), write a JSON array of `{name,category,description,satisfies}` to `shard_path` only. Interpolate `AGENTS.md`.
  - `_build_stack_prompt(cap, shard_path)` — greenfield-2026 component rec for one capability; write `{capability,components:[{name,kind,why}],notes}` to `shard_path`.
  - `cluster_one`/`stack_one` — copy `extract_one` shape verbatim (deferred SDK import, unlink-stale, `query()` with the exact `ClaudeAgentOptions`, verify file written + valid JSON).
  - `cluster_all`/`stack_all` — copy `extract_all` semaphore+gather+`return_exceptions=True`.
  - `main()`:
    1. `assert_in_repo_not_dotclaude(CATALOG_DIR, ROOT_DIR.parent)` (mirror extract.py:188-193).
    2. Resolve frameworks from `--frameworks` or `cfg["frameworks"]`.
    3. Idempotency: `state = load_state()`; per fw compute `file_hash(catalog/<fw>.json)`; skip fw whose stored `catalog_hash` matches AND already present in existing `capabilities.json` — unless `--all`.
    4. `--dry-run`: print which fw would run, exit 0 (mirror extract.py dry-run).
    5. `asyncio.run(cluster_all(fw_units, cfg))`; partition failures/ok (mirror extract.py:210-211).
    6. Read cluster shards → unique caps → `asyncio.run(stack_all(cap_units, cfg))`.
    7. Read stack shards; `catalog = cap_lib.assemble_catalog(...)`.
    8. **Verify**: for each fw `gap = cap_lib.coverage_gap(caps, constraints)`; set `uncovered_mandatory_ids`; if any gap across frameworks → print gap, set exit 1 (still write outputs so the gap is inspectable).
    9. Write `capabilities.json` (atomic tmp+replace), `capabilities.md` (`cap_lib.render_capabilities_md`), refresh `index.md` (`cap_lib.render_index`).
    10. Update `state["capabilities"][fw] = {"catalog_hash":…, "generated_at": now_iso()}`; `save_state`.
    11. Return `1 if failures or any_gap else 0`.
  - `if __name__ == "__main__": raise SystemExit(main())`.
- **GOTCHA**: agents append parentheticals to capability names → join stack by `capability_slug`, not exact string (this session hit exactly this).
- **GOTCHA**: no `load_dotenv` anywhere — SDK reads `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` from env itself; don't add a credential check.
- **APPLY TO**: both trees (byte-identical).
- **VALIDATE** (no LLM/network):
  ```bash
  diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/capabilities.py compliance-base/scripts/capabilities.py
  python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import capabilities"   # imports clean (SDK import is deferred)
  uv run --directory compliance-base python scripts/capabilities.py --dry-run
  uvx ruff check compliance-base/scripts/capabilities.py
  ```
  **EXPECT**: `--dry-run` lists frameworks and exits 0 without any SDK call.

### Task 4: UPDATE `AGENTS.md` — capability-derivation constitution (both trees)
- **ACTION**: Append a "## Capability derivation" section: capability = concrete technical building block; every constraint id maps to exactly one capability's `satisfies`; per-framework lists (overlap kept); fixed category vocabulary; stack recs = current greenfield-2026 components (2–4, `kind` = open-source|managed). Mirror the terse, rule-list tone of the existing extraction section.
- **MIRROR**: existing `compliance-base/AGENTS.md` extraction/schema sections.
- **APPLY TO**: both trees (byte-identical).
- **VALIDATE**:
  ```bash
  diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/AGENTS.md compliance-base/AGENTS.md
  grep -q "Capability derivation" compliance-base/AGENTS.md
  ```

### Task 5: CREATE `tests/test_capabilities.py` — pure-logic tests
- **ACTION**: Create `unittest` tests for `cap_lib` (no SDK, no network).
- **IMPLEMENT** (mirror `test_shards_precheck.py:1-16` import shim; `SCRIPTS = …/payload/scripts`):
  - `test_capability_slug` — strips parenthetical/`—` suffix, lowercases, hyphenates.
  - `test_coverage_gap_complete` — caps whose `satisfies` union covers all mandatory ids → `[]`.
  - `test_coverage_gap_missing` — drop one mandatory id from every `satisfies` → that id returned.
  - `test_assemble_catalog_schema` — assemble from tiny fixtures → assert top-level keys + `frameworks.gdpr.capabilities[0]` has `name/category/description/satisfies/stack/stack_notes`; stack joined by slug despite an appended parenthetical on the stack `capability` field.
  - `test_render_capabilities_md` — output contains the summary table header and a `### <cap name>` section.
- **MIRROR**: `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_shards_precheck.py`.
- **VALIDATE**:
  ```bash
  python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests -p 'test_capabilities.py'
  ```
  **EXPECT**: all tests pass, exit 0.

### Task 6: UPDATE `tests/test_install_recon.py` — assert new files copied
- **ACTION**: In `test_fresh_scaffold_and_hooks`, add assertions that install copies the new scripts.
- **IMPLEMENT**: alongside the existing `scripts/*.py` existence checks (`test_install_recon.py:53-65`), add:
  ```python
  self.assertTrue((cb / "scripts" / "capabilities.py").exists())
  self.assertTrue((cb / "scripts" / "cap_lib.py").exists())
  ```
- **MIRROR**: existing existence assertions in the same test.
- **VALIDATE**:
  ```bash
  python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests -p 'test_install_recon.py'
  ```
  **EXPECT**: install test passes (files auto-copied by `install.py`'s glob — no `install.py` edit needed).

### Task 7: Full engine test + lint
- **ACTION**: Run the whole compliance-compiler suite and lint both new files in both trees.
- **VALIDATE**:
  ```bash
  cd plugins/neurawork-cc-harness/engines
  python3 -m unittest discover -s compliance-compiler/tests
  python3 -m unittest discover -s _shared/tests
  cd - && uvx ruff check
  ```
  **EXPECT**: all tests pass; ruff clean (line-length 100).

### Task 8: (MANUAL, needs API key) Regenerate the catalog from code
- **ACTION**: Prove reproducibility end-to-end.
- **VALIDATE**:
  ```bash
  export ANTHROPIC_API_KEY=…            # or CLAUDE_CODE_OAUTH_TOKEN
  uv run --directory compliance-base python scripts/capabilities.py --all
  python3 -c "import json;d=json.load(open('compliance-base/catalog/capabilities.json'));\
print({k:(v['mandatory_covered'],v['mandatory_total'],len(v['uncovered_mandatory_ids'])) for k,v in d['frameworks'].items()})"
  uv run --directory compliance-base python scripts/capabilities.py   # second run: skips all (unchanged hashes), exit 0
  ```
  **EXPECT**: gdpr (109,109,0), soc2 (111,111,0), iso27001 (59,59,0); exit 0; second run reports skips.

---

## Testing Strategy

### Unit Tests to Write
| Test File | Test Cases | Validates |
|-----------|-----------|-----------|
| `tests/test_capabilities.py` | slug normalization; coverage gap (complete/missing); assemble schema + slug-join; md render | `cap_lib` pure logic |
| `tests/test_install_recon.py` (extend) | new scripts present after install | install copies `capabilities.py`+`cap_lib.py` |

### Edge Cases Checklist
- [ ] Capability name with appended parenthetical still joins to its stack shard (slug match)
- [ ] Mandatory id dropped from all `satisfies` → surfaced in `uncovered_mandatory_ids` and exit 1
- [ ] Unbuilt catalog (`catalog/<fw>.json` missing) → `load_constraints` yields none; script reports and exits non-zero, never crashes
- [ ] Unchanged catalog hash → framework skipped on re-run
- [ ] `--frameworks gdpr` runs only gdpr
- [ ] One cluster/stack agent failing (RuntimeError) does not abort siblings (`return_exceptions=True`), run exits 1
- [ ] `--dry-run` makes zero SDK calls

---

## Validation Commands

### Level 1: STATIC_ANALYSIS
```bash
uvx ruff check
python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import cap_lib, capabilities, utils"
```
**EXPECT**: exit 0, no errors.

### Level 2: UNIT_TESTS
```bash
python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests
```
**EXPECT**: all pass.

### Level 3: FULL_SUITE
```bash
cd plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s _shared/tests
python3 -m unittest discover -s knowledge-compiler/tests
python3 -m unittest discover -s claudemd-lerner/tests
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: all pass (no regressions in sibling engines).

### Level 4: TREE PARITY
```bash
for f in scripts/capabilities.py scripts/cap_lib.py scripts/utils.py AGENTS.md; do
  diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/$f compliance-base/$f || echo "DRIFT: $f"
done
```
**EXPECT**: no `DRIFT` lines.

### Level 5: DRY-RUN (no LLM)
```bash
uv run --directory compliance-base python scripts/capabilities.py --dry-run
```
**EXPECT**: lists frameworks, exit 0, no SDK call.

### Level 6: MANUAL (needs API key)
Task 8 above — full regeneration + idempotent second run.

---

## Acceptance Criteria
- [ ] `capabilities.py` + `cap_lib.py` exist in both trees, byte-identical (Level 4 clean)
- [ ] `--dry-run` runs with no SDK call, exit 0
- [ ] Deterministic `coverage_gap` gate: uncovered mandatory ⇒ exit 1 (unit-tested)
- [ ] Idempotency: unchanged catalog hash ⇒ framework skipped
- [ ] Levels 1–5 pass; no regressions in sibling engine tests
- [ ] Code mirrors `extract.py`/`precheck.py` naming, structure, deferred-SDK-import, atomic writes
- [ ] With API key (Task 8): reproduces 109/111/59 mandatory coverage, 0 uncovered

## Completion Checklist
- [ ] Tasks 1–7 done and validated in order
- [ ] Level 1 static analysis passes
- [ ] Level 2 unit tests pass
- [ ] Level 3 full suite passes (all four engines)
- [ ] Level 4 tree parity clean
- [ ] Level 5 dry-run clean
- [ ] Task 8 run at least once by an operator with credentials (or explicitly deferred)

---

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Payload/self-host drift (edit one tree only) | MED | MED | Level 4 diff gate in acceptance; every task says "both trees" |
| Cluster agent drops a mandatory id | MED | HIGH | Deterministic `coverage_gap` gate fails the run and prints the ids |
| Stack name drift breaks join | MED | LOW | Join by `capability_slug`, not exact string (unit-tested) |
| Non-deterministic re-runs churn tracked catalog | HIGH | MED | `file_hash` skip on unchanged catalog; human reviews diff before commit |
| One agent failure aborts the batch | LOW | MED | `return_exceptions=True` isolates failures (mirror extract.py) |
| Adding config keys silently missing on old installs | LOW | LOW | Reuse existing `model`/`max_concurrency`; add none |

---

## Compliance

**Scope**: This plan builds an internal batch tool (a Python script reading a local JSON catalog and writing derived JSON/Markdown). It processes no personal data, exposes no interface, and changes no runtime data flow — so the substantive runtime obligations of GDPR / SOC 2 / ISO 27001 (data-subject rights, operational trust-services controls, Annex-A controls) do **not** apply at this plan's scope.

**Relationship to the catalog is inverse and total**: this engine's whole purpose is to keep every mandatory constraint mapped to a capability. Its **deterministic coverage gate** (`cap_lib.coverage_gap`, Task 2/3, unit-tested Task 5) enforces that the union of capability `satisfies` lists covers **all 279 mandatory constraints** — GDPR 109/109, SOC 2 111/111, ISO 27001 59/59 — and **fails the run (exit 1) if any single mandatory id is uncovered**. So rather than referencing constraints piecemeal, this plan mechanically guarantees none is dropped.

**Self-application**: outputs stay inside the repo, never under `.claude/` (enforced by `repo_guard.assert_in_repo_not_dotclaude`, Task 3) — consistent with ISO-style asset/records governance the catalog itself encodes.

## Notes

- **Why deterministic verify, not an LLM agent**: coverage is a set-difference the script can compute exactly and cheaply; it's the real regression gate and is unit-testable without the SDK. The v1 ultracode verify-agent was an adversarial double-check appropriate to an interactive run, not a batch script.
- **Why one cluster agent per framework** (vs v1's chunk+merge): each framework's constraints (≤160) fit a single context; dropping the LLM-merge stage removes a semantic-dedup failure mode, and the deterministic gate guarantees nothing is lost regardless.
- **install.py needs no edit**: `_copy_code` globs `payload/scripts/*.py` (`install.py:63-65`), so new scripts ship automatically; the self-host copy is authored directly because `compliance-base/` is a live install target, not a symlink.
- **Confidence**: 9/10 — the fan-out, gate, atomic-write, and schema are all already present in-repo and reproduced verbatim; the only genuinely new code is `cap_lib` pure logic (fully unit-tested) and two prompt builders.
