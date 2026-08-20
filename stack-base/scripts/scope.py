"""Narrow the compliance capability catalog to ONE product — parallel agents.

Reads a tracked product description (``product.md``) plus the sibling compliance
install's ``catalog/capabilities.json`` and ``catalog/stack.json``, then fans out
one Claude Agent SDK agent per framework to decide, for every capability, whether
it applies to this product and why. A single CHALLENGE agent then tries to refute
each "not applicable" claim against the same description — a claim the description
itself contradicts fails the run. Finally a deterministic safety gate (pure set
math, no LLM) checks that no mandatory constraint was dropped without a reason.

Only a clean gate reaches the write, and the write goes through
``<compliance_dir>/scripts/stack.py --apply-scope`` — the one schema owner for
``stack.json``. This engine creates no data artifact of its own.

Per-agent shard files under ``.shards/`` avoid write races. A run whose product
description is unchanged since the recorded scoping is skipped entirely.

Usage:
    uv run python scripts/scope.py                    # scope from product.md
    uv run python scripts/scope.py --product P.md     # scope from another description
    uv run python scripts/scope.py --all              # ignore the unchanged-product skip
    uv run python scripts/scope.py --dry-run          # show the plan, no LLM
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

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

PRODUCT_TEMPLATE = """\
# Product

<!-- Describe the product this stack is being scoped for. The scoping agents read
     ONLY this file, so anything they must know has to be written down here. -->

## What it does

## Who uses it

## What data it holds

<!-- Be explicit about personal data: names, emails, IPs, payment details, health
     data, telemetry. "None" is a valid answer — and one the challenge pass will
     check against the rest of this file. -->

## Where it runs

## What it integrates with
"""


# ── Prompts ───────────────────────────────────────────────────────────

def _constitution() -> str:
    return AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""


def build_scope_prompt(fw: str, caps: list[dict], product: str, shard_path: Path) -> str:
    """One framework's scoping prompt. Every key it must decide on is listed inline."""
    listing = "\n".join(
        f"- key: {c['key']}\n"
        f"  capability: {c['capability']}\n"
        f"  category: {c['category']}\n"
        f"  mandatory_linked: {str(bool(c['mandatory_linked'])).lower()}\n"
        f"  description: {c['description']}"
        for c in caps
    )
    return f"""You are a compliance product-scoping agent. Decide, for ONE framework,
which capabilities this product must implement, following the constitution exactly.

## Constitution (AGENTS.md)

{_constitution()}

## Product description

{product}

## Framework: {fw} — {len(caps)} capabilities to decide on

{listing}

## Your task

For EACH of the {len(caps)} keys above, decide whether the capability applies to
THIS product, and give a reason grounded in the product description.

Rules (the constitution governs; these are the ones that fail the run):
- Decide on all {len(caps)} keys, using the EXACT key strings above. No others.
- "applicable": false REQUIRES a non-empty "reason" naming the property of this
  product that makes the capability unnecessary.
- When in doubt, "applicable": true. A wrongly-dropped capability is a compliance
  breach; an unnecessary one is only a component choice.
- Cost, effort or "not built yet" are never grounds for false.
- For "applicable": true a short reason is still useful; it may be empty.

Write a single JSON array to exactly this file, using the Write tool, and write
nothing else:

    {shard_path}

Each element: {{"key": str, "applicable": bool, "reason": str}}.
Output only the JSON array as the file's content — no prose, no other files. Ensure
valid JSON (double quotes, no trailing commas)."""


def build_challenge_prompt(product: str, items: list[dict], shard_path: Path) -> str:
    """The refutation pass over every "not applicable" decision."""
    listing = "\n".join(
        f"- key: {i['key']}\n"
        f"  capability: {i['capability']}\n"
        f"  description: {i['description']}\n"
        f"  claimed reason for NOT applicable: {i['reason']}"
        for i in items
    )
    return f"""You are an adversarial compliance reviewer. Another agent ruled the
capabilities below OUT of scope for this product. Try to REFUTE each claim using the
product description alone, following the constitution exactly.

## Constitution (AGENTS.md)

{_constitution()}

## Product description

{product}

## Claims to challenge ({len(items)})

{listing}

## Your task

For EACH key above decide whether the product description CONTRADICTS the claimed
reason.

- "refuted": true when the description says something incompatible with the claim —
  for example the reason says no personal data is processed while the description
  says user email addresses are stored.
- A refutation REQUIRES "evidence": the contradicting sentence, quoted verbatim from
  the product description. No quote means no refutation.
- Do not refute from knowledge of the regulation; only from this description.
- A merely thin or vague reason is not a contradiction.
- Prefer refuting a claim you cannot verify from the text over letting a false one
  through: a refuted run writes nothing and a human fixes it.

Write a single JSON array to exactly this file, using the Write tool, and write
nothing else:

    {shard_path}

Each element: {{"key": str, "refuted": bool, "evidence": str}}.
Output only the JSON array as the file's content — no prose, no other files. Ensure
valid JSON (double quotes, no trailing commas)."""


