"""Fast, deterministic (no-LLM) structural check of a PRP plan vs the catalog.

Used inline by the PostToolUse validator hook (which has a hard timeout) to give
immediate feedback; the deep semantic check is delegated to ``validate.py``.
Pure stdlib + catalog readers — cheap to unit-test.
"""

from __future__ import annotations

import re
from pathlib import Path

from config import PLANS_SUBPATH
from utils import load_constraints, mandatory_ids, referenced_ids, validation_frameworks

_COMPLIANCE_SECTION_RE = re.compile(r"^##\s+Compliance", re.MULTILINE)


def is_plan_path(path_str: str, repo_root: Path | str) -> bool:
    """True iff ``path_str`` is a live PRP plan file (not an archived one)."""
    if not path_str:
        return False
    p = Path(path_str)
    if not p.name.endswith(".plan.md"):
        return False
    try:
        rel = p.resolve().relative_to(Path(repo_root).resolve())
    except (ValueError, OSError):
        return False
    plans = tuple(PLANS_SUBPATH.split("/"))
    parts = rel.parts
    if parts[: len(plans)] != plans:
        return False
    return "completed" not in parts[len(plans):]


def precheck(plan_text: str, cfg: dict, catalog_dir: Path | None = None) -> dict:
    """Deterministic structural signals for a plan against the catalog."""
    frameworks = validation_frameworks(cfg)
    constraints = load_constraints(frameworks, catalog_dir)
    mand = mandatory_ids(constraints)
    refs = referenced_ids(plan_text)
    return {
        "catalog_built": bool(constraints),
        "frameworks": frameworks,
        "has_compliance_section": bool(_COMPLIANCE_SECTION_RE.search(plan_text)),
        "referenced_ids": sorted(refs),
        "mandatory_total": len(mand),
        "missing_mandatory_ids": sorted(mand - refs) if constraints else [],
    }
