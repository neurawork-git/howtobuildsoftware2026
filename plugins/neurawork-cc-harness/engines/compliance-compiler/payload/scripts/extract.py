"""Extract compliance frameworks into a structured catalog — parallel agents.

Fans out one Claude Agent SDK agent per shard (``shards.build_shards``), bounded
by ``max_concurrency``, each writing a JSON array of constraints to its own
per-shard temp file (``catalog/.shards/<framework>-<key>.json``). After the fan-out
completes, the shard files are merged into per-framework catalogs
(``catalog/<framework>.json``) and ``catalog/index.md`` is rebuilt.

Per-shard temp files avoid write races: no two agents ever touch the same file.

Usage:
    uv run python scripts/extract.py                       # all configured frameworks
    uv run python scripts/extract.py --frameworks gdpr     # subset
    uv run python scripts/extract.py --dry-run             # show the shard plan, no LLM
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

from config import (
    AGENTS_FILE,
    CATALOG_DIR,
    FRAMEWORK_TITLES,
    INDEX_FILE,
    LAST_EXTRACT_FILE,
    ROOT_DIR,
    SHARDS_DIR,
    load_cfg,
    now_iso,
    today_iso,
)
from shards import build_shards
from utils import load_state, save_state

from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude


def _shard_path(shard: dict) -> Path:
    return SHARDS_DIR / f"{shard['framework']}-{shard['key']}.json"


def _build_prompt(shard: dict, shard_path: Path) -> str:
    constitution = AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""
    fw = shard["framework"]
    return f"""You are a compliance extraction agent. Extract atomic constraints for
ONE slice of ONE framework, following the constitution exactly.

## Constitution (AGENTS.md)

{constitution}

## Your shard

- Framework: {fw} ({FRAMEWORK_TITLES.get(fw, fw)})
- Section: {shard['title']}
- Scope: {shard['scope_hint']}

## Task

Extract the atomic constraints for THIS shard only. Write a single JSON array of
constraint objects (schema per the constitution) to exactly this file, using the
Write tool, and write nothing else:

    {shard_path}

Output only the JSON array as the file's content — no surrounding prose, no other
files. Ensure it is valid JSON (double quotes, no trailing commas)."""


async def extract_one(shard: dict, cfg: dict) -> dict:
    """Run one shard agent. Returns a result dict; raises on hard failure."""
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ResultMessage,
        query,
    )

    shard_path = _shard_path(shard)
    if shard_path.exists():
        shard_path.unlink()  # clear stale output so existence proves this run wrote it

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
    try:
        parsed = json.loads(shard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{shard['framework']}-{shard['key']}: invalid JSON — {e}") from e
    if not isinstance(parsed, list):
        raise RuntimeError(f"{shard['framework']}-{shard['key']}: shard is not a JSON array")

    return {"shard": shard, "cost": cost, "count": len(parsed)}


async def extract_all(shards: list[dict], cfg: dict) -> list:
    """Run all shards concurrently, capped by max_concurrency. Never raises."""
    sem = asyncio.Semaphore(int(cfg.get("max_concurrency", 12)))

    async def run(shard: dict):
        async with sem:
            label = f"{shard['framework']}-{shard['key']}"
            print(f"  → extracting {label} ...")
            return await extract_one(shard, cfg)

    return await asyncio.gather(*(run(s) for s in shards), return_exceptions=True)


def _merge_framework(fw: str) -> dict:
    """Merge every shard file for ``fw`` into a single catalog dict (dedup by id)."""
    by_id: dict[str, dict] = {}
    for shard_file in sorted(SHARDS_DIR.glob(f"{fw}-*.json")):
        try:
            entries = json.loads(shard_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for c in entries:
            if isinstance(c, dict) and c.get("id"):
                by_id[c["id"]] = c
    constraints = [by_id[k] for k in sorted(by_id)]
    mandatory = sum(1 for c in constraints if c.get("mandatory", True))
    return {
        "framework": fw,
        "title": FRAMEWORK_TITLES.get(fw, fw),
        "generated": today_iso(),
        "count": len(constraints),
        "mandatory": mandatory,
        "constraints": constraints,
    }


def _write_index(catalogs: list[dict]) -> None:
    lines = [
        "# Compliance Catalog",
        "",
        "| Framework | Constraints | Mandatory | Generated |",
        "|-----------|-------------|-----------|-----------|",
    ]
    for cat in catalogs:
        lines.append(
            f"| {cat['framework']} | {cat['count']} | {cat['mandatory']} | {cat['generated']} |"
        )
    lines.append("")
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")


def _stamp_last_extract() -> None:
    LAST_EXTRACT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LAST_EXTRACT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")
    tmp.replace(LAST_EXTRACT_FILE)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract compliance frameworks into a catalog")
    parser.add_argument("--frameworks", type=str,
                        help="Comma-separated subset (default: config frameworks)")
    parser.add_argument("--dry-run", action="store_true", help="Show the shard plan, no LLM")
    args = parser.parse_args()

    cfg = load_cfg()
    if args.frameworks:
        cfg["frameworks"] = [f.strip() for f in args.frameworks.split(",") if f.strip()]

    repo_root = ROOT_DIR.parent
    try:
        assert_in_repo_not_dotclaude(CATALOG_DIR, repo_root)
    except WriteGuardError as e:
        print(f"Refusing to write catalog: {e}")
        return 1

    shards = build_shards(cfg)
    if not shards:
        print("No shards for the configured frameworks — nothing to extract.")
        return 1

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Frameworks: {', '.join(cfg['frameworks'])}")
    print(f"Shards ({len(shards)}), max_concurrency={cfg.get('max_concurrency', 12)}:")
    for s in shards:
        print(f"  - {s['framework']}-{s['key']}: {s['title']}")
    if args.dry_run:
        return 0

    SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    results = asyncio.run(extract_all(shards, cfg))

    failures = [r for r in results if isinstance(r, Exception)]
    ok = [r for r in results if isinstance(r, dict)]
    total_cost = sum(r["cost"] for r in ok)

    catalogs = [_merge_framework(fw) for fw in cfg["frameworks"]]
    for cat in catalogs:
        (CATALOG_DIR / f"{cat['framework']}.json").write_text(
            json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    _write_index(catalogs)
    _stamp_last_extract()

    state = load_state()
    state["total_cost"] = state.get("total_cost", 0.0) + total_cost
    state["extracted"] = {"at": now_iso(), "shards_ok": len(ok), "shards_failed": len(failures)}
    save_state(state)

    total = sum(c["count"] for c in catalogs)
    print(f"\nExtracted {total} constraints across {len(catalogs)} frameworks. "
          f"Cost: ${total_cost:.2f}.")
    if failures:
        print(f"\n{len(failures)} shard(s) FAILED:")
        for e in failures:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
