"""Stdlib helpers for the learner: state, hashing, log listing, the update gate.

Hosts ``should_update`` — the pure decision behind the SessionStart 6h update
gate — kept here (no SDK import) so hooks and tests can use it cheaply. The
learner maintains no wiki, so there are no wikilink/index helpers here.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from config import DAILY_DIR, STATE_FILE


# ── State ─────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load state.json, or a fresh skeleton if absent/corrupt."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"ingested": {}, "updated_count": 0, "total_cost": 0.0}


def save_state(state: dict) -> None:
    """Write state.json atomically (tmp + os.replace)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ── Hashing ───────────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    """First 16 hex chars of a file's SHA-256."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


# ── Reading the capture store ─────────────────────────────────────────

def list_raw_files() -> list[Path]:
    """Every daily log file, sorted."""
    if not DAILY_DIR.exists():
        return []
    return sorted(DAILY_DIR.glob("*.md"))


# ── Update trigger gate (pure) ────────────────────────────────────────

def should_update(
    now: float,
    last_ts: float | None,
    age_hours: float,
    has_new_daily: bool,
    in_wt: bool,
    lock_fresh: bool,
) -> bool:
    """Whether SessionStart should spawn a background update.

    Eligible only when there is new daily content, we are NOT in a worktree, no
    fresh lock is holding, and the last update is at least ``age_hours`` old
    (a missing last-update stamp counts as infinitely old).
    """
    if in_wt or lock_fresh or not has_new_daily:
        return False
    if last_ts is None:
        return True
    return (now - last_ts) >= age_hours * 3600
