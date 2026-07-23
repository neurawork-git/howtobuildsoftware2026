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
from utils import catalog_file, file_hash, load_constraints, load_state, save_state

from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude

CAPABILITIES_JSON = CATALOG_DIR / "capabilities.json"
CAPABILITIES_MD = CATALOG_DIR / "capabilities.md"


def _cluster_shard_path(fw: str) -> Path:
    return SHARDS_DIR / f"cap-{fw}.json"


def _stack_shard_path(slug: str) -> Path:
    return SHARDS_DIR / f"stack-{slug}.json"


def _delta_shard_path(fw: str) -> Path:
    return SHARDS_DIR / f"delta-{fw}.json"


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

LICENSE / COST POLICY (a company shipping a COMMERCIAL software product):
- Set "role" to "in-product" if the component is shipped IN / AS the customer-facing
  product, or "internal-infra" if it is operator-side tooling we run to
  build/observe/secure our OWN stack and never distribute to customers.
- "in-product" components MUST be self-hostable open-source under a product-embeddable
  license: MIT, Apache-2.0, BSD-2/3-Clause, ISC, MPL-2.0, PostgreSQL, Unlicense, CC0,
  Zlib (LGPL only if dynamically linked). NEVER pick a copyleft (GPL/AGPL),
  source-available (SSPL, BSL/BUSL, Elastic-2.0, Confluent Community, Redis RSAL,
  "Sustainable Use"), or proprietary/managed-SaaS component for an in-product role.
  If the obvious tool relicensed, use the OSS fork (Terraform->OpenTofu,
  Elasticsearch->OpenSearch, Redis->Valkey, Grafana in-product->…).
- "internal-infra" components may carry ANY license (incl. AGPL like Grafana) OR be
  proprietary — as long as they cost NO money at the start (a free tier or free
  self-hosting is fine: GitHub free, Terraform, AWS free-tier services). Do NOT pick a
  paid-only proprietary SaaS; prefer a free OSS self-hostable tool. Truly inherent
  operator dependencies (a cloud substrate/region, cloud compliance attestations, an
  EU Art.27 representative, physical badge/camera hardware) may stay proprietary.
- Set "kind" to "open-source" or "internal-infra" accordingly, and "license" to the
  component's real SPDX id (or "proprietary" / "inherent" for the kept exceptions).

Rules:
- 2-4 components, widely-adopted and well-supported.
- One-line "why" per component, including the license justification.

Write a single JSON object to exactly this file, using the Write tool, and write
nothing else:

    {shard_path}

Object: {{"capability": "{cap.get("name", "")}", "components": [{{"name": str,
"kind": str, "license": str, "role": str, "why": str}}], "notes": str}}.
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


def _build_delta_cluster_prompt(
    fw: str, existing_caps: list[dict], new_constraints: list[dict], shard_path: Path
) -> str:
    existing_summary = "\n".join(
        f"- {c['name']} [{c.get('category', '')}]: {c.get('description', '')[:160]}"
        for c in existing_caps
    )
    new_block = "\n".join(
        f"- {c['id']}: {c.get('title', '')} — {c.get('requirement', '')[:240]}"
        for c in new_constraints
    )
    return f"""You are a compliance capability agent. New constraints were added to ONE
framework. Fit ONLY these new constraints into the framework's EXISTING capabilities,
following the constitution exactly. Do NOT re-derive or rename the existing capabilities.

## Constitution (AGENTS.md)

{_constitution()}

## Framework: {fw} ({FRAMEWORK_TITLES.get(fw, fw)})

## Existing capabilities (reuse these — assign by EXACT name)

{existing_summary}

## New constraints to place

{new_block}

Rules:
- Every new constraint id above MUST be placed exactly once: either assigned to an
  existing capability (by its EXACT name from the list) or covered by a NEW capability.
- Prefer assigning to an existing capability; only create a new capability when none fits.
- Each new capability's "category" must be one of: {", ".join(cap_lib.CATEGORIES)}.
- Do NOT touch, rename, or re-describe existing capabilities; do NOT re-list old ids.

Write a single JSON object to exactly this file, using the Write tool, and write
nothing else:

    {shard_path}

Object: {{"assignments": {{"<existing capability name>": ["<new id>", ...]}},
"new_capabilities": [{{"name": str, "category": str, "description": str,
"satisfies": [str]}}]}}.
Output only the JSON object as the file's content — no prose, no other files. Ensure
valid JSON (double quotes, no trailing commas)."""


