"""Apply session learnings to the CLAUDE.md hierarchy + docs/ (the LLM learner).

Reads new/changed daily logs plus the current CLAUDE.md tree and docs/, and lets
the Claude Agent SDK edit those files in place per AGENTS.md. Incremental by
SHA-256 of each log; stamps ``last-update.json`` on success so the SessionStart
gate knows when it last ran.

Usage:
    uv run python scripts/update.py            # changed logs only
    uv run python scripts/update.py --all      # re-apply all logs
    uv run python scripts/update.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # <ldir> for _shared

from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude
from config import (
    AGENTS_FILE,
    CLAUDEMD_FILE,
    LAST_UPDATE_FILE,
    REPO_ROOT,
    docs_dir,
    load_cfg,
    now_iso,
)
from markers import restore, snapshot
from utils import file_hash, list_raw_files, load_state, save_state


def _stamp_last_update() -> None:
    """Record the success time for the SessionStart age-gate (atomic)."""
    LAST_UPDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LAST_UPDATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")
    os.replace(tmp, LAST_UPDATE_FILE)


def _list_claudemd_files(depth: int, excluded: list[str]) -> list[Path]:
    """Existing CLAUDE.md files at or above ``depth`` (1 = repo root only)."""
    found: list[Path] = []
    if CLAUDEMD_FILE.exists():
        found.append(CLAUDEMD_FILE)
    excl = set(excluded)
    for path in REPO_ROOT.rglob("CLAUDE.md"):
        if path == CLAUDEMD_FILE:
            continue
        rel = path.relative_to(REPO_ROOT)
        if any(part in excl or part.startswith(".") for part in rel.parts[:-1]):
            continue
        # rel.parts is (<dir>, ..., "CLAUDE.md"); subdir depth = len - 1.
        if (len(rel.parts) - 1) <= max(depth - 1, 0):
            found.append(path)
    return found


def _list_docs(excluded: list[str]) -> list[Path]:
    docs = docs_dir()
    if not docs.is_dir():
        return []
    excl = set(excluded)
    return sorted(
        p for p in docs.rglob("*.md")
        if not any(part in excl for part in p.relative_to(REPO_ROOT).parts)
    )


def _build_prompt(log_path: Path, claudemds: list[Path], docs: list[Path]) -> str:
    schema = AGENTS_FILE.read_text(encoding="utf-8")
    cfg = load_cfg()
    depth = int(cfg.get("claudemd_depth", 1))
    excluded = list(cfg.get("excluded_dirs", []))
    language = str(cfg.get("language", "en"))
    docs_name = str(cfg.get("docs_dir", "docs"))
    log_content = log_path.read_text(encoding="utf-8")

    cmd_block = "\n".join(f"- {p.relative_to(REPO_ROOT)}" for p in claudemds) or "(none yet)"
    docs_block = "\n".join(f"- {p.relative_to(REPO_ROOT)}" for p in docs) or "(none yet)"

    return f"""You are the claudemd-lerner. Apply what this session implies to the
project's CLAUDE.md hierarchy and {docs_name}/ tree, following the schema exactly.
Edit files surgically — do not rewrite from scratch.

## Schema (AGENTS.md)

{schema}

## Configuration

- claudemd_depth: {depth} (1 = root CLAUDE.md only; maintain area CLAUDE.md only within this depth)
- docs_dir: {docs_name}
- language: {language}
- excluded_dirs: {excluded}

## Existing CLAUDE.md files

{cmd_block}

## Existing {docs_name}/ files

{docs_block}

## Session Daily Log to Apply — {log_path.name}

{log_content}

## Task

Ground every change in the live repository (use Read/Glob/Grep to confirm paths,
commands, and names) and in the daily log above. Update the root CLAUDE.md for
durable repo-wide facts; update an area CLAUDE.md (only within depth {depth}) for
area-specific facts; write longer-form content under {docs_name}/. Prefer Edit
over rewrite, never invent, write prose in {language}, ignore {excluded}, and
NEVER write under .claude/. If nothing in the log warrants a doc change, make no
edits."""


async def update_one(log_path: Path, state: dict) -> tuple[float, bool]:
    """Apply a single daily log to the docs. Returns ``(cost, ingested)``."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    cfg = load_cfg()
    # The exact files the prompt advertises are the files the guard covers — one
    # traversal, and the guard is provably scoped to what the learner may edit.
    claudemds = _list_claudemd_files(int(cfg.get("claudemd_depth", 1)),
                                     list(cfg.get("excluded_dirs", [])))
    docs = _list_docs(list(cfg.get("excluded_dirs", [])))
    guarded = snapshot(claudemds + docs)

    cost = 0.0
    try:
        async for message in query(
            prompt=_build_prompt(log_path, claudemds, docs),
            options=ClaudeAgentOptions(
                cwd=str(REPO_ROOT),
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
                        pass  # the LLM edits files directly
            elif isinstance(message, ResultMessage):
                cost = message.total_cost_usd or 0.0
                print(f"  Cost: ${cost:.4f}")
    except Exception as e:
        print(f"  Error: {e}")
        return 0.0, False
    finally:
        # `finally`, not a trailing call: the early return above must not skip the guard.
        for message in restore(guarded):
            print(f"  Marker guard: {message}")

    state.setdefault("ingested", {})[log_path.name] = {
        "hash": file_hash(log_path),
        "updated_at": now_iso(),
        "cost_usd": cost,
    }
    state["updated_count"] = state.get("updated_count", 0) + 1
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    save_state(state)
    return cost, True


def _select(args, state: dict) -> list[Path]:
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
    parser = argparse.ArgumentParser(description="Apply daily logs to CLAUDE.md + docs/")
    parser.add_argument("--all", action="store_true", help="Re-apply all logs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would update")
    args = parser.parse_args()

    # Refuse to run if the doc targets are somehow not in-repo or under .claude/.
    try:
        assert_in_repo_not_dotclaude(CLAUDEMD_FILE, REPO_ROOT)
        assert_in_repo_not_dotclaude(docs_dir(), REPO_ROOT)
    except WriteGuardError as e:
        print(f"Refusing to update: {e}")
        return

    state = load_state()
    to_update = _select(args, state)

    if not to_update:
        print("Nothing to update — docs are current with the daily logs.")
        return

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Logs to apply ({len(to_update)}):")
    for f in to_update:
        print(f"  - {f.name}")
    if args.dry_run:
        return

    total = 0.0
    ingested_any = False
    for i, log_path in enumerate(to_update, 1):
        print(f"\n[{i}/{len(to_update)}] Applying {log_path.name}...")
        cost, ingested = asyncio.run(update_one(log_path, state))
        total += cost
        ingested_any = ingested_any or ingested

    # Stamp only on real progress: the stamp shuts the SessionStart gate for
    # `update_age_hours`, so stamping a run where every log errored defers the work
    # silently instead of letting the next session retry it.
    if ingested_any:
        _stamp_last_update()
    else:
        print("\nNothing was ingested — leaving the completion stamp untouched.")
    print(f"\nDone. Total cost: ${total:.2f}.")


if __name__ == "__main__":
    main()
