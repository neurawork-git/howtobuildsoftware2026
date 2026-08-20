"""Pure (no-SDK) logic for rank.py: the rankable universe, the license policy, the
ranking gate, and the rank-report renderer.

Stdlib only — no ``claude_agent_sdk`` import and no import of any
``compliance-base`` module — for the same reasons ``scope_lib`` states: the gate
that decides whether a ranking run may touch ``stack.json`` must be testable
without an API key, and a cross-engine import would bind the wrong ``config``.

Ranking is an **ordering**, not a selection. A capability's component pool is
``stack.json``'s ``options``, which ``compliance-compiler`` recomputes from the
catalog; a ranking must name exactly those components, once each. That makes the
gate one set comparison and leaves no room for a silent omission — the failure
mode the whole engine exists to remove. Narrowing the pool is the catalog's job,
and the human's at selection time; it is never this pass's.
"""

from __future__ import annotations

# Licenses whose catalog spelling differs from the policy's. The catalog records
# the precise SPDX id, the policy records the class it belongs to; without this
# the gate would reject components the policy plainly permits. Deliberately tiny
# and explicit — it maps spellings, it does not interpret license terms.
_LICENSE_ALIASES = {
    "CC0-1.0": "CC0",
}
_LGPL_CLASS = "LGPL (dynamic)"


def normalize_license(license_text: object) -> str:
    """The policy's spelling of a catalog license id, or the id unchanged."""
    text = str(license_text or "").strip()
    if text in _LICENSE_ALIASES:
        return _LICENSE_ALIASES[text]
    if text.startswith("LGPL"):
        return _LGPL_CLASS
    return text


def license_check(component: dict, policy: dict) -> str:
    """``ok`` | ``exception`` | ``violation`` for one component under the policy.

    ``internal-infra`` components may carry any license — the policy's
    ``internal_infra_exception`` covers operator-side tooling that is never shipped.
    An ``in-product`` component must carry a product-embeddable license, unless the
    catalog already recorded the deviation as ``verdict: "keep-exception"``: that
    value *is* the audit trail, and the component's ``why`` text carries the
    reasoning. Treating it as a violation would re-litigate a settled decision;
    treating it as ordinary would erase it, so it is reported as an exception.
    """
    if str((component or {}).get("role") or "") != "in-product":
        return "ok"
    if normalize_license((component or {}).get("license")) in set(policy.get("embeddable") or []):
        return "ok"
    if str((component or {}).get("verdict") or "") == "keep-exception":
        return "exception"
    return "violation"


def is_scoped(stack: dict) -> bool:
    """True when the product-scoping pass has run at least once.

    Every pass downstream of scoping needs this answer — ranking an unscoped stack
    would order every capability in the catalog, and offering an unscoped stack for
    selection would ask the human to choose components for capabilities scoping
    exists to rule out. One definition, shared, so the two cannot drift.
    """
    return any((c or {}).get("scoped_from")
               for c in (stack.get("choices") or {}).values())


def rankable_universe(stack: dict, capabilities: dict) -> list[dict]:
    """Every capability this product still has to rank, in ``stack.json`` key order.

    Only ``applicable`` entries — a capability the scoping pass ruled out is a
    recorded decision, not pending work. ``options`` is the closed pool and comes
    from ``stack.json``; each option is joined to its full catalog entry (license,
    role, verdict, why) by name, because ``stack.json`` stores names only. An
    option the catalog no longer describes still appears, with empty metadata, so
    it cannot vanish from the pool the gate checks against.
    """
    described: dict[tuple[str, str], dict] = {}
    for fw, f in capabilities.get("frameworks", {}).items():
        for cap in f.get("capabilities", []):
            described[(fw, cap.get("name", ""))] = cap

    out: list[dict] = []
    for key, entry in (stack.get("choices") or {}).items():
        if not (entry or {}).get("applicable", True):
            continue
        fw = entry.get("framework", "")
        name = entry.get("capability", "")
        cap = described.get((fw, name), {})
        by_name = {c.get("name", ""): c for c in cap.get("stack", []) if isinstance(c, dict)}
        options = list(entry.get("options") or [])
        out.append({
            "key": key,
            "framework": fw,
            "capability": name,
            "mandatory_linked": bool(entry.get("mandatory_linked")),
            "category": cap.get("category", ""),
            "description": cap.get("description", ""),
            "options": options,
            "components": [
                {
                    "name": opt,
                    "license": by_name.get(opt, {}).get("license", ""),
                    "role": by_name.get(opt, {}).get("role", ""),
                    "verdict": by_name.get(opt, {}).get("verdict", ""),
                    "why": by_name.get(opt, {}).get("why", ""),
                }
                for opt in options
            ],
        })
    return out