async def delta_cluster_one(
    fw: str, existing_caps: list[dict], new_constraints: list[dict], cfg: dict
) -> dict:
    """Place only the NEW constraints into a framework's existing capabilities.

    Returns ``{fw, assignments, new_capabilities, cost}``; raises on failure."""
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    shard_path = _delta_shard_path(fw)
    if shard_path.exists():
        shard_path.unlink()

    cost = 0.0
    async for message in query(
        prompt=_build_delta_cluster_prompt(fw, existing_caps, new_constraints, shard_path),
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
        raise RuntimeError(f"delta {fw}: agent wrote no shard file")
    try:
        parsed = json.loads(shard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"delta {fw}: invalid JSON — {e}") from e
    if not isinstance(parsed, dict):
        raise RuntimeError(f"delta {fw}: shard is not a JSON object")
    return {
        "fw": fw,
        "assignments": parsed.get("assignments", {}) or {},
        "new_capabilities": parsed.get("new_capabilities", []) or [],
        "cost": cost,
    }


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


def _delta_all(jobs: list[tuple[str, list[dict], list[dict]]], cfg: dict) -> list:
    thunks = [(lambda j=j: delta_cluster_one(j[0], j[1], j[2], cfg)) for j in jobs]
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

    to_run: list[tuple[str, str]] = []       # full rebuild: (framework, catalog_hash)
    reuse: dict[str, list[dict]] = {}          # framework -> existing capabilities (carry all)
    delta_jobs: list[dict] = []                # incremental frameworks (new/removed constraints)
    hash_refresh: dict[str, str] = {}          # framework -> hash to persist without any agent
    for fw in frameworks:
        cf = catalog_file(fw)
        if not cf.exists():
            print(f"  ! {fw}: no catalog file — run extract.py first; skipping")
            continue
        h = file_hash(cf)
        prev = cap_state.get(fw, {})
        existing_caps = existing.get("frameworks", {}).get(fw, {}).get("capabilities")
        if (not args.all and prev.get("catalog_hash") == h and existing_caps is not None):
            reuse[fw] = existing_caps
            print(f"  = {fw}: catalog unchanged — reusing existing capabilities")
        elif not args.all and existing_caps is not None:
            constraints = load_constraints([fw])
            current_ids = {c["id"] for c in constraints if c.get("id")}
            d = cap_lib.constraint_delta(current_ids, existing_caps)
            if d["unchanged"]:
                reuse[fw] = existing_caps
                hash_refresh[fw] = h
                print(f"  ~ {fw}: constraint id set unchanged — reusing, refreshing hash")
            else:
                new_ids = set(d["new_ids"])
                delta_jobs.append({
                    "fw": fw, "hash": h, "existing_caps": existing_caps,
                    "orphaned_ids": d["orphaned_ids"],
                    "new_constraints": [c for c in constraints if c.get("id") in new_ids],
                })
                print(f"  Δ {fw}: +{len(d['new_ids'])} new / -{len(d['orphaned_ids'])} "
                      f"orphaned constraint(s) — incremental")
        else:
            to_run.append((fw, h))

    if not to_run and not reuse and not delta_jobs:
        print("No catalog to derive from — run extract.py first.")
        return 1

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Frameworks: {', '.join(frameworks)}")
    print(f"  cluster: {', '.join(fw for fw, _ in to_run) or '(none)'}")
    print(f"  delta:   {', '.join(j['fw'] for j in delta_jobs) or '(none)'}")
    print(f"  reuse:   {', '.join(reuse) or '(none)'}")
    if args.dry_run:
        return 0

    SHARDS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Cluster (parallel, one agent per full-rebuild framework) ──
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

    # ── Delta cluster (parallel, one agent per incremental framework) ──
    delta_failures: list = []
    delta_cost = 0.0
    delta_succeeded: set[str] = set()
    delta_changed_names: dict[str, set[str]] = {}
    if delta_jobs:
        results = _delta_all(
            [(j["fw"], j["existing_caps"], j["new_constraints"]) for j in delta_jobs], cfg
        )
        delta_failures = [r for r in results if isinstance(r, Exception)]
        by_fw = {r["fw"]: r for r in results if isinstance(r, dict)}
        for j in delta_jobs:
            fw = j["fw"]
            delta_changed_names[fw] = set()  # empty ⇒ all caps carried (also the fail path)
            r = by_fw.get(fw)
            if r is None:
                clusters[fw] = j["existing_caps"]  # agent failed — carry data, don't refresh hash
                continue
            delta_cost += r.get("cost", 0.0)
            delta_succeeded.add(fw)
            pruned = cap_lib.prune_orphaned_ids(j["existing_caps"], j["orphaned_ids"])
            merged = cap_lib.merge_delta_capabilities(
                pruned, r["assignments"], r["new_capabilities"]
            )
            clusters[fw] = merged
            orig = {c["name"]: set(c.get("satisfies", [])) for c in j["existing_caps"]}
            for c in merged:
                sat = set(c.get("satisfies", []))
                if c["name"] not in orig or (sat - orig[c["name"]]):
                    delta_changed_names[fw].add(c["name"])  # new cap or gained an id ⇒ re-stack

    # ── Stack (parallel, one agent per unique capability that needs (re)stacking) ──
    seen: set[str] = set()
    restack: list[dict] = []

    def _queue_restack(c: dict) -> None:
        slug = cap_lib.capability_slug(c["name"])
        if slug not in seen:
            seen.add(slug)
            restack.append(c)

    for fw, _ in to_run:
        for c in clusters.get(fw, []):
            _queue_restack(c)
    for fw, changed in delta_changed_names.items():
        for c in clusters.get(fw, []):
            if c["name"] in changed:
                _queue_restack(c)

    # carried stacks (no agent) — reused frameworks + delta capabilities that did not change;
    # listed first so any freshly-stacked capability wins on a slug clash
    stacks: list[dict] = []
    for fw, caps in reuse.items():
        for c in caps:
            stacks.append({"capability": c["name"], "components": c.get("stack", []),
                           "notes": c.get("stack_notes", "")})
    for fw, changed in delta_changed_names.items():
        for c in clusters.get(fw, []):
            if c["name"] not in changed:
                stacks.append({"capability": c["name"], "components": c.get("stack", []),
                               "notes": c.get("stack_notes", "")})

    stack_failures: list = []
    if restack:
        results = _stack_all(restack, cfg)
        stack_failures = [r for r in results if isinstance(r, Exception)]
        stacks.extend(r for r in results if isinstance(r, dict))

    stack_cost = sum(s["cost"] for s in stacks if isinstance(s, dict) and "cost" in s)
    total_cost = cluster_cost + delta_cost + stack_cost

    # ── Assemble + deterministic verify (only the frameworks derived this run) ──
    fresh = cap_lib.assemble_catalog(clusters, stacks, generated=today_iso())
    uncovered = {fw: f["uncovered_mandatory_ids"]
                 for fw, f in fresh["frameworks"].items()
                 if f["uncovered_mandatory_ids"]}

    # Preserve frameworks NOT processed this run (subset --frameworks, or a failed
    # cluster) by carrying their existing entries over — never clobber good data.
    catalog = cap_lib.merge_preserving(existing, fresh)

    # ── Write outputs ──
    _write_json_atomic(CAPABILITIES_JSON, catalog)
    CAPABILITIES_MD.write_text(cap_lib.render_capabilities_md(catalog), encoding="utf-8")
    INDEX_FILE.write_text(
        cap_lib.render_index(_constraint_meta(list(catalog["frameworks"])), catalog),
        encoding="utf-8",
    )

    # ── Persist per-framework catalog hashes ──
    # full rebuild (cluster succeeded), delta run (agent succeeded), and delta-unchanged
    # frameworks (id set identical — refresh the hash so the next run is a fast reuse).
    # NEVER persist a hash for a framework that failed the coverage gate: leaving the old
    # hash in place means a plain re-run retries it automatically instead of seeing a hash
    # match, reusing the gapped catalog, and falsely reporting success (no --all needed).
    for fw, h in to_run:
        if fw in clusters and fw not in uncovered:
            cap_state[fw] = {"catalog_hash": h, "generated_at": now_iso()}
    for j in delta_jobs:
        if j["fw"] in delta_succeeded and j["fw"] not in uncovered:
            cap_state[j["fw"]] = {"catalog_hash": j["hash"], "generated_at": now_iso()}
    for fw, h in hash_refresh.items():
        if fw not in uncovered:  # provably gap-free, but keep the rule uniform
            cap_state[fw] = {"catalog_hash": h, "generated_at": now_iso()}
    state["total_cost"] = state.get("total_cost", 0.0) + total_cost
    save_state(state)

    total_caps = sum(f["capability_count"] for f in catalog["frameworks"].values())
    print(f"\nDerived {total_caps} capabilities across {len(catalog['frameworks'])} "
          f"frameworks. Cost: ${total_cost:.2f}.")
    for fw, f in catalog["frameworks"].items():
        print(f"  {fw}: {f['capability_count']} caps, "
              f"mandatory {f['mandatory_covered']}/{f['mandatory_total']} covered")

    failures = cluster_failures + delta_failures + stack_failures
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
