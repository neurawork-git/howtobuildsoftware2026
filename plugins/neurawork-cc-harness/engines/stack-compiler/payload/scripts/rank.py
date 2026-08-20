"""Order each applicable capability's catalog components for ONE product — parallel agents.

Reads the same tracked product description ``scope.py`` scoped from, plus the
sibling compliance install's ``catalog/capabilities.json`` and ``catalog/stack.json``,
then fans out one Claude Agent SDK agent per framework to put that framework's
still-applicable capabilities' components in best-fit-first order, each with a
product-specific reason.

The pool is closed and complete: a ranking must name exactly the capability's
``options``, once each. Narrowing is the catalog's job and the human's at selection
time, never this pass's — so there is no adversarial challenge agent here as there
is in ``scope.py``. The claims worth checking (the pool matches, the licenses
satisfy the policy) are decidable by set math, and ``rank_lib.ranking_gate`` decides
them more reliably than a second LLM could.

Only a clean gate reaches the write, and the write goes through
``<compliance_dir>/scripts/stack.py --apply-ranking`` — the one schema owner for
``stack.json``. This engine creates no data artifact of its own.

Per-agent shard files under ``.shards/`` avoid write races. A run whose product
description is unchanged since the recorded ranking is skipped entirely.

Usage:
    uv run python scripts/rank.py                    # rank from product.md
    uv run python scripts/rank.py --product P.md     # rank from another description
    uv run python scripts/rank.py --all              # ignore the unchanged-product skip
    uv run python scripts/rank.py --dry-run          # show the plan, no LLM
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

import rank_lib
import scope_lib
from config import (
    AGENTS_FILE,
    REPORTS_DIR,
    ROOT_DIR,
    SHARDS_DIR,
    STATE_FILE,
    compliance_root,
    load_cfg,
    now_iso,
    product_file,
    today_iso,
)

# _shared/ and claude_agent_sdk are imported inside functions: neither exists in the
# plugin's payload/ tree, so the pure logic and the prompt builders below stay
# importable (and unit-testable) straight from payload/scripts.


# ── Prompts ───────────────────────────────────────────────────────────

def _constitution() -> str:
    return AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""


def build_rank_prompt(fw: str, caps: list[dict], product: str, shard_path: Path) -> str:
    """One framework's ranking prompt. Every component it must order is listed inline."""
    blocks = []
    for c in caps:
        components = "\n".join(
            f"    - name: {comp['name']}\n"
            f"      license: {comp['license'] or 'unknown'}\n"
            f"      role: {comp['role'] or 'unknown'}\n"
            f"      verdict: {comp['verdict'] or 'unknown'}\n"
            f"      why: {comp['why']}"
            for comp in c["components"]
        )
        blocks.append(
            f"- key: {c['key']}\n"
            f"  capability: {c['capability']}\n"
            f"  category: {c['category']}\n"
            f"  mandatory_linked: {str(bool(c['mandatory_linked'])).lower()}\n"
            f"  description: {c['description']}\n"
            f"  components ({len(c['components'])}, rank ALL of them):\n{components}"
        )
    listing = "\n".join(blocks)
    total = sum(len(c["components"]) for c in caps)
    return f"""You are a compliance stack-ranking agent. For ONE framework, put each
capability's components in best-fit-first order for THIS product, following the
constitution exactly.

## Constitution (AGENTS.md)

{_constitution()}

## Product description

{product}

## Framework: {fw} — {len(caps)} applicable capabilities, {total} components to order

{listing}

## Your task

For EACH of the {len(caps)} keys above, return its components ordered best-fit-first
for this product, each with a reason grounded in the product description.

Rules (the constitution governs; these are the ones that fail the run):
- Rank all {len(caps)} keys, using the EXACT key strings above. No others.
- For each key, return EXACTLY the components listed under it — every one, once
  each, spelled exactly as given. Never add a component, never leave one out. The
  pool is closed; narrowing it is not your decision.
- Every component needs a non-empty "rationale": one factual sentence naming why it
  sits in that position FOR THIS PRODUCT. Do not restate its "why" text back.
- Rank on fit to this product — deployment shape, data held, integrations, stated
  non-goals — not on general popularity.
- "verdict: replaced" means the component SUPERSEDED another during the license
  audit, never that it was rejected. Rank it on its merits like any other.
- Licenses are checked deterministically after this run. Never silently drop a
  component that looks license-incompatible: rank it last and say so in its reason.

Write a single JSON array to exactly this file, using the Write tool, and write
nothing else:

    {shard_path}

Each element: {{"key": str, "ranked": [{{"component": str, "rationale": str}}, ...]}}.
Output only the JSON array as the file's content — no prose, no other files. Ensure
valid JSON (double quotes, no trailing commas)."""


# ── Parsing ───────────────────────────────────────────────────────────

