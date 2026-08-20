"""Pure (no-SDK) logic for scope.py: the capability universe, the mandatory-safety
gate, and the scope-report renderer.

Stdlib only — no ``claude_agent_sdk`` import and no import of any
``compliance-base`` module — so the gate that decides whether a scoping run may
touch ``stack.json`` is unit-testable without an API key, and so this engine stays
independently installable. The ~10 lines of constraint reading below deliberately
duplicate ``compliance-base``'s readers rather than importing them: ``stack.py``
resolves its paths through a module named ``config``, and this engine has its own,
so an in-process import would silently bind the wrong catalog directory.

The capability key set is never re-derived here. It is read straight out of
``stack.json``, whose keys ``compliance-compiler`` owns, and capability
descriptions are joined on by exact framework + name. Re-implementing the slug
rule in a second engine would be a silent divergence waiting to happen.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def product_hash(text: str) -> str:
    """First 16 hex chars of the product description's SHA-256.

    Matches ``compliance-base``'s ``utils.file_hash`` width so the value recorded
    in ``stack.json``'s ``scoped_from`` reads like every other hash in the catalog.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def mandatory_ids_for(framework: str, catalog_dir: Path) -> set[str]:
    """IDs of a framework's mandatory constraints (``mandatory`` defaults to True).

    A missing or corrupt catalog file yields an empty set rather than raising: an
    unbuilt framework simply contributes no mandatory constraints to the gate.
    """
    path = Path(catalog_dir) / f"{framework}.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return {
        c["id"] for c in data.get("constraints", [])
        if isinstance(c, dict) and c.get("id") and c.get("mandatory", True)
    }


def capability_universe(stack: dict, capabilities: dict) -> list[dict]:
    """Every capability this product must decide on, in ``stack.json`` key order.

    The key set comes from ``stack.json`` — the closed, authoritative identity set.
    ``description`` and ``category`` are joined from ``capabilities.json`` by exact
    framework + capability name; a capability the catalog no longer describes still
    appears (with empty prose) so it cannot vanish from the decision set.
    """
    described: dict[tuple[str, str], dict] = {}
    for fw, f in capabilities.get("frameworks", {}).items():
        for cap in f.get("capabilities", []):
            described[(fw, cap.get("name", ""))] = cap
    out: list[dict] = []
    for key, entry in (stack.get("choices") or {}).items():
        fw = entry.get("framework", "")
        name = entry.get("capability", "")
        cap = described.get((fw, name), {})
        out.append({
            "key": key,
            "framework": fw,
            "capability": name,
            "mandatory_linked": bool(entry.get("mandatory_linked")),
            "category": cap.get("category", ""),
            "description": cap.get("description", ""),
            "satisfies": list(cap.get("satisfies", [])),
        })
    return out


def _covering_keys(universe: list[dict]) -> dict[str, list[str]]:
    """Constraint id → the capability keys whose ``satisfies`` list contains it."""
    covering: dict[str, list[str]] = {}
    for u in universe:
        for cid in u["satisfies"]:
            covering.setdefault(cid, []).append(u["key"])
    return covering


def safety_gate(
    universe: list[dict],
    decisions: dict,
    mandatory_by_framework: dict[str, set[str]],
) -> dict:
    """The invariant, as set math: no mandatory constraint may be dropped silently.

    ``decisions`` maps a capability key to ``{"applicable": bool, "reason": str}``.
    A mandatory constraint passes when at least one capability covering it stays
    applicable, or when **every** covering capability was ruled out **with a
    reason** — that second case is a justified drop and is reported, never hidden.
    Anything else is a failure and the caller must not write to ``stack.json``.

    ``uncovered_upstream`` is informational: a mandatory constraint no capability
    covers at all is a hole in ``capabilities.json``, not in this scoping pass.
    """
    keys = {u["key"] for u in universe}
    given = set(decisions)
    missing = sorted(keys - given)
    unknown = sorted(given - keys)
    blank_reasons = sorted(
        k for k in keys & given
        if not (decisions[k] or {}).get("applicable", True)
        and not str((decisions[k] or {}).get("reason") or "").strip()
    )

    covering = _covering_keys(universe)
    unjustified_mandatory: list[dict] = []
    justified_drops: list[dict] = []
    uncovered_upstream: list[str] = []
    for mand in mandatory_by_framework.values():
        for cid in sorted(mand):
            cover = covering.get(cid, [])
            if not cover:
                uncovered_upstream.append(cid)
                continue
            if any((decisions.get(k) or {}).get("applicable", True) for k in cover):
                continue
            unreasoned = sorted(
                k for k in cover
                if not str((decisions.get(k) or {}).get("reason") or "").strip()
            )
            if unreasoned:
                unjustified_mandatory.append({"constraint": cid, "capabilities": unreasoned})
            else:
                justified_drops.append({"constraint": cid, "capabilities": sorted(cover)})

    return {
        "ok": not (missing or unknown or blank_reasons or unjustified_mandatory),
        "missing_decisions": missing,
        "unknown_decisions": unknown,
        "blank_reasons": blank_reasons,
        "unjustified_mandatory": unjustified_mandatory,
        "justified_drops": sorted(justified_drops, key=lambda d: d["constraint"]),
        "uncovered_upstream": sorted(uncovered_upstream),
    }


