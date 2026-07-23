"""Derive per-framework capabilities from the constraint catalog — parallel agents.

Reads ``catalog/<framework>.json`` (the extracted constraints) and, per framework,
fans out one Claude Agent SDK agent to CLUSTER its constraints into capabilities
(concrete technical building blocks), then one agent per unique capability to map
it to greenfield-2026 STACK components. A deterministic verify gate (pure set math,
no LLM) then checks every mandatory constraint is covered by some capability; an
uncovered mandatory id fails the run. Outputs ``catalog/capabilities.json`` +
``catalog/capabilities.md`` and refreshes ``catalog/index.md``.

Per-capability shard files under ``catalog/.shards/`` avoid write races. A framework
whose ``catalog/<fw>.json`` is unchanged since the last run (content hash in
``state.json``) is skipped and its existing capabilities reused.

Usage:
    uv run python scripts/capabilities.py                    # all configured frameworks
    uv run python scripts/capabilities.py --frameworks gdpr  # subset
    uv run python scripts/capabilities.py --all              # ignore hashes, rebuild all
    uv run python scripts/capabilities.py --dry-run          # show the plan, no LLM
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

import cap_lib
from config import (
    AGENTS_FILE,
    CATALOG_DIR,
    FRAMEWORK_TITLES,
    INDEX_FILE,
    ROOT_DIR,
    SHARDS_DIR,
    load_cfg,
    now_iso,
    today_iso,
)
from utils import catalog_file, file_hash, load_state, save_state

from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude

CAPABILITIES_JSON = CATALOG_DIR / "capabilities.json"
CAPABILITIES_MD = CATALOG_DIR / "capabilities.md"


def _cluster_shard_path(fw: str) -> Path:
    return SHARDS_DIR / f"cap-{fw}.json"


def _stack_shard_path(slug: str) -> Path:
    return SHARDS_DIR / f"stack-{slug}.json"


def _constitution() -> str:
    return AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""


def _build_cluster_prompt(fw: str, shard_path: Path) -> str:
    return f"""You are a compliance capability agent. Cluster the constraints of ONE
framework into capabilities, following the constitution exactly.

## Constitution (AGENTS.md)

{_constitution()}

## Your task

- Framework: {fw} ({FRAMEWORK_TITLES.get(fw, fw)})
- Read the constraint catalog with the Read tool: {catalog_file(fw)}

Cluster ALL of that framework's constraints into CAPABILITIES — concrete technical
building blocks a greenfield software system implements to satisfy them (e.g.
"immutable audit logging", "data-subject request handling", "encryption in transit",
"RBAC & least privilege").

Rules:
- Every constraint id in the catalog MUST appear in exactly one capability's
  "satisfies" list. Drop none; duplicate none.
- Each capability's "category" must be one of: {", ".join(cap_lib.CATEGORIES)}.
- Aim for 15-25 capabilities.

Write a single JSON array of objects to exactly this file, using the Write tool, and
write nothing else:

    {shard_path}

Each object: {{"name": str, "category": str, "description": str, "satisfies": [str]}}.
Output only the JSON array as the file's content — no prose, no other files. Ensure
valid JSON (double quotes, no trailing commas)."""


def _build_stack_prompt(cap: dict, shard_path: Path) -> str:
    return f"""You are a greenfield software-architecture agent. Year: 2026.

For this compliance capability, recommend concrete, current (2025-2026) software
components / tools / services that implement it in a NEW build:

- Capability: {cap.get("name", "")}
- Description: {cap.get("description", "")}
- Category: {cap.get("category", "")}

Rules:
- 2-4 components, widely-adopted and well-supported.
- Mark each component "kind" as "open-source" or "managed".
- One-line "why" per component.

Write a single JSON object to exactly this file, using the Write tool, and write
nothing else:

    {shard_path}

