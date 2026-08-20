"""Stdlib helpers for the compliance catalog: state, catalog readers, ID parsing,
and the plan-validation framework selector — no SDK import, so hooks and tests can
use them cheaply.
"""

from __future__ import annotations

import hashlib
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


def file_hash(path: Path) -> str:
    """First 16 hex chars of a file's SHA-256."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


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


def _load_json_obj(path: Path) -> dict:
    """Read a JSON object, or ``{}`` when absent/corrupt/not-an-object. Never raises."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def load_capability_catalog(catalog_dir: Path | None = None) -> dict:
    """The derived capability catalog (``catalog/capabilities.json``), or ``{}``.

    An install that never ran ``capabilities.py`` simply yields no capabilities —
    callers treat that as "capability layer not built", never as an error.
    """
    return _load_json_obj((catalog_dir or CATALOG_DIR) / "capabilities.json")


def load_stack(catalog_dir: Path | None = None) -> dict:
    """The chosen-component record (``catalog/stack.json``), or ``{}``."""
    return _load_json_obj((catalog_dir or CATALOG_DIR) / "stack.json")


def mandatory_ids(constraints: list[dict]) -> set[str]:
    """IDs of constraints flagged mandatory (default True when unspecified)."""
    return {c["id"] for c in constraints if c.get("mandatory", True)}


def referenced_ids(text: str) -> set[str]:
    """Constraint ids explicitly referenced in a block of text (e.g. a plan)."""
    return set(CONSTRAINT_ID_RE.findall(text))


def validation_frameworks(cfg: dict) -> list[str]:
    """Frameworks the plan-validator checks against: ``validate_frameworks`` when
    set, else all extracted ``frameworks``. Extraction is unaffected (it keeps
    reading ``frameworks``)."""
    return cfg.get("validate_frameworks") or cfg.get("frameworks", [])