# ── Shard parsing ─────────────────────────────────────────────────────

def parse_scope_shard(raw: object, expected_keys: set[str], fw: str) -> dict:
    """Validate one framework's scope shard into ``{key: {applicable, reason}}``.

    The key set must match EXACTLY: a dropped key is the silent omission this engine
    exists to prevent, and an invented one is a decision about a capability the
    catalog does not contain. Either fails the framework, and a failed framework
    fails the run.
    """
    if not isinstance(raw, list):
        raise TypeError(f"scope {fw}: shard is not a JSON array")
    decisions: dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict) or not item.get("key"):
            raise RuntimeError(f"scope {fw}: shard element without a key: {item!r}")
        key = str(item["key"])
        if key in decisions:
            raise RuntimeError(f"scope {fw}: duplicate decision for {key}")
        decisions[key] = {
            "applicable": bool(item.get("applicable", True)),
            "reason": str(item.get("reason") or "").strip(),
        }
    got = set(decisions)
    if missing := sorted(expected_keys - got):
        raise RuntimeError(f"scope {fw}: no decision for {len(missing)} key(s): "
                           f"{', '.join(missing)}")
    if unknown := sorted(got - expected_keys):
        raise RuntimeError(f"scope {fw}: decision for {len(unknown)} unknown key(s): "
                           f"{', '.join(unknown)}")
    return decisions


def parse_challenge_shard(raw: object, expected_keys: set[str]) -> list[dict]:
    """Validate the challenge shard into the list of REFUTED claims.

    A refutation without a verbatim quote is discarded, per the constitution: an
    unevidenced refusal is unarguable and would block a correct run.
    """
    if not isinstance(raw, list):
        raise TypeError("challenge: shard is not a JSON array")
    refuted: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("key"):
            raise RuntimeError(f"challenge: shard element without a key: {item!r}")
        key = str(item["key"])
        if key not in expected_keys:
            raise RuntimeError(f"challenge: verdict for a key that was not challenged: {key}")
        evidence = str(item.get("evidence") or "").strip()
        if item.get("refuted") and evidence:
            refuted.append({"key": key, "evidence": evidence})
    return refuted


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


async def scope_one(fw: str, caps: list[dict], product: str, cfg: dict) -> dict:
    """Decide one framework's capabilities. Returns ``{fw, decisions, cost}``."""
    shard_path = SHARDS_DIR / f"scope-{fw}.json"
    raw, cost = await _run_agent(build_scope_prompt(fw, caps, product, shard_path),
                                 shard_path, cfg)
    return {
        "fw": fw,
        "decisions": parse_scope_shard(raw, {c["key"] for c in caps}, fw),
        "cost": cost,
    }