def ranking_gate(universe: list[dict], rankings: dict, policy: dict) -> dict:
    """The invariant, as set math: order the whole pool, justify every position.

    ``rankings`` maps a capability key to a list of ``{"component", "rationale"}``
    in best-fit-first order. A ranking passes when its component names are exactly
    that capability's ``options`` — same members, no duplicates — and every entry
    carries a rationale. ``violations`` fails the run; ``exceptions`` is the
    recorded, non-fatal list of ``keep-exception`` components the ranking touched.
    """
    by_key = {u["key"]: u for u in universe}
    keys, given = set(by_key), set(rankings)

    set_mismatches: list[dict] = []
    blank_rationales: list[dict] = []
    violations: list[dict] = []
    exceptions: list[dict] = []

    for key in sorted(keys & given):
        u = by_key[key]
        ranked = rankings[key]
        if not isinstance(ranked, list) or not ranked:
            set_mismatches.append({"key": key, "missing": list(u["options"]),
                                   "unexpected": [], "duplicated": []})
            continue
        names = [str((r or {}).get("component") or "").strip() for r in ranked]
        options = list(u["options"])
        duplicated = sorted({n for n in names if n and names.count(n) > 1})
        missing = sorted(set(options) - set(names))
        unexpected = sorted(n for n in set(names) if n not in set(options))
        if missing or unexpected or duplicated or not all(names):
            set_mismatches.append({"key": key, "missing": missing,
                                   "unexpected": unexpected, "duplicated": duplicated})
        blank = [n for n, r in zip(names, ranked)
                 if not str((r or {}).get("rationale") or "").strip()]
        if blank:
            blank_rationales.append({"key": key, "components": blank})

        by_component = {c["name"]: c for c in u["components"]}
        for name in names:
            verdict = license_check(by_component.get(name, {}), policy)
            if verdict == "violation":
                comp = by_component.get(name, {})
                violations.append({"key": key, "component": name,
                                   "license": comp.get("license", ""),
                                   "role": comp.get("role", "")})
            elif verdict == "exception":
                comp = by_component.get(name, {})
                exceptions.append({"key": key, "component": name,
                                   "license": comp.get("license", ""),
                                   "why": comp.get("why", "")})

    missing_rankings = sorted(keys - given)
    unknown_rankings = sorted(given - keys)
    return {
        "ok": not (missing_rankings or unknown_rankings
                   or set_mismatches or blank_rationales or violations),
        "missing_rankings": missing_rankings,
        "unknown_rankings": unknown_rankings,
        "set_mismatches": set_mismatches,
        "blank_rationales": blank_rationales,
        "violations": violations,
        "exceptions": exceptions,
    }


def rankings_payload(rankings: dict, ranked_from: str) -> dict:
    """The file ``stack.py --apply-ranking`` consumes.

    This engine's internal shape and the schema owner's field names meet here, in
    one place, exactly as ``scope_lib.decisions_payload`` does for scoping.
    """
    return {
        "ranked_from": ranked_from,
        "rankings": {
            key: [
                {
                    "component": str((r or {}).get("component") or "").strip(),
                    "rationale": str((r or {}).get("rationale") or "").strip(),
                }
                for r in (ranked or [])
            ]
            for key, ranked in sorted(rankings.items())
        },
    }


