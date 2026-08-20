"""Path constants and runtime config for the per-repo compliance catalog.

ROOT_DIR is the compliance directory (``<repo>/<catalog_dir>``). It defaults to
this file's grandparent, but a worktree-redirecting hook may override it via the
``COMPLIANCE_ROOT`` environment variable so output lands in the main checkout
rather than a disposable worktree.

No timezone is hardcoded: local time is read from the system via ``astimezone``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(os.environ.get("COMPLIANCE_ROOT") or Path(__file__).resolve().parent.parent)
CATALOG_DIR = ROOT_DIR / "catalog"
SHARDS_DIR = CATALOG_DIR / ".shards"
REPORTS_DIR = ROOT_DIR / "reports"
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"
CONFIG_FILE = ROOT_DIR / "config.json"

INDEX_FILE = CATALOG_DIR / "index.md"
STATE_FILE = SCRIPTS_DIR / "state.json"

# Completion stamp written by extract.py after a run.
LAST_EXTRACT_FILE = SCRIPTS_DIR / "last-extract.json"

# PRP plan files the validator hook checks (relative to the REPO root, which is
# ROOT_DIR.parent for a top-level catalog dir).
PLANS_SUBPATH = ".claude/PRPs/plans"

# prp-core resolves its artifact store as ``"${PRP_HOME:-$HOME/.prp}/<repo-name>-<hash>"``,
# so with PRP_HOME=".claude/PRPs" (what install.py sets) plans land one level deeper:
# ``.claude/PRPs/<repo-name>-<hash>/plans/``. Both layouts are checked — see
# precheck.is_plan_path.
PRP_SUBPATH = ".claude/PRPs"

# Display names for the supported frameworks.
FRAMEWORK_TITLES = {
    "gdpr": "GDPR / DSGVO — Regulation (EU) 2016/679",
    "soc2": "SOC 2 — AICPA Trust Services Criteria",
    "iso27001": "ISO/IEC 27001:2022 — Annex A controls",
}

# ── Config defaults (overridden by <catalog_dir>/config.json) ──────────
DEFAULT_CFG = {
    "catalog_dir": "compliance-base",
    "model": "",
    "frameworks": ["gdpr", "soc2", "iso27001"],
    "validate_frameworks": [],  # empty → validate plans against all `frameworks`
    "max_concurrency": 12,
    "validate_mode": "warn",
}


def load_cfg() -> dict:
    """Merge ``<catalog_dir>/config.json`` over the defaults. Never raises."""
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
