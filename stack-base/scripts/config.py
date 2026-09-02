"""Path constants and runtime config for the per-repo product-scoping engine.

ROOT_DIR is the stack directory (``<repo>/<stack_dir>``). It defaults to this
file's grandparent, but a worktree-redirecting hook may override it via the
``STACK_ROOT`` environment variable so output lands in the main checkout rather
than a disposable worktree — the same contract ``compliance-base`` uses with
``COMPLIANCE_ROOT``.

This engine owns machinery only. The data artifact it writes,
``<compliance_dir>/catalog/stack.json``, is owned by ``compliance-compiler``; see
``compliance_root()`` for how it is located.

No timezone is hardcoded: local time is read from the system via ``astimezone``.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(os.environ.get("STACK_ROOT") or Path(__file__).resolve().parent.parent)
REPORTS_DIR = ROOT_DIR / "reports"
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
SHARDS_DIR = ROOT_DIR / ".shards"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"
CONFIG_FILE = ROOT_DIR / "config.json"
STATE_FILE = SCRIPTS_DIR / "state.json"
# The component gate's spawn ledger: one entry per document, carrying the content
# hash that last earned an LLM run and what that run concluded.
GATE_STATE_FILE = REPORTS_DIR / ".state.json"

# ── Config defaults (overridden by <stack_dir>/config.json) ────────────
DEFAULT_CFG = {
    "stack_dir": "stack-base",
    "compliance_dir": "compliance-base",
    "model": "",
    "max_concurrency": 12,
    "product_file": "product.md",
    # Which files the gate treats as a PRD / a plan. Each takes a string or a list; a
    # "*" segment matches exactly one path segment (here: the PRP_HOME store key). A
    # repo with another convention — GSD's `.planning/phases/<phase>/NN-NN-PLAN.md` —
    # overrides them; the same three keys exist in `compliance-base/config.json`.
    "prds_subpath": [".claude/PRPs/prds", ".claude/PRPs/*/prds"],
    "plans_subpath": [".claude/PRPs/plans", ".claude/PRPs/*/plans"],
    "prd_suffix": ".prd.md",
    "plan_suffix": ".plan.md",
    "doc_archive_segments": ["completed"],
    "validate_mode": {"prd": "warn", "plan": "warn"},
}


def load_cfg() -> dict:
    """Merge ``<stack_dir>/config.json`` over the defaults. Never raises."""
    cfg = dict(DEFAULT_CFG)
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def gate_mode(cfg: dict, kind: str) -> str:
    """``warn`` | ``block`` for one document kind, from ``validate_mode``.

    Tolerates a bare string (``"warn"``) as well as the per-kind dict, and falls
    back to ``warn`` for anything else: this is read inside a PostToolUse hook, and
    a hand-edited config must not be able to crash a session's tool call.
    """
    mode = cfg.get("validate_mode")
    if isinstance(mode, dict):
        value = mode.get(kind, "")
    elif isinstance(mode, str):
        value = mode
    else:
        value = ""
    value = str(value or "").strip().lower()
    return value if value in {"warn", "block"} else "warn"


def compliance_root(cfg: dict) -> Path:
    """The sibling compliance install this engine reads from and writes through.

    Resolved against the repo root (``ROOT_DIR.parent``) so a redirected
    ``STACK_ROOT`` finds the compliance install next to it, not next to the
    original checkout.
    """
    return ROOT_DIR.parent / str(cfg.get("compliance_dir") or "compliance-base")


def product_file(cfg: dict) -> Path:
    """The tracked product description this scoping pass is derived from."""
    return ROOT_DIR / str(cfg.get("product_file") or "product.md")


def now_iso() -> str:
    """Current local time, ISO 8601 with offset, second precision."""
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current local date as YYYY-MM-DD."""
    return datetime.now(UTC).astimezone().strftime("%Y-%m-%d")
