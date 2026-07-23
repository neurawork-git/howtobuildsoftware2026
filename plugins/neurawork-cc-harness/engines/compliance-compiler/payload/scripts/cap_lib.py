"""Pure (no-SDK) logic for capabilities.py: capability slug, catalog assembly,
the deterministic coverage gate, and the capabilities.md / index.md renderers.

Stdlib + config/utils only — no ``claude_agent_sdk`` import — so the clustering
output shape, the coverage math, and the markdown renderers are unit-testable
without the SDK or any network call.
"""

from __future__ import annotations

import re

from config import FRAMEWORK_TITLES, today_iso
from utils import load_constraints, mandatory_ids

# Fixed capability category vocabulary (shared by the cluster agents).
CATEGORIES = [
    "IAM",
    "Data Protection",
    "Logging & Monitoring",
    "Incident & Vulnerability",
    "Governance & Privacy Ops",
    "Change & SDLC",
    "Infrastructure & Network",
    "Vendor & Third-Party",
    "Business Continuity",
]

# Strip a trailing " (...)" / " — ..." / " - ..." clause the stack agent appends to
# the capability name, so its slug matches the clean cluster name.
_SLUG_SUFFIX_RE = re.compile(r"\s+[(—-].*$")
_SLUG_NONALNUM_RE = re.compile(r"[^a-z0-9]+")


def capability_slug(name: str) -> str:
    """Stable join/filename key for a capability name.

    Lowercases, drops any trailing parenthetical / em-dash / dash clause, and
    hyphenates. So 'Audit logging (SOC2 CC7)' and 'Audit logging' share the slug
    'audit-logging' — the stack↔capability join key.
    """
    base = _SLUG_SUFFIX_RE.sub("", name.strip().lower())
    return _SLUG_NONALNUM_RE.sub("-", base).strip("-")


def coverage_gap(capabilities: list[dict], constraints: list[dict]) -> list[str]:
    """Mandatory constraint ids covered by no capability's ``satisfies`` list.

    The deterministic verify gate: a non-empty result means the capability layer
    dropped a mandatory constraint and the run must fail.
    """
    covered = {cid for c in capabilities for cid in c.get("satisfies", [])}
    return sorted(mandatory_ids(constraints) - covered)


def assemble_catalog(
    clusters: dict[str, list[dict]],
    stacks: list[dict],
    catalog_dir=None,
    generated: str | None = None,
) -> dict:
    """Build the capabilities.json dict.

    clusters: ``{framework: [{name, category, description, satisfies:[ids]}]}``
    stacks:   ``[{capability, components:[{name,kind,why}], notes}]`` — joined onto
              capabilities by ``capability_slug`` (last entry wins on a slug clash,
              so callers order reused stacks first and fresh ones last).
    """
    generated = generated or today_iso()
    stack_by = {capability_slug(s["capability"]): s for s in stacks}
    frameworks: dict[str, dict] = {}
    for fw, caps in clusters.items():
        constraints = load_constraints([fw], catalog_dir)
        mand = mandatory_ids(constraints)
        covered = {cid for c in caps for cid in c.get("satisfies", [])}
        out_caps = []
        for c in caps:
            st = stack_by.get(capability_slug(c["name"]), {})
            out_caps.append({
                "name": c["name"],
                "category": c.get("category", ""),
                "description": c.get("description", ""),
                "satisfies": sorted(set(c.get("satisfies", []))),
                "stack": st.get("components", []),
                "stack_notes": st.get("notes", ""),
            })
        frameworks[fw] = {
            "capability_count": len(out_caps),
            "mandatory_covered": len(mand & covered),
            "mandatory_total": len(mand),
            "uncovered_mandatory_ids": sorted(mand - covered),
            "capabilities": out_caps,
        }
    return {
        "generated": generated,
        "source": "compliance-base/catalog/{gdpr,soc2,iso27001}.json",
        "method": "capabilities.py (cluster -> stack, deterministic verify)",
        "stack_target": "greenfield 2026",
        "structure": "per-framework (overlap kept)",
        "frameworks": frameworks,
    }


def merge_preserving(existing: dict, fresh: dict) -> dict:
    """Overlay freshly-derived frameworks onto the existing catalog.

    Any framework NOT re-derived this run (a ``--frameworks`` subset run, or a
    framework whose cluster agent failed) keeps its existing entry — the combined
    ``capabilities.json`` is never clobbered down to just this run's frameworks.
    """
    frameworks = dict(existing.get("frameworks", {}))
    frameworks.update(fresh.get("frameworks", {}))
    return {**fresh, "frameworks": frameworks}


def constraint_delta(current_ids: set[str], existing_caps: list[dict]) -> dict:
    """Diff a framework's current constraint ids against the ids its existing
    capabilities already cover.

    ``new_ids``      — constraints present now but covered by no capability (need clustering).
    ``orphaned_ids`` — constraints a capability still lists but the catalog dropped.
    ``unchanged``    — True when the covered id set already equals the current id set, so
                       the framework can be reused without any LLM call (a byte change to
                       the constraint file that added/removed no id — e.g. edited prose).
    """
    covered = {cid for c in existing_caps for cid in c.get("satisfies", [])}
    new_ids = sorted(current_ids - covered)
    orphaned_ids = sorted(covered - current_ids)
    return {
        "new_ids": new_ids,
        "orphaned_ids": orphaned_ids,
        "unchanged": not new_ids and not orphaned_ids,
    }


