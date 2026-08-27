"""Path constants and runtime config for the per-repo knowledge base.

ROOT_DIR is the knowledge directory (``<repo>/<kdir>``). It defaults to this
file's grandparent, but a worktree-redirecting hook may override it via the
``KNOWLEDGE_ROOT`` environment variable so captured output lands in the main
checkout rather than a disposable worktree.

No timezone is hardcoded: local time is read from the system via ``astimezone``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from research_directive import DEFAULT_PROMPT_MATCH, DEFAULT_SKILL_MATCH

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(os.environ.get("KNOWLEDGE_ROOT") or Path(__file__).resolve().parent.parent)
DAILY_DIR = ROOT_DIR / "daily"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
CONCEPTS_DIR = KNOWLEDGE_DIR / "concepts"
CONNECTIONS_DIR = KNOWLEDGE_DIR / "connections"
QA_DIR = KNOWLEDGE_DIR / "qa"
REPORTS_DIR = ROOT_DIR / "reports"
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"
CONFIG_FILE = ROOT_DIR / "config.json"

INDEX_FILE = KNOWLEDGE_DIR / "index.md"
LOG_FILE = KNOWLEDGE_DIR / "log.md"
STATE_FILE = SCRIPTS_DIR / "state.json"

# Trigger coordination (the SessionStart 6h compile gate).
LAST_COMPILE_FILE = SCRIPTS_DIR / "last-compile.json"
LOCK_FILE = SCRIPTS_DIR / "kc-compile.lock"

# ── Config defaults (overridden by <kdir>/config.json) ─────────────────
DEFAULT_CFG = {
    "knowledge_dir": "knowledge-base",
    "model": "",
    "compile_age_hours": 6,
    # Kill switch for the kb-researcher spawn directive. Read live by both injecting
    # hooks, so `false` here disables them without an installer re-run.
    "research_directive": True,
    # The two match patterns. Their defaults and the reasoning behind their anchoring
    # live in research_directive.py, next to the code that applies them.
    "research_skill_match": DEFAULT_SKILL_MATCH,
    "research_prompt_match": DEFAULT_PROMPT_MATCH,
}


def load_cfg() -> dict:
    """Merge ``<kdir>/config.json`` over the defaults. Never raises."""
    cfg = dict(DEFAULT_CFG)
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def now_iso() -> str:
    """Current local time, ISO 8601 with offset, second precision."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current local date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