def parse_rank_shard(raw: object, expected_keys: set[str], fw: str) -> dict:
    """Validate one framework's rank shard into ``{key: [{component, rationale}]}``.

    The key set must match EXACTLY, for the same reason ``parse_scope_shard`` demands
    it. Component names are NOT checked against ``options`` here: that is the gate's
    job, so a pool mismatch is reported once, by one owner, with the full context.
    """
    if not isinstance(raw, list):
        raise TypeError(f"rank {fw}: shard is not a JSON array")
    rankings: dict[str, list[dict]] = {}
    for item in raw:
        if not isinstance(item, dict) or not item.get("key"):
            raise RuntimeError(f"rank {fw}: shard element without a key: {item!r}")
        key = str(item["key"])
        if key in rankings:
            raise RuntimeError(f"rank {fw}: duplicate ranking for {key}")
        ranked = item.get("ranked")
        if not isinstance(ranked, list) or not ranked:
            raise RuntimeError(f"rank {fw}: {key} carries no ranked components")
        entries: list[dict] = []
        for r in ranked:
            name = str((r or {}).get("component") or "").strip() if isinstance(r, dict) else ""
            if not name:
                raise RuntimeError(f"rank {fw}: {key} has an entry naming no component")
            entries.append({
                "component": name,
                "rationale": str((r or {}).get("rationale") or "").strip(),
            })
        rankings[key] = entries
    got = set(rankings)
    if missing := sorted(expected_keys - got):
        raise RuntimeError(f"rank {fw}: no ranking for {len(missing)} key(s): "
                           f"{', '.join(missing)}")
    if unknown := sorted(got - expected_keys):
        raise RuntimeError(f"rank {fw}: ranking for {len(unknown)} unknown key(s): "
                           f"{', '.join(unknown)}")
    return rankings


# ── Agents ────────────────────────────────────────────────────────────

