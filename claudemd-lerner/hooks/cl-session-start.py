"""SessionStart hook — maybe spawn an update.

One job: if the last update is older than the configured age AND there is new
daily content AND no fresh lock, spawn update.py detached. Skipped in a worktree.

No context injection — CLAUDE.md + docs/ are already read at session start, so
re-injecting them here would only crowd the context (the knowledge-compiler's
concepts inject is kept free for that). The update is a fire-and-forget Popen.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))                       # _shared
sys.path.insert(0, str(KDIR / "scripts"))           # config, utils

from _shared.hookio import recursion_guard, child_env

recursion_guard()

from _shared.gitctx import repo_root, in_worktree
from config import (
    DAILY_DIR,
    LAST_UPDATE_FILE,
    LOCK_FILE,
    load_cfg,
)
from utils import should_update


def _last_update_ts() -> float | None:
    if LAST_UPDATE_FILE.exists():
        try:
            return float(json.loads(LAST_UPDATE_FILE.read_text(encoding="utf-8"))["ts"])
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError):
            return None
    return None


def _newest_daily_mtime() -> float | None:
    if not DAILY_DIR.exists():
        return None
    mtimes = [p.stat().st_mtime for p in DAILY_DIR.glob("*.md")]
    return max(mtimes) if mtimes else None


def maybe_spawn_update(age_hours: float) -> None:
    now = time.time()
    last_ts = _last_update_ts()
    newest = _newest_daily_mtime()
    has_new_daily = newest is not None and (last_ts is None or newest > last_ts)
    lock_fresh = LOCK_FILE.exists() and (now - LOCK_FILE.stat().st_mtime) < age_hours * 3600

    if not should_update(now, last_ts, age_hours, has_new_daily, False, lock_fresh):
        return

    cmd = ["uv", "run", "--directory", str(KDIR), "python", "scripts/update.py", "--all"]
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
    # Update gate: main checkout only, never inside a worktree.
    if repo_root(str(KDIR)) and not in_worktree(str(KDIR)):
        try:
            maybe_spawn_update(float(load_cfg().get("update_age_hours", 6)))
        except Exception:
            pass


if __name__ == "__main__":
    main()