def render_rank_report(
    universe: list[dict],
    rankings: dict,
    gate: dict,
    ranked_from: str,
    generated: str,
    product_path: str = "",
) -> str:
    """Render reports/rank-<date>.md — the ordering, and what justified it."""
    by_key = {u["key"]: u for u in universe}
    ranked_count = sum(len(rankings.get(k) or []) for k in by_key)
    lines = [
        "# Component Ranking Report",
        "",
        (f"Generated {generated} by `scripts/rank.py` from `{product_path or 'product.md'}` "
         f"(product hash `{ranked_from}`)."),
        (f"{len(by_key)} applicable capability/-ies, {ranked_count} component(s) ordered "
         "from the catalog's closed pool."),
        "",
    ]
    if not gate["ok"]:
        lines += ["> **This run wrote nothing.** `stack.json` is unchanged.", ""]
        lines += ["## Gate failures", ""]
        if gate["missing_rankings"]:
            lines.append(f"**Applicable capabilities with no ranking "
                         f"({len(gate['missing_rankings'])})**")
            lines.append("")
            lines += [f"- `{k}`" for k in gate["missing_rankings"]]
            lines.append("")
        if gate["unknown_rankings"]:
            lines.append(f"**Rankings for unknown or non-applicable capabilities "
                         f"({len(gate['unknown_rankings'])})**")
            lines.append("")
            lines += [f"- `{k}`" for k in gate["unknown_rankings"]]
            lines.append("")
        if gate["set_mismatches"]:
            lines.append(f"**Rankings that do not match the pool "
                         f"({len(gate['set_mismatches'])})**")
            lines.append("")
            for m in gate["set_mismatches"]:
                parts = []
                if m["missing"]:
                    parts.append("left unranked: " + ", ".join(m["missing"]))
                if m["unexpected"]:
                    parts.append("not in options: " + ", ".join(m["unexpected"]))
                if m["duplicated"]:
                    parts.append("ranked twice: " + ", ".join(m["duplicated"]))
                lines.append(f"- `{m['key']}` — {'; '.join(parts) or 'malformed ranking'}")
            lines.append("")
        if gate["blank_rationales"]:
            lines.append(f"**Ranked with no rationale ({len(gate['blank_rationales'])})**")
            lines.append("")
            for b in gate["blank_rationales"]:
                lines.append(f"- `{b['key']}` — {', '.join(b['components'])}")
            lines.append("")
        if gate["violations"]:
            lines.append(f"**License policy violations ({len(gate['violations'])})**")
            lines.append("")
            for v in gate["violations"]:
                lines.append(f"- `{v['key']}` — **{v['component']}** carries `{v['license']}` "
                             f"in an `{v['role']}` role, which the policy does not permit. "
                             "Fix `capabilities.json`; the catalog is `compliance-compiler`'s.")
            lines.append("")

    for key in sorted(by_key):
        ranked = rankings.get(key) or []
        if not ranked:
            continue
        u = by_key[key]
        flag = " *(mandatory-linked)*" if u["mandatory_linked"] else ""
        lines += [f"## {u['capability']}{flag}", "", f"`{key}`", ""]
        for i, r in enumerate(ranked, start=1):
            name = str((r or {}).get("component") or "").strip() or "—"
            reason = str((r or {}).get("rationale") or "").strip() or "—"
            lines.append(f"{i}. **{name}** — {reason}")
        lines.append("")

    if gate["exceptions"]:
        lines += [
            f"## Recorded license exceptions ({len(gate['exceptions'])})",
            "",
            ("These `in-product` components carry a license outside the embeddable policy, and "
             "the catalog already records the deviation as `verdict: \"keep-exception\"`. They "
             "are ranked, not rejected — but the exception travels with the choice:"),
            "",
        ]
        for e in gate["exceptions"]:
            lines.append(f"- `{e['key']}` — **{e['component']}** (`{e['license']}`)")
            if e["why"]:
                lines.append(f"  - {e['why']}")
        lines.append("")

    return "\n".join(lines)