Object: {{"capability": "{cap.get("name", "")}", "components": [{{"name": str,
"kind": str, "why": str}}], "notes": str}}.
Output only the JSON object as the file's content — no prose, no other files. Ensure
valid JSON (double quotes, no trailing commas)."""


async def cluster_one(fw: str, cfg: dict) -> dict:
    """Run one framework's cluster agent. Returns a result dict; raises on failure."""
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    shard_path = _cluster_shard_path(fw)
    if shard_path.exists():
        shard_path.unlink()  # existence proves this run wrote it

    cost = 0.0
    async for message in query(
        prompt=_build_cluster_prompt(fw, shard_path),
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
        raise RuntimeError(f"cluster {fw}: agent wrote no shard file")
    try:
        parsed = json.loads(shard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"cluster {fw}: invalid JSON — {e}") from e
    if not isinstance(parsed, list):
        raise RuntimeError(f"cluster {fw}: shard is not a JSON array")
    return {"fw": fw, "capabilities": parsed, "cost": cost}


async def stack_one(cap: dict, cfg: dict) -> dict:
    """Run one capability's stack agent. Returns the component-rec dict; raises on failure."""
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    slug = cap_lib.capability_slug(cap["name"])
    shard_path = _stack_shard_path(slug)
    if shard_path.exists():
        shard_path.unlink()

    cost = 0.0
    async for message in query(
        prompt=_build_stack_prompt(cap, shard_path),
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
        raise RuntimeError(f"stack {slug}: agent wrote no shard file")
    try:
        parsed = json.loads(shard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"stack {slug}: invalid JSON — {e}") from e
    if not isinstance(parsed, dict):
        raise RuntimeError(f"stack {slug}: shard is not a JSON object")
    parsed.setdefault("capability", cap["name"])
    parsed["cost"] = cost
    return parsed


async def _fan_out(coros: list, cfg: dict) -> list:
    """Run coroutine thunks concurrently, capped by max_concurrency. Never raises."""
    sem = asyncio.Semaphore(int(cfg.get("max_concurrency", 12)))

    async def run(make):
        async with sem:
            return await make()

    return await asyncio.gather(*(run(m) for m in coros), return_exceptions=True)


def _cluster_all(frameworks: list[str], cfg: dict) -> list:
    thunks = [(lambda fw=fw: cluster_one(fw, cfg)) for fw in frameworks]
    return asyncio.run(_fan_out(thunks, cfg))


def _stack_all(caps: list[dict], cfg: dict) -> list:
    thunks = [(lambda c=c: stack_one(c, cfg)) for c in caps]
    return asyncio.run(_fan_out(thunks, cfg))


def _load_existing() -> dict:
    if CAPABILITIES_JSON.exists():
        try:
            return json.loads(CAPABILITIES_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"frameworks": {}}


def _constraint_meta(frameworks: list[str]) -> list[dict]:
    """Per-framework constraint counts for the index top table (from catalog headers)."""
    meta = []
    for fw in frameworks:
        path = catalog_file(fw)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        meta.append({
            "framework": fw,
            "count": data.get("count", len(data.get("constraints", []))),
            "mandatory": data.get("mandatory", 0),
            "generated": data.get("generated", ""),
        })
    return meta


def _write_json_atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Derive per-framework capabilities from the constraint catalog"
    )
    parser.add_argument("--frameworks", type=str,
                        help="Comma-separated subset (default: config frameworks)")
    parser.add_argument("--all", action="store_true",
                        help="Rebuild all frameworks, ignoring unchanged-catalog hashes")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan, no LLM")
    args = parser.parse_args()

    cfg = load_cfg()
    if args.frameworks:
        cfg["frameworks"] = [f.strip() for f in args.frameworks.split(",") if f.strip()]
    frameworks = cfg["frameworks"]

    try:
        assert_in_repo_not_dotclaude(CATALOG_DIR, ROOT_DIR.parent)
    except WriteGuardError as e:
        print(f"Refusing to write catalog: {e}")
        return 1

    existing = _load_existing()
    state = load_state()
    cap_state = state.setdefault("capabilities", {})

    to_run: list[tuple[str, str]] = []   # (framework, catalog_hash)
    reuse: dict[str, list[dict]] = {}     # framework -> existing capabilities
    for fw in frameworks:
        cf = catalog_file(fw)
        if not cf.exists():
            print(f"  ! {fw}: no catalog file — run extract.py first; skipping")
            continue
        h = file_hash(cf)
        prev = cap_state.get(fw, {})
        if (not args.all
                and prev.get("catalog_hash") == h
                and fw in existing.get("frameworks", {})):
            reuse[fw] = existing["frameworks"][fw]["capabilities"]
            print(f"  = {fw}: catalog unchanged — reusing existing capabilities")
        else:
            to_run.append((fw, h))

    if not to_run and not reuse:
        print("No catalog to derive from — run extract.py first.")
        return 1

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Frameworks: {', '.join(frameworks)}")
    print(f"  cluster: {', '.join(fw for fw, _ in to_run) or '(none)'}")
    print(f"  reuse:   {', '.join(reuse) or '(none)'}")
    if args.dry_run:
        return 0

    SHARDS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Cluster (parallel, one agent per framework) ──
    cluster_failures: list = []
    clusters: dict[str, list[dict]] = {}
    cluster_cost = 0.0
    if to_run:
        results = _cluster_all([fw for fw, _ in to_run], cfg)
        cluster_failures = [r for r in results if isinstance(r, Exception)]
        for r in results:
            if isinstance(r, dict):
                clusters[r["fw"]] = r["capabilities"]
                cluster_cost += r.get("cost", 0.0)
    for fw, caps in reuse.items():
        clusters[fw] = caps

    # ── Stack (parallel, one agent per unique fresh capability) ──
    seen: set[str] = set()
    fresh_unique: list[dict] = []
    for fw, _ in to_run:
        for c in clusters.get(fw, []):
            slug = cap_lib.capability_slug(c["name"])
            if slug not in seen:
                seen.add(slug)
                fresh_unique.append(c)

    stack_failures: list = []
    stacks: list[dict] = []
    # reused stacks first so a fresh recommendation wins on any slug clash
    for fw, caps in reuse.items():
        for c in caps:
            stacks.append({
                "capability": c["name"],
                "components": c.get("stack", []),
                "notes": c.get("stack_notes", ""),
            })
    if fresh_unique:
        results = _stack_all(fresh_unique, cfg)
        stack_failures = [r for r in results if isinstance(r, Exception)]
        stacks.extend(r for r in results if isinstance(r, dict))

    stack_cost = sum(s["cost"] for s in stacks if isinstance(s, dict) and "cost" in s)
    total_cost = cluster_cost + stack_cost

    # ── Assemble + deterministic verify ──
    catalog = cap_lib.assemble_catalog(clusters, stacks, generated=today_iso())
    uncovered = {fw: f["uncovered_mandatory_ids"]
                 for fw, f in catalog["frameworks"].items()
                 if f["uncovered_mandatory_ids"]}

    # ── Write outputs ──
    _write_json_atomic(CAPABILITIES_JSON, catalog)
    CAPABILITIES_MD.write_text(cap_lib.render_capabilities_md(catalog), encoding="utf-8")
    INDEX_FILE.write_text(
        cap_lib.render_index(_constraint_meta(frameworks), catalog), encoding="utf-8"
    )

    # ── Persist per-framework catalog hashes for successfully clustered frameworks ──
    for fw, h in to_run:
        if fw in clusters:
            cap_state[fw] = {"catalog_hash": h, "generated_at": now_iso()}
    state["total_cost"] = state.get("total_cost", 0.0) + total_cost
    save_state(state)

    total_caps = sum(f["capability_count"] for f in catalog["frameworks"].values())
    print(f"\nDerived {total_caps} capabilities across {len(catalog['frameworks'])} "
          f"frameworks. Cost: ${total_cost:.2f}.")
    for fw, f in catalog["frameworks"].items():
        print(f"  {fw}: {f['capability_count']} caps, "
              f"mandatory {f['mandatory_covered']}/{f['mandatory_total']} covered")

    failures = cluster_failures + stack_failures
    if failures:
        print(f"\n{len(failures)} agent(s) FAILED:")
        for e in failures:
            print(f"  - {e}")
    if uncovered:
        print("\nCOVERAGE GAP — mandatory constraints not covered by any capability:")
        for fw, ids in uncovered.items():
            print(f"  {fw}: {', '.join(ids)}")

    return 1 if (failures or uncovered) else 0


if __name__ == "__main__":
    raise SystemExit(main())
