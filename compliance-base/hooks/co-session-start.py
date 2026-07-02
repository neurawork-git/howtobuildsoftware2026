"""SessionStart hook — inject the compliance catalog index, and maybe bootstrap it.

Two jobs, both fast:
  1. Print the catalog index (applicable frameworks) as additionalContext.
  2. If the catalog is missing (or a completion stamp is older than the configured
     age), spawn extract.py detached to (re)build it. Skipped in a worktree.

Never blocks: extraction is a fire-and-forget Popen; JSON is printed right after.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))                       # _shared
sys.path.insert(0, str(KDIR / "scripts"))           # config, utils

from _shared.hookio import child_env, recursion_guard

recursion_guard()

from _shared.gitctx import in_worktree, repo_root
from config import INDEX_FILE, LAST_EXTRACT_FILE, LOCK_FILE, load_cfg
from utils import catalog_is_missing, should_extract

MAX_CONTEXT_CHARS = 8_000


def build_context() -> str:
    today = datetime.now(timezone.utc).astimezone()
    parts = [f"## Today\n{today.strftime('%A, %B %d, %Y')}"]
    if INDEX_FILE.exists():
        parts.append(f"## Compliance Catalog\n\n{INDEX_FILE.read_text(encoding='utf-8')}")
        parts.append("When writing a PRP plan, cover the applicable mandatory "
                     "constraints; plan writes are checked automatically.")
    else:
        parts.append("## Compliance Catalog\n\n(empty — run "
                     "`/neurawork-cc-harness:co-extract` to build it)")
    context = "\n\n---\n\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n...(truncated)"
    return context


def _last_extract_ts() -> float | None:
    if LAST_EXTRACT_FILE.exists():
        try:
            return float(json.loads(LAST_EXTRACT_FILE.read_text(encoding="utf-8"))["ts"])
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError):
            return None
    return None


def maybe_spawn_extract(cfg: dict) -> None:
    age_hours = float(cfg.get("extract_age_hours", 168))
    now = time.time()
    last_ts = _last_extract_ts()
    missing = catalog_is_missing(cfg.get("frameworks", []))
    lock_fresh = LOCK_FILE.exists() and (now - LOCK_FILE.stat().st_mtime) < age_hours * 3600

    if not should_extract(now, last_ts, age_hours, missing, False, lock_fresh):
        return

    cmd = ["uv", "run", "--directory", str(KDIR), "python", "scripts/extract.py"]
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
    # Bootstrap gate: main checkout only, never inside a worktree.
    if repo_root(str(KDIR)) and not in_worktree(str(KDIR)):
        try:
            maybe_spawn_extract(load_cfg())
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