async def challenge_all(product: str, items: list[dict], cfg: dict) -> dict:
    """Try to refute every "not applicable" claim. Returns ``{refuted, cost}``."""
    shard_path = SHARDS_DIR / "challenge.json"
    raw, cost = await _run_agent(build_challenge_prompt(product, items, shard_path),
                                 shard_path, cfg)
    return {
        "refuted": parse_challenge_shard(raw, {i["key"] for i in items}),
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


def already_scoped(stack: dict, scope_hash: str) -> bool:
    """True when every capability already carries this exact product's scope hash."""
    choices = (stack.get("choices") or {}).values()
    return bool(choices) and all(c.get("scoped_from") == scope_hash for c in choices)


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decide which compliance capabilities apply to this product, and why"
    )
    parser.add_argument("--product", type=str, metavar="PATH",
                        help="Product description to scope from (default: <stack_dir>/product.md)")
    parser.add_argument("--all", action="store_true",
                        help="Re-scope even when the product description is unchanged")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan, no LLM")
    args = parser.parse_args()

    cfg = load_cfg()
    comp = compliance_root(cfg)
    catalog_dir = comp / "catalog"
    capabilities_json = catalog_dir / "capabilities.json"
    stack_json = catalog_dir / "stack.json"
    stack_py = comp / "scripts" / "stack.py"

    if not comp.is_dir():
        print(f"No compliance install at {comp} — stack-compiler has nothing to scope. "
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
        default_path = product_file(cfg)
        if args.product:
            print(f"No such product description: {product_path}")
            return 1
        default_path.parent.mkdir(parents=True, exist_ok=True)
        default_path.write_text(PRODUCT_TEMPLATE, encoding="utf-8")
        print(f"Wrote a product template to {default_path} — describe the product, then re-run.")
        return 1

    product = product_path.read_text(encoding="utf-8")
    if not product.strip():
        print(f"{product_path} is empty — describe the product, then re-run.")
        return 1
    scope_hash = scope_lib.product_hash(product)

    capabilities = _load_json(capabilities_json)
    stack = _load_json(stack_json)
    universe = scope_lib.capability_universe(stack, capabilities)
    if not universe:
        print(f"{stack_json} has no capabilities — re-run stack.py --scaffold")
        return 1

    by_fw: dict[str, list[dict]] = {}
    for u in universe:
        by_fw.setdefault(u["framework"], []).append(u)
    mandatory_by_fw = {fw: scope_lib.mandatory_ids_for(fw, catalog_dir) for fw in by_fw}

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Scoping {len(universe)} capabilities "
          f"across {len(by_fw)} framework(s) from {product_path} (hash {scope_hash})")
    for fw, caps in sorted(by_fw.items()):
        print(f"  {fw}: {len(caps)} capabilities, "
              f"{len(mandatory_by_fw[fw])} mandatory constraint(s)")
    if args.dry_run:
        return 0

    if not args.all and already_scoped(stack, scope_hash):
        print("Product description unchanged since the recorded scoping — nothing to do "
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
    report_path = REPORTS_DIR / f"scope-{generated}.md"

    # ── Scope (parallel, one agent per framework) ──
    results = asyncio.run(_fan_out(
        [(lambda fw=fw, caps=caps: scope_one(fw, caps, product, cfg))
         for fw, caps in sorted(by_fw.items())],
        cfg,
    ))
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        # An unscoped framework is exactly the silent omission this engine prevents,
        # so unlike capabilities.py there is no carry-over path: the run fails.
        print(f"\n{len(failures)} scoping agent(s) FAILED — nothing written:")
        for e in failures:
            print(f"  - {e}")
        return 1

    decisions: dict[str, dict] = {}
    cost = 0.0
    for r in results:
        decisions.update(r["decisions"])
        cost += r.get("cost", 0.0)

    # ── Challenge (one agent over every "not applicable" claim) ──
    by_key = {u["key"]: u for u in universe}
    challenge_items = [
        {"key": k, "capability": by_key[k]["capability"],
         "description": by_key[k]["description"], "reason": d["reason"]}
        for k, d in sorted(decisions.items())
        if k in by_key and not d["applicable"]
    ]
    refuted: list[dict] = []
    if challenge_items:
        try:
            outcome = asyncio.run(challenge_all(product, challenge_items, cfg))
        except Exception as e:  # noqa: BLE001 — any challenge failure must fail the run
            print(f"\nChallenge agent FAILED — nothing written: {e}")
            return 1
        refuted = outcome["refuted"]
        cost += outcome.get("cost", 0.0)
    else:
        print("\nNo capability was ruled out — challenge pass skipped.")

    # ── Deterministic gate (runs before any write, always) ──
    gate = scope_lib.safety_gate(universe, decisions, mandatory_by_fw)
    report_path.write_text(
        scope_lib.render_scope_report(universe, decisions, gate, scope_hash, generated,
                                      refuted=refuted, product_path=str(product_path)),
        encoding="utf-8",
    )

    state = load_state()
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    state["last_run"] = {"product_hash": scope_hash, "product": str(product_path),
                         "generated_at": now_iso(), "applied": False}

    ruled_out = sum(1 for d in decisions.values() if not d["applicable"])
    print(f"\n{len(universe)} capabilities scoped: {len(universe) - ruled_out} applicable, "
          f"{ruled_out} ruled out. Cost: ${cost:.2f}.")
    print(f"report: {report_path}")

    if refuted:
        print(f"\nREFUTED — the product description contradicts {len(refuted)} "
              "'not applicable' decision(s); nothing written:")
        for r in refuted:
            print(f"  - {r['key']}: {r['evidence']}")
        save_state(state)
        return 1

    if not gate["ok"]:
        print("\nSAFETY GATE FAILED — nothing written:")
        for label, items in (("no decision", gate["missing_decisions"]),
                             ("unknown capability", gate["unknown_decisions"]),
                             ("ruled out with no reason", gate["blank_reasons"])):
            for key in items:
                print(f"  - {label}: {key}")
        for item in gate["unjustified_mandatory"]:
            print(f"  - mandatory {item['constraint']} dropped without a reason "
                  f"(only covered by {', '.join(item['capabilities'])})")
        save_state(state)
        return 1

    # ── Apply through the schema owner ──
    decisions_path = SHARDS_DIR / "decisions.json"
    decisions_path.write_text(
        json.dumps(scope_lib.decisions_payload(decisions, scope_hash), indent=1,
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(  # fixed argv, no shell; the return code is inspected below
        [sys.executable, str(stack_py), "--apply-scope", str(decisions_path)],
        cwd=str(comp), capture_output=True, text=True, check=False,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        print(f"\n{stack_py.name} refused the write (exit {proc.returncode}) — "
              "stack.json is unchanged.")
        save_state(state)
        return 1

    state["last_run"]["applied"] = True
    save_state(state)
    if gate["justified_drops"]:
        print(f"{len(gate['justified_drops'])} mandatory constraint(s) traced to a justified "
              "non-applicable capability — see the report.")
    if gate["uncovered_upstream"]:
        print(f"! {len(gate['uncovered_upstream'])} mandatory constraint(s) are covered by no "
              "capability at all — a gap in capabilities.json, not in this scoping pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
