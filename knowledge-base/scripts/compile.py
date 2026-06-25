"""Compile daily logs into structured knowledge articles (the LLM compiler).

Reads a daily log plus the current knowledge base, and lets the Claude Agent SDK
write/update articles per AGENTS.md. Incremental by SHA-256 of each log; stamps
``last-compile.json`` on success so the SessionStart gate knows when it last ran.

Usage:
    uv run python scripts/compile.py            # changed logs only
    uv run python scripts/compile.py --all      # recompile everything
    uv run python scripts/compile.py --file daily/2026-06-18.md
    uv run python scripts/compile.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from config import (
    AGENTS_FILE,
    CONCEPTS_DIR,
    CONNECTIONS_DIR,
    DAILY_DIR,
    KNOWLEDGE_DIR,
    LAST_COMPILE_FILE,
    ROOT_DIR,
    load_cfg,
    now_iso,
)
from utils import (
    file_hash,
    list_raw_files,
    list_wiki_articles,
    load_state,
    read_wiki_index,
    save_state,
)


def _stamp_last_compile() -> None:
    """Record the success time for the SessionStart age-gate (atomic)."""
    LAST_COMPILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LAST_COMPILE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")
    os.replace(tmp, LAST_COMPILE_FILE)


def _build_prompt(log_path: Path) -> str:
    schema = AGENTS_FILE.read_text(encoding="utf-8")
    wiki_index = read_wiki_index()
    log_content = log_path.read_text(encoding="utf-8")

    existing = []
    for article in list_wiki_articles():
        rel = article.relative_to(KNOWLEDGE_DIR)
        existing.append(f"### {rel}\n```markdown\n{article.read_text(encoding='utf-8')}\n```")
    existing_block = "\n\n".join(existing) if existing else "(none yet)"
    stamp = now_iso()[:10]

    return f"""You are the knowledge compiler. Compile the daily log below into wiki
articles, following the schema exactly.

## Schema (AGENTS.md)

{schema}

## Current Index

{wiki_index}

## Existing Articles

{existing_block}

## Daily Log to Compile — {log_path.name}

{log_content}

## Task

Extract 3-7 distinct concepts. Prefer UPDATING existing articles over creating
near-duplicates. Create connection articles only for genuinely non-obvious links.
Write concept articles under {CONCEPTS_DIR} and connection articles under
{CONNECTIONS_DIR}. Every article needs full YAML frontmatter, cites this daily log
in its sources, and links to at least two other articles via [[wikilinks]].
Then update {KNOWLEDGE_DIR / 'index.md'} (add/modify rows) and append a dated entry
to {KNOWLEDGE_DIR / 'log.md'} (use the date {stamp})."""


async def compile_one(log_path: Path, state: dict) -> float:
    """Compile a single daily log. Returns the API cost."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    cfg = load_cfg()
    cost = 0.0
    try:
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
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        pass  # the LLM writes files directly
            elif isinstance(message, ResultMessage):
                cost = message.total_cost_usd or 0.0
                print(f"  Cost: ${cost:.4f}")
    except Exception as e:
        print(f"  Error: {e}")
        return 0.0

    state.setdefault("ingested", {})[log_path.name] = {
        "hash": file_hash(log_path),
        "compiled_at": now_iso(),
        "cost_usd": cost,
    }
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    save_state(state)
    return cost


def _select(args, state: dict) -> list[Path]:
    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = DAILY_DIR / target.name
        if not target.exists():
            target = ROOT_DIR / args.file
        if not target.exists():
            print(f"Error: {args.file} not found")
            sys.exit(1)
        return [target]

    all_logs = list_raw_files()
    if args.all:
        return all_logs
    changed = []
    for log_path in all_logs:
        prev = state.get("ingested", {}).get(log_path.name, {})
        if not prev or prev.get("hash") != file_hash(log_path):
            changed.append(log_path)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile daily logs into knowledge articles")
    parser.add_argument("--all", action="store_true", help="Force recompile all logs")
    parser.add_argument("--file", type=str, help="Compile a specific daily log")
    parser.add_argument("--dry-run", action="store_true", help="Show what would compile")
    args = parser.parse_args()

    state = load_state()
    to_compile = _select(args, state)

    if not to_compile:
        print("Nothing to compile — knowledge base is up to date.")
        return

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Files to compile ({len(to_compile)}):")
    for f in to_compile:
        print(f"  - {f.name}")
    if args.dry_run:
        return

    total = 0.0
    for i, log_path in enumerate(to_compile, 1):
        print(f"\n[{i}/{len(to_compile)}] Compiling {log_path.name}...")
        total += asyncio.run(compile_one(log_path, state))

    _stamp_last_compile()
    print(f"\nDone. Total cost: ${total:.2f}. Articles: {len(list_wiki_articles())}")


if __name__ == "__main__":
    main()