def prune_orphaned_ids(caps: list[dict], orphaned_ids) -> list[dict]:
    """Drop orphaned constraint ids from every capability's ``satisfies``; remove any
    capability left covering nothing. Returns new cap dicts (inputs untouched)."""
    drop = set(orphaned_ids)
    out: list[dict] = []
    for c in caps:
        kept = [cid for cid in c.get("satisfies", []) if cid not in drop]
        if not kept:
            continue
        out.append({**c, "satisfies": kept})
    return out


def merge_delta_capabilities(
    existing_caps: list[dict], assignments: dict, new_caps: list[dict]
) -> list[dict]:
    """Fold a delta-cluster result into an existing capability list.

    ``assignments`` — ``{capability_name: [new constraint ids]}`` appended to the named
    existing capability's ``satisfies`` (exact name, else ``capability_slug`` fallback).
    ``new_caps``    — brand-new ``{name, category, description, satisfies}`` capabilities,
                      appended with an empty ``stack``/``stack_notes`` for the stack stage.

    Inputs are never mutated. An existing capability whose ``satisfies`` set gains no id
    is copied through unchanged (same field values), so the caller can compare against the
    original by ``satisfies`` set to decide which capabilities need re-stacking.
    """
    add_by_name: dict[str, set[str]] = {}
    slug_to_name = {capability_slug(c["name"]): c["name"] for c in existing_caps}
    for name, ids in assignments.items():
        resolved = name if name in slug_to_name.values() else slug_to_name.get(capability_slug(name))
        if resolved is None:
            continue  # a name the agent invented but did not list under new_caps — skip
        add_by_name.setdefault(resolved, set()).update(ids)

    out: list[dict] = []
    for c in existing_caps:
        extra = add_by_name.get(c["name"])
        if extra:
            out.append({**c, "satisfies": sorted(set(c.get("satisfies", [])) | extra)})
        else:
            out.append({**c})
    for nc in new_caps:
        out.append({
            "name": nc["name"],
            "category": nc.get("category", ""),
            "description": nc.get("description", ""),
            "satisfies": sorted(set(nc.get("satisfies", []))),
            "stack": [],
            "stack_notes": "",
        })
    return out


def _component_label(comp: dict) -> str:
    """`name (license · internal-infra)` — surfaces the license and operator-side tag."""
    name = comp.get("name", "")
    tag = " · internal-infra" if comp.get("role") == "internal-infra" else ""
    inner = comp.get("license") or ("internal-infra" if tag else "")
    if not comp.get("license"):
        return f"{name} ({inner})" if inner else name
    return f"{name} ({inner}{tag})"


def render_capabilities_md(catalog: dict) -> str:
    """Render catalog/capabilities.md from the assembled capability catalog."""
    fws = catalog["frameworks"]
    lines = [
        "# Capability Catalog",
        "",
        f"Derived from the compliance constraint catalog on {catalog['generated']} "
        "via `capabilities.py` (cluster → stack → deterministic verify).",
        "Per-framework capability lists (cross-framework overlap intentionally kept). "
        "Each capability groups the constraints it satisfies and maps to recommended "
        "greenfield-2026 stack components.",
        "",
        "| Framework | Capabilities | Mandatory covered | Uncovered |",
        "|-----------|--------------|-------------------|-----------|",
    ]
    for fw, f in fws.items():
        lines.append(
            f"| {FRAMEWORK_TITLES.get(fw, fw)} | {f['capability_count']} | "
            f"{f['mandatory_covered']}/{f['mandatory_total']} | "
            f"{len(f['uncovered_mandatory_ids'])} |"
        )
    lines += ["", "---", ""]
    for fw, f in fws.items():
        lines.append(f"## {FRAMEWORK_TITLES.get(fw, fw)} — {f['capability_count']} capabilities")
        lines.append("")
        for c in f["capabilities"]:
            comps = "; ".join(_component_label(x) for x in c.get("stack", [])) or "—"
            lines.append(f"### {c['name']}")
            lines.append(f"*{c['category']}* · satisfies {len(c['satisfies'])} constraints")
            lines.append("")
            lines.append(c["description"])
            lines.append("")
            lines.append(f"**Stack (greenfield 2026):** {comps}")
            lines.append("")
            lines.append(f"<sub>{', '.join(c['satisfies'])}</sub>")
            lines.append("")
    return "\n".join(lines)


def render_index(constraint_meta: list[dict], capability_catalog: dict) -> str:
    """Render catalog/index.md: the constraints table + the Derived capabilities section.

    constraint_meta: ``[{framework, count, mandatory, generated}]`` read from each
    ``catalog/<fw>.json`` header, so the top table matches extract.py's output.
    """
    lines = [
        "# Compliance Catalog",
        "",
        "| Framework | Constraints | Mandatory | Generated |",
        "|-----------|-------------|-----------|-----------|",
    ]
    for m in constraint_meta:
        lines.append(f"| {m['framework']} | {m['count']} | {m['mandatory']} | {m['generated']} |")
    lines += [
        "",
        "## Derived capabilities",
        "",
        "Constraints distilled into per-framework **capabilities** (concrete technical "
        "building blocks) mapped to a greenfield 2026 stack — see "
        "[`capabilities.md`](capabilities.md) / [`capabilities.json`](capabilities.json).",
        "",
        "| Framework | Capabilities | Mandatory covered | Generated |",
        "|-----------|--------------|-------------------|-----------|",
    ]
    gen = capability_catalog["generated"]
    for fw, f in capability_catalog["frameworks"].items():
        lines.append(
            f"| {fw} | {f['capability_count']} | "
            f"{f['mandatory_covered']}/{f['mandatory_total']} | {gen} |"
        )
    lines.append("")
    return "\n".join(lines)
