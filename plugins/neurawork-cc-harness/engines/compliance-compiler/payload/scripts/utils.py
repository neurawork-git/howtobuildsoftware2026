"""Stdlib helpers for the compliance catalog: state, catalog readers, ID parsing.

Also hosts ``should_extract`` — the pure decision behind the SessionStart
bootstrap/age gate — kept here (no SDK import) so hooks and tests can use it
cheaply.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from config import CATALOG_DIR, STATE_FILE

# A constraint id looks like GDPR-ART5-01 / SOC2-CC6-03 / ISO-A8-12.
CONSTRAINT_ID_RE = re.compile(r"\b(?:GDPR|SOC2|ISO)-[A-Z0-9]+(?:-[0-9]+)?\b")


# ── State ─────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load state.json, or a fresh skeleton if absent/corrupt."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"extracted": {}, "total_cost": 0.0}


def save_state(state: dict) -> None:
    """Write state.json atomically (tmp + os.replace)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ── Catalog readers ───────────────────────────────────────────────────

def catalog_file(framework: str, catalog_dir: Path | None = None) -> Path:
    """Path to a framework's catalog JSON (``catalog/<framework>.json``)."""
    return (catalog_dir or CATALOG_DIR) / f"{framework}.json"


def load_constraints(frameworks: list[str], catalog_dir: Path | None = None) -> list[dict]:
    """Every constraint across the given frameworks' catalog files.

    Missing or corrupt files are skipped (never raises) — an unbuilt catalog
    simply yields no constraints.
    """
    out: list[dict] = []
    for fw in frameworks:
        path = catalog_file(fw, catalog_dir)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for c in data.get("constraints", []):
            if isinstance(c, dict) and c.get("id"):
                out.append(c)
    return out


def mandatory_ids(constraints: list[dict]) -> set[str]:
    """IDs of constraints flagged mandatory (default True when unspecified)."""
    return {c["id"] for c in constraints if c.get("mandatory", True)}


def referenced_ids(text: str) -> set[str]:
    """Constraint ids explicitly referenced in a block of text (e.g. a plan)."""
    return set(CONSTRAINT_ID_RE.findall(text))


def catalog_is_missing(frameworks: list[str], catalog_dir: Path | None = None) -> bool:
    """True when no configured framework has a catalog file yet."""
    return not any(catalog_file(fw, catalog_dir).exists() for fw in frameworks)


# ── Extract trigger gate (pure) ───────────────────────────────────────

def should_extract(
    now: float,
    last_ts: float | None,
    age_hours: float,
    catalog_missing: bool,
    in_wt: bool,
    lock_fresh: bool,
) -> bool:
    """Whether SessionStart should spawn a background extraction.

    Never in a worktree or while a fresh lock holds. Otherwise: build when the
    catalog is missing (bootstrap); when it already exists, only re-extract if a
    completion stamp is present and older than ``age_hours`` (a missing stamp on
    an existing catalog means it was built manually — leave it alone, no
    surprise recurring cost).
    """
    if in_wt or lock_fresh:
        return False
    if catalog_missing:
        return True
    if last_ts is None:
        return False
    return (now - last_ts) >= age_hours * 3600
