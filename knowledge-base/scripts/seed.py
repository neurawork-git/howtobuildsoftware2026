"""Seed an initial knowledge base from an existing (brownfield) repository.

Run once at install time (foreground). Reads the repo's own documentation and
source map, then lets the Claude Agent SDK write the first concept articles and
index per AGENTS.md. Aborts on a dirty working tree (outside the knowledge dir)
so it never compiles over uncommitted work.

Usage:
    uv run python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # <kdir> for _shared

from config import AGENTS_FILE, KNOWLEDGE_DIR, LAST_COMPILE_FILE, ROOT_DIR, load_cfg
from _shared.gitctx import repo_root
from _shared.repo_guard import assert_in_repo_not_dotclaude, WriteGuardError

PROMPT_FILE = Path(__file__).resolve().parent / "seed_prompt.txt"


def _dirty_outside_kdir(root: Path, kdir_name: str) -> list[str]:
    """Changed paths in the working tree that are NOT under the knowledge dir."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root), capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    dirty = []
    for line in out.stdout.splitlines():
        path = line[3:].strip()
        if path and not path.startswith(f"{kdir_name}/"):
            dirty.append(path)
    return dirty


def _repo_context(root: Path) -> str:
    parts = []
    readme = next((root / n for n in ("README.md", "README.rst", "README.txt")
                   if (root / n).exists()), None)
    if readme:
        parts.append(f"## README ({readme.name})\n\n{readme.read_text(encoding='utf-8')[:8000]}")

    docs = root / "docs"
    if docs.is_dir():
        listing = "\n".join(sorted(str(p.relative_to(root)) for p in docs.rglob("*.md"))[:50])
        parts.append(f"## docs/ files\n\n{listing or '(none)'}")

    top = sorted(p.name + ("/" if p.is_dir() else "")
                 for p in root.iterdir() if not p.name.startswith("."))
    parts.append("## Top-level entries\n\n" + "\n".join(top))
    return "\n\n---\n\n".join(parts)


async def run_seed() -> float:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    root = repo_root(str(ROOT_DIR)) or ROOT_DIR.parent
    try:
        assert_in_repo_not_dotclaude(KNOWLEDGE_DIR, root)
    except WriteGuardError as e:
        print(f"Refusing to seed: {e}")
        return 0.0

    schema = AGENTS_FILE.read_text(encoding="utf-8")
    instructions = PROMPT_FILE.read_text(encoding="utf-8")
    prompt = f"""{instructions}

## AGENTS.md Schema

{schema}

## Write articles under

{KNOWLEDGE_DIR}

## Repository Context

{_repo_context(Path(root))}"""

    cfg = load_cfg()
    cost = 0.0
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=str(root),
            system_prompt={"type": "preset", "preset": "claude_code"},
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
            permission_mode="acceptEdits",
            max_turns=40,
            setting_sources=[],
            strict_mcp_config=True,
            model=(cfg.get("model") or None),
        ),
    ):
        if isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0
    return cost


def _stamp_last_compile() -> None:
    LAST_COMPILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LAST_COMPILE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")
    os.replace(tmp, LAST_COMPILE_FILE)


def main() -> int:
    root = repo_root(str(ROOT_DIR))
    if not root:
        print("Not a git repository — cannot seed.")
        return 1

    dirty = _dirty_outside_kdir(Path(root), ROOT_DIR.name)
    if dirty:
        print("Working tree has uncommitted changes outside the knowledge dir:")
        for p in dirty[:20]:
            print(f"  {p}")
        print("Commit or stash them first, then re-run seed.")
        return 1

    print("Seeding knowledge base from repository...")
    cost = asyncio.run(run_seed())
    _stamp_last_compile()
    print(f"Seed complete. Cost: ${cost:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
