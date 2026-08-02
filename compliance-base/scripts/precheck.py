"""Fast, deterministic (no-LLM) structural check of a PRP plan vs the catalog.

Used inline by the PostToolUse validator hook (which has a hard timeout) to give
immediate feedback; the deep semantic check is delegated to ``validate.py``.
Pure stdlib + catalog readers — cheap to unit-test.
"""

from __future__ import annotations

import re
from pathlib import Path

from config import DEFAULT_CFG
from utils import load_constraints, mandatory_ids, referenced_ids, validation_frameworks

_COMPLIANCE_SECTION_RE = re.compile(r"^##\s+Compliance", re.MULTILINE)
_MISSING = object()


def _cfg_strings(cfg: dict, key: str) -> tuple[str, ...]:
    """A plan-matching config value as a tuple of strings (accepts one or many).

    Falls back to the default when the key is absent or not a string/list, so an
    ADOPT install whose ``config.json`` predates these keys keeps the documented
    behaviour instead of silently matching nothing. An explicitly empty list is
    honoured — that is how you switch the matcher off without uninstalling.
    """
    value = cfg.get(key, _MISSING)
    if not isinstance(value, (str, list, tuple)):
        value = DEFAULT_CFG[key]
    if isinstance(value, str):
        value = [value]
    return tuple(v.strip() for v in value if isinstance(v, str) and v.strip())


def _segments(subpath: str) -> tuple[str, ...]:
    """Split a configured subpath into path segments, tolerating either slash
    style and stray separators (``./.planning/phases/`` → ``.planning``, ``phases``)."""
    return tuple(s for s in subpath.replace("\\", "/").split("/") if s and s != ".")


def is_plan_path(path_str: str, repo_root: Path | str, cfg: dict | None = None) -> bool:
    """True iff ``path_str`` is a live plan file (not an archived one).

    Which files qualify is configurable via ``plans_subpath``, ``plan_suffix`` and
    ``plan_archive_segments`` (see ``config.DEFAULT_CFG``). Omitting ``cfg`` applies
    those defaults, i.e. the PRP layout ``.claude/PRPs/plans/*.plan.md``.
    """
    if not path_str:
        return False
    cfg = cfg if isinstance(cfg, dict) else {}
    p = Path(path_str)
    if not any(p.name.endswith(s) for s in _cfg_strings(cfg, "plan_suffix")):
        return False
    try:
        rel = p.resolve().relative_to(Path(repo_root).resolve())
    except (ValueError, OSError):
        return False
    parts = rel.parts
    archived = _cfg_strings(cfg, "plan_archive_segments")
    for subpath in _cfg_strings(cfg, "plans_subpath"):
        plans = _segments(subpath)
        if plans and parts[: len(plans)] == plans:
            return not any(seg in archived for seg in parts[len(plans):])
    return False


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