def decisions_payload(decisions: dict, scoped_from: str) -> dict:
    """The file ``stack.py --apply-scope`` consumes.

    Translates this engine's internal ``reason`` into the schema owner's
    ``applicability_reason``; that mapping lives here, in one place.
    """
    return {
        "scoped_from": scoped_from,
        "decisions": {
            key: {
                "applicable": bool((d or {}).get("applicable", True)),
                "applicability_reason": str((d or {}).get("reason") or "").strip(),
            }
            for key, d in sorted(decisions.items())
        },
    }


def render_scope_report(
    universe: list[dict],
    decisions: dict,
    gate: dict,
    scoped_from: str,
    generated: str,
    refuted: list[dict] | None = None,
    product_path: str = "",
) -> str:
    """Render reports/scope-<date>.md — what was ruled out, and on what grounds."""
    refuted = refuted or []
    by_key = {u["key"]: u for u in universe}
    ruled_out = sorted(
        k for k in by_key
        if k in decisions and not (decisions[k] or {}).get("applicable", True)
    )
    lines = [
        "# Product Scope Report",
        "",
        (f"Generated {generated} by `scripts/scope.py` from `{product_path or 'product.md'}` "
         f"(scope hash `{scoped_from}`)."),
        (f"{len(by_key)} capabilities in scope-set, {len(by_key) - len(ruled_out)} applicable, "
         f"{len(ruled_out)} ruled out."),
        "",
    ]
    if not gate["ok"] or refuted:
        lines += ["> **This run wrote nothing.** `stack.json` is unchanged.", ""]

    if refuted:
        lines += [
            f"## Refuted decisions ({len(refuted)})",
            "",
            "The product description itself contradicts these “not applicable” claims:",
            "",
        ]
        for r in refuted:
            cap = by_key.get(r.get("key", ""), {}).get("capability", r.get("key", ""))
            reason = str((decisions.get(r.get("key", "")) or {}).get("reason") or "")
            lines.append(f"- **{cap}** (`{r.get('key', '')}`)")
            lines.append(f"  - claimed: {reason or '—'}")
            lines.append(f"  - contradicted by: {r.get('evidence', '—')}")
        lines.append("")

    failures = [
        ("Capabilities with no decision", gate["missing_decisions"]),
        ("Decisions for unknown capabilities", gate["unknown_decisions"]),
        ("Ruled out with no reason", gate["blank_reasons"]),
    ]
    if any(items for _, items in failures) or gate["unjustified_mandatory"]:
        lines += ["## Gate failures", ""]
        for title, items in failures:
            if items:
                lines.append(f"**{title} ({len(items)})**")
                lines.append("")
                lines += [f"- `{k}`" for k in items]
                lines.append("")
        if gate["unjustified_mandatory"]:
            lines.append(
                f"**Mandatory constraints dropped without a reason "
                f"({len(gate['unjustified_mandatory'])})**"
            )
            lines.append("")
            for item in gate["unjustified_mandatory"]:
                caps = ", ".join(f"`{k}`" for k in item["capabilities"])
                lines.append(f"- `{item['constraint']}` — only covered by {caps}")
            lines.append("")

    if ruled_out:
        lines += [f"## Not applicable ({len(ruled_out)})", ""]
        for key in ruled_out:
            u = by_key[key]
            reason = str((decisions[key] or {}).get("reason") or "").strip() or "—"
            flag = " *(mandatory-linked)*" if u["mandatory_linked"] else ""
            lines.append(f"- **{u['capability']}** (`{key}`){flag} — {reason}")
        lines.append("")

    if gate["justified_drops"]:
        lines += [
            f"## Mandatory constraints traced to a justified drop ({len(gate['justified_drops'])})",
            "",
            ("Every capability covering these was ruled out, each with a recorded reason. "
             "This is the audit trail for narrowing the compliance surface:"),
            "",
        ]
        for item in gate["justified_drops"]:
            caps = ", ".join(f"`{k}`" for k in item["capabilities"])
            lines.append(f"- `{item['constraint']}` — via {caps}")
        lines.append("")

    if gate["uncovered_upstream"]:
        lines += [
            f"## Uncovered upstream ({len(gate['uncovered_upstream'])})",
            "",
            ("These mandatory constraints are covered by no capability at all — a gap in "
             "`capabilities.json`, not in this scoping pass. Re-run `scripts/capabilities.py`:"),
            "",
        ]
        lines += [f"- `{cid}`" for cid in gate["uncovered_upstream"]]
        lines.append("")

    return "\n".join(lines)
