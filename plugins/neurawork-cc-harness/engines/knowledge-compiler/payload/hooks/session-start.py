"""SessionStart hook — inject the knowledge index, and maybe spawn a compile.

Two jobs, both fast:
  1. Print the knowledge base index + recent daily log as additionalContext.
  2. If the last compile is older than the configured age AND there is new daily
     content AND no fresh lock, spawn compile.py detached. Skipped in a worktree.

Never blocks: the compile is a fire-and-forget Popen; JSON is printed right after.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))                       # _shared
sys.path.insert(0, str(KDIR / "scripts"))           # config, utils

from _shared.hookio import recursion_guard, child_env

recursion_guard()

from _shared.gitctx import repo_root, in_worktree
from config import (
    DAILY_DIR,
    INDEX_FILE,
    LAST_COMPILE_FILE,
    LOCK_FILE,
    load_cfg,
)
from utils import should_compile

MAX_CONTEXT_CHARS = 20_000
MAX_LOG_LINES = 30


def _recent_daily() -> str:
    today = datetime.now(timezone.utc).astimezone()
    for offset in range(2):
        date = today - timedelta(days=offset)
        log_path = DAILY_DIR / f"{date.strftime('%Y-%m-%d')}.md"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            return "\n".join(lines[-MAX_LOG_LINES:])
    return "(no recent daily log)"


def build_context() -> str:
    today = datetime.now(timezone.utc).astimezone()
    parts = [f"## Today\n{today.strftime('%A, %B %d, %Y')}"]
    if INDEX_FILE.exists():
        parts.append(f"## Knowledge Base Index\n\n{INDEX_FILE.read_text(encoding='utf-8')}")
    else:
        parts.append("## Knowledge Base Index\n\n(empty — nothing compiled yet)")
    parts.append(f"## Recent Daily Log\n\n{_recent_daily()}")
    context = "\n\n---\n\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n...(truncated)"
    return context


def _last_compile_ts() -> float | None:
    if LAST_COMPILE_FILE.exists():
        try:
            return float(json.loads(LAST_COMPILE_FILE.read_text(encoding="utf-8"))["ts"])
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError):
            return None
    return None


def _newest_daily_mtime() -> float | None:
    if not DAILY_DIR.exists():
        return None
    mtimes = [p.stat().st_mtime for p in DAILY_DIR.glob("*.md")]
    return max(mtimes) if mtimes else None


def maybe_spawn_compile(age_hours: float) -> None:
    now = time.time()
    last_ts = _last_compile_ts()
    newest = _newest_daily_mtime()
    has_new_daily = newest is not None and (last_ts is None or newest > last_ts)
    lock_fresh = LOCK_FILE.exists() and (now - LOCK_FILE.stat().st_mtime) < age_hours * 3600

    if not should_compile(now, last_ts, age_hours, has_new_daily, False, lock_fresh):
        return

    cmd = ["uv", "run", "--directory", str(KDIR), "python", "scripts/compile.py", "--all"]
    try:
        subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=child_env(), start_new_session=True,
        )
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOCK_FILE.write_text(str(now), encoding="utf-8")
    except OSError:
        pass


def main() -> None:
    # Compile gate: main checkout only, never inside a worktree.
    if repo_root(str(KDIR)) and not in_worktree(str(KDIR)):
        try:
            maybe_spawn_compile(float(load_cfg().get("compile_age_hours", 6)))
        except Exception:
            pass  # injection must always proceed

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": build_context(),
        }
    }))


if __name__ == "__main__":
    main()