async def _run_agent(prompt: str, shard_path: Path, cfg: dict) -> tuple[object, float]:
    """Run one SDK agent that must leave a JSON file at ``shard_path``."""
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    if shard_path.exists():
        shard_path.unlink()  # existence proves this run wrote it

    cost = 0.0
    async for message in query(
        prompt=prompt,
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
        raise RuntimeError(f"{shard_path.name}: agent wrote no shard file")
    try:
        return json.loads(shard_path.read_text(encoding="utf-8")), cost
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{shard_path.name}: invalid JSON — {e}") from e


async def rank_one(fw: str, caps: list[dict], product: str, cfg: dict) -> dict:
    """Order one framework's applicable capabilities. Returns ``{fw, rankings, cost}``."""
    shard_path = SHARDS_DIR / f"rank-{fw}.json"
    raw, cost = await _run_agent(build_rank_prompt(fw, caps, product, shard_path),
                                 shard_path, cfg)
    return {
        "fw": fw,
        "rankings": parse_rank_shard(raw, {c["key"] for c in caps}, fw),
        "cost": cost,
    }


async def _fan_out(thunks: list, cfg: dict) -> list:
    """Run coroutine thunks concurrently, capped by max_concurrency. Never raises."""
    sem = asyncio.Semaphore(int(cfg.get("max_concurrency", 12)))

    async def run(make):
        async with sem:
            return await make()

    return await asyncio.gather(*(run(m) for m in thunks), return_exceptions=True)


# ── State ─────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load state.json, or a fresh skeleton if absent/corrupt."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"total_cost": 0.0}


def save_state(state: dict) -> None:
    """Write state.json atomically (tmp + replace)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _load_json(path: Path) -> dict:
    """Read a JSON object, or ``{}`` if absent/corrupt. Never raises."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def already_ranked(stack: dict, product_hash: str) -> bool:
    """True when every APPLICABLE capability already carries this product's ranking."""
    applicable = [c for c in (stack.get("choices") or {}).values()
                  if (c or {}).get("applicable", True)]
    return bool(applicable) and all(
        c.get("ranked") and c.get("ranked_from") == product_hash for c in applicable
    )


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Order each applicable capability's catalog components for this product"
    )
    parser.add_argument("--product", type=str, metavar="PATH",
                        help="Product description to rank against (default: <stack_dir>/product.md)")
    parser.add_argument("--all", action="store_true",
                        help="Re-rank even when the product description is unchanged")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan, no LLM")
    args = parser.parse_args()

    cfg = load_cfg()
    comp = compliance_root(cfg)
    catalog_dir = comp / "catalog"
    capabilities_json = catalog_dir / "capabilities.json"
    stack_json = catalog_dir / "stack.json"
    stack_py = comp / "scripts" / "stack.py"

    if not comp.is_dir():
        print(f"No compliance install at {comp} — stack-compiler has nothing to rank. "
              "Install compliance-compiler first, or set 'compliance_dir' in config.json.")
        return 1
    if not capabilities_json.exists():
        print(f"No {capabilities_json} — run "
              f"`uv run --directory {comp.name} python scripts/capabilities.py` first")
        return 1
    if not stack_json.exists():
        print(f"No {stack_json} — run "
              f"`uv run --directory {comp.name} python scripts/stack.py --scaffold` first")
        return 1
    if not stack_py.exists():
        print(f"No {stack_py} — the compliance install is incomplete")
        return 1

    product_path = Path(args.product) if args.product else product_file(cfg)
    if not product_path.exists():
        print(f"No such product description: {product_path} — "
              "run `python scripts/scope.py` first, which scaffolds it.")
        return 1

    product = product_path.read_text(encoding="utf-8")
    if not product.strip():
        print(f"{product_path} is empty — describe the product, then re-run.")
        return 1
    ranked_from = scope_lib.product_hash(product)

    capabilities = _load_json(capabilities_json)
    stack = _load_json(stack_json)
    if not rank_lib.is_scoped(stack):
        print(f"{stack_json} carries no scoping decisions — run "
              f"`uv run --directory {ROOT_DIR.name} python scripts/scope.py` first. "
              "Ranking an unscoped stack would order every capability in the catalog.")
        return 1

    universe = rank_lib.rankable_universe(stack, capabilities)
    if not universe:
        print("Every capability was scoped out of this product — nothing to rank.")
        return 0

    by_fw: dict[str, list[dict]] = {}
    for u in universe:
        by_fw.setdefault(u["framework"], []).append(u)
    total_components = sum(len(u["components"]) for u in universe)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Ranking {total_components} components "
          f"across {len(universe)} applicable capabilities in {len(by_fw)} framework(s) "
          f"from {product_path} (hash {ranked_from})")
    for fw, caps in sorted(by_fw.items()):
        print(f"  {fw}: {len(caps)} capabilities, "
              f"{sum(len(c['components']) for c in caps)} components")
    if args.dry_run:
        return 0

    if not args.all and already_ranked(stack, ranked_from):
        print("Product description unchanged since the recorded ranking — nothing to do "
              "(use --all to force).")
        return 0

    from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude
    try:
        assert_in_repo_not_dotclaude(REPORTS_DIR, ROOT_DIR.parent)
    except WriteGuardError as e:
        print(f"Refusing to write reports: {e}")
        return 1

    SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generated = today_iso()
    report_path = REPORTS_DIR / f"rank-{generated}.md"

    # ── Rank (parallel, one agent per framework) ──
    results = asyncio.run(_fan_out(
        [(lambda fw=fw, caps=caps: rank_one(fw, caps, product, cfg))
         for fw, caps in sorted(by_fw.items())],
        cfg,
    ))
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        # An unranked framework would reach the gate as a missing ranking anyway; failing
        # here names the agent that broke instead of the capabilities it left behind.
        print(f"\n{len(failures)} ranking agent(s) FAILED — nothing written:")
        for e in failures:
            print(f"  - {e}")
        return 1

    rankings: dict[str, list[dict]] = {}
    cost = 0.0
    for r in results:
        rankings.update(r["rankings"])
        cost += r.get("cost", 0.0)

    # ── Deterministic gate (runs before any write, always) ──
    policy = capabilities.get("license_policy") or {}
    gate = rank_lib.ranking_gate(universe, rankings, policy)
    report_path.write_text(
        rank_lib.render_rank_report(universe, rankings, gate, ranked_from, generated,
                                    product_path=str(product_path)),
        encoding="utf-8",
    )

    state = load_state()
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    state["last_rank_run"] = {"product_hash": ranked_from, "product": str(product_path),
                              "generated_at": now_iso(), "applied": False}

    print(f"\n{len(universe)} capabilities ranked, {total_components} components ordered. "
          f"Cost: ${cost:.2f}.")
    print(f"report: {report_path}")

    if not gate["ok"]:
        print("\nRANKING GATE FAILED — nothing written:")
        for label, items in (("no ranking", gate["missing_rankings"]),
                             ("unknown capability", gate["unknown_rankings"])):
            for key in items:
                print(f"  - {label}: {key}")
        for m in gate["set_mismatches"]:
            parts = []
            if m["missing"]:
                parts.append(f"left unranked: {', '.join(m['missing'])}")
            if m["unexpected"]:
                parts.append(f"not in options: {', '.join(m['unexpected'])}")
            if m["duplicated"]:
                parts.append(f"ranked twice: {', '.join(m['duplicated'])}")
            print(f"  - {m['key']}: {'; '.join(parts) or 'malformed ranking'}")
        for b in gate["blank_rationales"]:
            print(f"  - {b['key']}: no rationale for {', '.join(b['components'])}")
        for v in gate["violations"]:
            print(f"  - {v['key']}: {v['component']} carries {v['license']} in an "
                  f"{v['role']} role — fix capabilities.json, not this ranking")
        save_state(state)
        return 1

    # ── Apply through the schema owner ──
    rankings_path = SHARDS_DIR / "rankings.json"
    rankings_path.write_text(
        json.dumps(rank_lib.rankings_payload(rankings, ranked_from), indent=1,
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(  # fixed argv, no shell; the return code is inspected below
        [sys.executable, str(stack_py), "--apply-ranking", str(rankings_path)],
        cwd=str(comp), capture_output=True, text=True, check=False,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        print(f"\n{stack_py.name} refused the write (exit {proc.returncode}) — "
              "stack.json is unchanged.")
        save_state(state)
        return 1

    state["last_rank_run"]["applied"] = True
    save_state(state)
    if gate["exceptions"]:
        print(f"{len(gate['exceptions'])} component(s) ranked under a recorded license "
              "exception — see the report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
