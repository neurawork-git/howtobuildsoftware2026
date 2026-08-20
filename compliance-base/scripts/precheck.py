"""Fast, deterministic (no-LLM) structural check of a PRP plan vs the catalog.

Used inline by the PostToolUse validator hook (which has a hard timeout) to give
immediate feedback; the deep semantic check is delegated to ``validate.py``.
Pure stdlib + catalog readers — cheap to unit-test.
"""

from __future__ import annotations

import re
from pathlib import Path

import stack
from config import PLANS_SUBPATH
from utils import (
    load_capability_catalog,
    load_constraints,
    load_stack,
    mandatory_ids,
    referenced_ids,
    validation_frameworks,
)

_COMPLIANCE_SECTION_RE = re.compile(r"^##\s+Compliance", re.MULTILINE)

# The machine-readable capability declaration a plan carries in its `## Compliance`
# section, e.g. `**Capabilities**: gdpr/audit-logging, soc2/change-management` or
# `**Capabilities**: none — <reason>`. The declaration runs to the next blank line, so a
# wrapped list is read whole.
_CAP_DECL_RE = re.compile(
    r"^\*\*Capabilities\*\*:[ \t]*(?P<body>.+?)(?=\n[ \t]*\n|\Z)",
    re.MULTILINE | re.DOTALL,
)
_CAP_NONE_RE = re.compile(r"^`?none`?\b", re.IGNORECASE)
_CAP_REASON_SEP_RE = re.compile(r"[—–:-]")
# A capability key is `<framework>/<capability_slug>` — see stack.capability_key.
_CAP_KEY_RE = re.compile(r"[a-z0-9]+/[a-z0-9][a-z0-9-]*")


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


def declared_capabilities(plan_text: str) -> dict:
    """Parse a plan's ``**Capabilities**:`` declaration.

    Returns ``{"present", "none", "keys", "reason"}``. ``none`` is an explicit,
    accepted declaration ("this plan delivers no compliance capability") and carries
    the stated reason; absence of the line entirely is ``present: False``.

    Only comma-separated tokens that are *entirely* a capability key are taken, so
    prose that happens to contain a slash (a file path, a URL) never becomes a
    phantom key.
    """
    m = _CAP_DECL_RE.search(plan_text)
    if not m:
        return {"present": False, "none": False, "keys": [], "reason": ""}
    body = " ".join(m.group("body").split())
    if _CAP_NONE_RE.match(body):
        rest = _CAP_NONE_RE.sub("", body, count=1).strip()
        sep = _CAP_REASON_SEP_RE.search(rest)
        return {
            "present": True,
            "none": True,
            "keys": [],
            "reason": (rest[sep.end():] if sep else rest).strip(),
        }
    keys = set()
    for token in body.split(","):
        t = token.strip().removeprefix("and ").strip().strip("`").strip().lower()
        if _CAP_KEY_RE.fullmatch(t):
            keys.add(t)
    return {"present": True, "none": False, "keys": sorted(keys), "reason": ""}


def known_capabilities(frameworks: list[str], catalog_dir: Path | None) -> tuple[dict, dict]:
    """``(filtered capability catalog, {capability_key: capability})``.

    Restricted to the frameworks the validator checks, so a framework excluded via
    ``validate_frameworks`` makes its keys neither known nor required.
    """
    catalog = load_capability_catalog(catalog_dir)
    all_fws = catalog.get("frameworks") or {}
    filtered = {fw: all_fws[fw] for fw in frameworks if fw in all_fws}
    known = {
        stack.capability_key(fw, cap["name"]): cap
        for fw, f in filtered.items()
        for cap in f.get("capabilities", [])
        if cap.get("name")
    }
    return {"frameworks": filtered}, known


def capability_precheck(plan_text: str, cfg: dict, catalog_dir: Path | None = None) -> dict:
    """Deterministic capability signals for a plan: is the declaration there, do its
    keys resolve, and what does ``stack.json`` say about the ones it names.

    Deliberately does NOT enumerate every mandatory-linked capability: applicability
    is the validator agent's judgment (``validate.py``), not something a regex can
    decide, and a 62-item "undeclared" list on every plan write is noise nobody acts on.
    """
    catalog, known = known_capabilities(validation_frameworks(cfg), catalog_dir)
    decl = declared_capabilities(plan_text)
    choices = load_stack(catalog_dir).get("choices") or {}

    unknown_keys, declared_unchosen, declared_not_applicable = [], [], []
    for key in decl["keys"]:
        if key not in known:
            unknown_keys.append(key)
            continue
        entry = choices.get(key) or {}
        if not str(entry.get("chosen") or "").strip():
            declared_unchosen.append(key)
        if entry.get("applicable") is False:
            declared_not_applicable.append(key)

    return {
        "catalog_built": bool(known),
        "declaration_present": decl["present"],
        "declared_none": decl["none"],
        "none_reason": decl["reason"],
        "declared": decl["keys"],
        "unknown_keys": unknown_keys,
        "declared_unchosen": declared_unchosen,
        "declared_not_applicable": declared_not_applicable,
        "mandatory_linked_total": (
            len(stack.mandatory_linked_keys(catalog, catalog_dir)) if known else 0
        ),
    }


def capability_verdict(
    applicable_keys, declared_keys, mandatory_linked, known_keys=None
) -> dict:
    """Turn the validator agent's applicability judgment into a pass/fail.

    ``undeclared_mandatory`` — applicable, mandatory-linked, and not declared by the
    plan. Non-empty means the plan silently drops a capability its own content makes
    applicable, and ``validate.py`` exits non-zero.

    ``applicable_keys`` is agent output: when ``known_keys`` is given it is filtered
    against it first, so a key the agent invented can neither inflate nor deflate the
    verdict.
    """
    applicable = set(applicable_keys)
    if known_keys is not None:
        applicable &= set(known_keys)
    declared = set(declared_keys)
    return {
        "applicable_total": len(applicable),
        "undeclared_mandatory": sorted((applicable & set(mandatory_linked)) - declared),
        "declared_not_applicable": sorted(declared - applicable),
    }


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
        "capabilities": capability_precheck(plan_text, cfg, catalog_dir),
    }
