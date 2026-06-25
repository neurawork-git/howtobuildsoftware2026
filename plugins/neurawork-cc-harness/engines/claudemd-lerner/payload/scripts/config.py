"""Path constants and runtime config for the per-repo CLAUDE.md/docs learner.

ROOT_DIR is the lerner directory (``<repo>/<ldir>``) — it holds ONLY machinery
(hooks/scripts/_shared/daily). The learner's actual outputs (CLAUDE.md files and
the docs/ tree) live at the REPO ROOT, i.e. ``ROOT_DIR.parent``.

ROOT_DIR defaults to this file's grandparent, but a worktree-redirecting hook may
override it via the ``LERNER_ROOT`` environment variable so captured output lands
in the main checkout rather than a disposable worktree.

No timezone is hardcoded: local time is read from the system via ``astimezone``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(os.environ.get("LERNER_ROOT") or Path(__file__).resolve().parent.parent)
DAILY_DIR = ROOT_DIR / "daily"
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"
CONFIG_FILE = ROOT_DIR / "config.json"
STATE_FILE = SCRIPTS_DIR / "state.json"

# The learner writes here (repo root, NOT inside the lerner dir).
REPO_ROOT = ROOT_DIR.parent
CLAUDEMD_FILE = REPO_ROOT / "CLAUDE.md"

# Trigger coordination (the SessionStart 6h update gate).
LAST_UPDATE_FILE = SCRIPTS_DIR / "last-update.json"
LOCK_FILE = SCRIPTS_DIR / "cl-update.lock"

# ── Config defaults (overridden by <ldir>/config.json) ─────────────────
DEFAULT_CFG = {
    "lerner_dir": "claudemd-lerner",
    "model": "",
    "update_age_hours": 6,
    "claudemd_depth": 1,
    "docs_dir": "docs",
    "language": "en",
    "excluded_dirs": ["node_modules", ".venv", "dist", "build", ".git"],
}


def load_cfg() -> dict:
    """Merge ``<ldir>/config.json`` over the defaults. Never raises."""
    cfg = dict(DEFAULT_CFG)
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def docs_dir() -> Path:
    """The repo-root docs directory (per config), e.g. ``<repo>/docs``."""
    return REPO_ROOT / str(load_cfg().get("docs_dir", "docs"))


def now_iso() -> str:
    """Current local time, ISO 8601 with offset, second precision."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current local date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
