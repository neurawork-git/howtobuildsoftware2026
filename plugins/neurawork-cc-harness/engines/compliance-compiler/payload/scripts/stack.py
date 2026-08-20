"""Record which component each compliance capability is actually built on, and
report the ones still undecided — pure stdlib, no LLM, no network.

Reads ``catalog/capabilities.json`` (the derived capability catalog, which lists
2-5 *recommended* components per capability) and maintains ``catalog/stack.json``,
the tracked record of the component that was actually *chosen*. Entries are keyed
``<framework>/<capability_slug>``: capabilities carry no id, and the framework
prefix is required because the catalog is deliberately per-framework with overlap
kept, so the same capability name may legitimately appear under two frameworks.

``--scaffold`` (re)generates ``stack.json``: machine-owned fields (``capability``,
``framework``, ``mandatory_linked``, ``options``) are recomputed every run, while
the decision-owned ``chosen``, ``rationale``, ``applicable``,
``applicability_reason``, ``scoped_from``, ``ranked`` and ``ranked_from`` are
carried over by key. New capabilities appear with ``chosen: null``; keys the
catalog no longer knows are reported as orphaned before being dropped.

The applicability and ranking fields are written by the ``stack-compiler`` skill,
which owns no data artifact of its own; both are carried over here so a
re-scaffold cannot erase that work, and each has one entry point:

``--apply-scope`` takes the product-scoping pass's decisions file
``{"scoped_from": <hash>, "decisions": {<key>: {"applicable", "applicability_reason"}}}``
and refuses the whole write unless the decision set is exactly the capability key
set and every non-applicable decision carries a reason. A capability that does not
apply to the product at hand is recorded as such, with a reason — never silently
omitted.

``--apply-ranking`` takes the component-ranking pass's file
``{"ranked_from": <hash>, "rankings": {<key>: [{"component", "rationale"}, ...]}}``
and refuses the whole write unless every **applicable** capability is ranked and
each ranking names exactly that entry's ``options``, once each, with a rationale.
The ranking is an ordering of the catalog's own recommendations, not a selection
from them, so ``options`` stays the closed pool and ``ranked`` its best-fit-first
order.

``chosen`` and ``rationale`` are never touched by either: the component decision
belongs to the human selection pass.

A plain run computes the gap — *applicable* mandatory-linked capabilities with no
chosen component — writes ``reports/stack-gaps-<date>.md`` and prints a one-line
summary. A capability scoped out of the product is not a gap; it is reported
separately together with its reason. The run is deliberately REPORT-ONLY and always
exits 0: an unfilled stack is the normal starting state, not a regression.
Enforcement belongs to the plan validator.

Usage:
    uv run python scripts/stack.py --scaffold          # create/refresh catalog/stack.json
    uv run python scripts/stack.py --apply-scope F.json  # write applicability decisions
    uv run python scripts/stack.py --apply-ranking F.json  # write component orderings
    uv run python scripts/stack.py                     # report gaps (report-only, exit 0)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

import cap_lib
from config import CATALOG_DIR, FRAMEWORK_TITLES, REPORTS_DIR, ROOT_DIR, today_iso
from utils import file_hash, load_constraints, mandatory_ids

# _shared/ is imported inside main(): it exists next to scripts/ only in an installed
# repo, not in the plugin's payload/ tree, so the pure logic below stays importable
# (and unit-testable) straight from payload/scripts.

CAPABILITIES_JSON = CATALOG_DIR / "capabilities.json"
STACK_JSON = CATALOG_DIR / "stack.json"


# ── Pure logic ────────────────────────────────────────────────────────

def capability_key(framework: str, name: str) -> str:
    """Stable identity for one capability: ``<framework>/<capability_slug>``.

    Capabilities in capabilities.json carry no ``id``; the slug (shared with the
    engine's stack↔capability join) plus the framework prefix is the identity.
    """
    return f"{framework}/{cap_lib.capability_slug(name)}"


def mandatory_linked_keys(catalog: dict, catalog_dir=None) -> set[str]:
    """Keys of capabilities that satisfy at least one MANDATORY constraint.

    These are the capabilities a gap actually matters for — a capability covering
    only optional constraints is reported separately, never as a gap.
    """
    keys: set[str] = set()
    for fw, f in catalog.get("frameworks", {}).items():
        mand = mandatory_ids(load_constraints([fw], catalog_dir))
        for cap in f.get("capabilities", []):
            if set(cap.get("satisfies", [])) & mand:
                keys.add(capability_key(fw, cap["name"]))
    return keys


def component_options(cap: dict) -> list[str]:
    """Component names recommended for a capability, order preserved, deduped.

    Every entry of ``cap["stack"]`` is a live recommendation regardless of its
    ``verdict``: ``replaced`` means this component SUPERSEDED the one named in
    ``replaced_from`` during the license audit — never that it was rejected.
    """
    seen: set[str] = set()
    out: list[str] = []
    for comp in cap.get("stack", []):
        name = (comp or {}).get("name")
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def scaffold(
    catalog: dict,
    existing: dict | None = None,
    catalog_dir=None,
    generated: str | None = None,
    capabilities_hash: str = "",
) -> dict:
    """Build catalog/stack.json from the capability catalog.

    Machine-owned fields are recomputed from ``catalog``; the decision-owned
    ``chosen``/``rationale`` and the ``stack-compiler``-owned applicability fields
    are carried over from ``existing`` by key. Keys are emitted sorted so a
    re-scaffold produces a stable, reviewable diff.
    """
    prev_choices = (existing or {}).get("choices") or {}
    linked = mandatory_linked_keys(catalog, catalog_dir)
    choices: dict[str, dict] = {}
    for fw, f in catalog.get("frameworks", {}).items():
        for cap in f.get("capabilities", []):
            key = capability_key(fw, cap["name"])
            if key in choices:
                raise ValueError(f"duplicate capability key: {key}")
            prev = prev_choices.get(key) or {}
            choices[key] = {
                "capability": cap["name"],
                "framework": fw,
                "mandatory_linked": key in linked,
                "options": component_options(cap),
                "chosen": prev.get("chosen"),
                "rationale": prev.get("rationale", ""),
                "applicable": prev.get("applicable", True),
                "applicability_reason": prev.get("applicability_reason", ""),
                "scoped_from": prev.get("scoped_from"),
                "ranked": prev.get("ranked"),
                "ranked_from": prev.get("ranked_from"),
            }
    return {
        "generated": generated or today_iso(),
        "source": "compliance-base/catalog/capabilities.json",
        "capabilities_generated": catalog.get("generated", ""),
        "capabilities_hash": capabilities_hash,
        "choices": {k: choices[k] for k in sorted(choices)},
    }


def gaps(
    catalog: dict,
    stack: dict,
    catalog_dir=None,
    capabilities_hash: str = "",
) -> dict:
    """Which capabilities still have no chosen component (and related findings).

    ``mandatory_unchosen`` is the headline gap, and ``mandatory_total`` counts only
    capabilities that are still **applicable** to the product — a capability the
    product-scoping pass ruled out is a recorded decision, not a pending one, so
    counting it as a gap would make a fully-decided stack unable to reach 0.
    ``non_applicable`` reports those separately; ``unexplained_non_applicable`` is
    the compliance hole — ruled out with no reason. ``off_catalog`` is
    informational: a human may deliberately choose something the catalog did not list.
    """
    linked = mandatory_linked_keys(catalog, catalog_dir)
    catalog_keys = {
        capability_key(fw, cap["name"])
        for fw, f in catalog.get("frameworks", {}).items()
        for cap in f.get("capabilities", [])
    }
    choices = stack.get("choices") or {}

    mandatory_unchosen: list[str] = []
    optional_unchosen: list[str] = []
    off_catalog: list[dict] = []
    non_applicable: list[str] = []
    unexplained_non_applicable: list[str] = []
    applicable_linked = 0
    for key in sorted(catalog_keys):
        entry = choices.get(key) or {}
        if not entry.get("applicable", True):
            non_applicable.append(key)
            if not str(entry.get("applicability_reason") or "").strip():
                unexplained_non_applicable.append(key)
            continue
        if key in linked:
            applicable_linked += 1
        chosen = str(entry.get("chosen") or "").strip()
        if not chosen:
            (mandatory_unchosen if key in linked else optional_unchosen).append(key)
            continue
        options = entry.get("options") or []
        if chosen not in options:
            off_catalog.append({"key": key, "chosen": chosen, "options": list(options)})

    stack_hash = stack.get("capabilities_hash")
    return {
        "mandatory_total": applicable_linked,
        "mandatory_linked": sorted(linked),
        "mandatory_unchosen": mandatory_unchosen,
        "optional_unchosen": optional_unchosen,
        "off_catalog": off_catalog,
        "non_applicable": non_applicable,
        "unexplained_non_applicable": unexplained_non_applicable,
        "orphaned": sorted(set(choices) - catalog_keys),
        "stale": bool(capabilities_hash and stack_hash and stack_hash != capabilities_hash),
    }


def apply_scope(stack: dict, decisions: dict, scoped_from: str) -> dict:
    """Write one product-scoping pass into stack.json's applicability fields.

    ``decisions`` maps every capability key to ``{"applicable": bool,
    "applicability_reason": str}``. The whole write is refused — nothing partial —
    when the decision set is not exactly the capability key set (a missing key is
    the silent omission this schema exists to prevent; an unknown key is a decision
    about a capability the catalog does not contain) or when a non-applicable
    decision carries no reason. ``chosen`` and ``rationale`` are never read or written:
    the component decision belongs to the human selection pass.
    """
    choices = stack.get("choices") or {}
    keys, given = set(choices), set(decisions)
    problems: list[str] = []
    if missing := sorted(keys - given):
        problems.append(f"no decision for {len(missing)} capability key(s): {', '.join(missing)}")
    if unknown := sorted(given - keys):
        problems.append(f"decision for {len(unknown)} unknown key(s): {', '.join(unknown)}")
    blank = sorted(
        k for k in keys & given
        if not (decisions[k] or {}).get("applicable", True)
        and not str((decisions[k] or {}).get("applicability_reason") or "").strip()
    )
    if blank:
        problems.append(f"not applicable without a reason: {', '.join(blank)}")
    if problems:
        raise ValueError("; ".join(problems))

    out: dict[str, dict] = {}
    for key in sorted(choices):
        d = decisions[key] or {}
        entry = dict(choices[key])
        entry["applicable"] = bool(d.get("applicable", True))
        entry["applicability_reason"] = str(d.get("applicability_reason") or "").strip()
        entry["scoped_from"] = scoped_from
        out[key] = entry
    return {**stack, "choices": out}


def apply_ranking(stack: dict, rankings: dict, ranked_from: str) -> dict:
    """Write one component-ranking pass into stack.json's ``ranked`` fields.

    ``rankings`` maps every **applicable** capability key to a list of
    ``{"component": str, "rationale": str}`` in best-fit-first order. The whole
    write is refused — nothing partial — when a ranking is missing for an
    applicable capability (the silent omission this schema exists to prevent),
    when one is given for an unknown or non-applicable key, when the ranked
    component names are not exactly the entry's ``options`` as a set (which
    catches dropped, invented and duplicated components in one check), or when a
    rationale is blank. ``chosen``, ``rationale``, ``options`` and the three
    applicability fields are never read or written: the component decision belongs
    to the human selection pass, and ``options`` is recomputed from the catalog.
    """
    choices = stack.get("choices") or {}
    applicable = {k for k, e in choices.items() if (e or {}).get("applicable", True)}
    given = set(rankings)
    problems: list[str] = []

    if unknown := sorted(given - set(choices)):
        problems.append(f"ranking for {len(unknown)} unknown key(s): {', '.join(unknown)}")
    if scoped_out := sorted((given & set(choices)) - applicable):
        problems.append(f"ranking for {len(scoped_out)} non-applicable key(s): "
                        f"{', '.join(scoped_out)}")
    if missing := sorted(applicable - given):
        problems.append(f"no ranking for {len(missing)} applicable key(s): {', '.join(missing)}")

    for key in sorted(applicable & given):
        ranked = rankings[key]
        if not isinstance(ranked, list) or not ranked:
            problems.append(f"{key}: ranking is not a non-empty list")
            continue
        names = [str((r or {}).get("component") or "").strip() for r in ranked]
        if blank := [i for i, n in enumerate(names) if not n]:
            problems.append(f"{key}: {len(blank)} entry/-ies name no component")
            continue
        if len(set(names)) != len(names):
            dupes = sorted({n for n in names if names.count(n) > 1})
            problems.append(f"{key}: component(s) ranked twice: {', '.join(dupes)}")
        options = list(choices[key].get("options") or [])
        if extra := sorted(set(names) - set(options)):
            problems.append(f"{key}: not in options: {', '.join(extra)}")
        if dropped := sorted(set(options) - set(names)):
            problems.append(f"{key}: options left unranked: {', '.join(dropped)}")
        if no_reason := [n for n, r in zip(names, ranked)
                         if not str((r or {}).get("rationale") or "").strip()]:
            problems.append(f"{key}: ranked with no rationale: {', '.join(no_reason)}")

    if problems:
        raise ValueError("; ".join(problems))

    out: dict[str, dict] = {}
    for key in sorted(choices):
        entry = dict(choices[key])
        if key in rankings:
            entry["ranked"] = [
                {"component": str(r["component"]).strip(),
                 "rationale": str(r["rationale"]).strip()}
                for r in rankings[key]
            ]
            entry["ranked_from"] = ranked_from
        else:
            # Every entry carries every field, as it does for the applicability fields:
            # a scoped-out capability reads `ranked: null`, never a missing key that a
            # consumer would have to guard. setdefault, so a ranking recorded before the
            # capability was scoped out survives rather than being silently discarded.
            entry.setdefault("ranked", None)
            entry.setdefault("ranked_from", None)
        out[key] = entry
    return {**stack, "choices": out}


def render_gap_report(catalog: dict, stack: dict, result: dict, generated: str) -> str:
    """Render reports/stack-gaps-<date>.md from a ``gaps()`` result."""
    choices = stack.get("choices") or {}
    unchosen = set(result["mandatory_unchosen"])
    linked = set(result["mandatory_linked"])
    non_applicable = set(result.get("non_applicable", []))
    unchosen_by_fw: dict[str, list[str]] = {}
    for key in unchosen:
        unchosen_by_fw.setdefault(key.split("/", 1)[0], []).append(key)

    lines = [
        "# Stack Gap Report",
        "",
        (f"Generated {generated} by `scripts/stack.py` from `catalog/capabilities.json` "
         f"(derived {catalog.get('generated', '?')}) and `catalog/stack.json`."),
        "Report-only: an unchosen capability is a pending decision, not a failure.",
        "",
        "| Framework | Capabilities | Mandatory-linked | Not applicable | Chosen | Unchosen |",
        "|-----------|--------------|------------------|----------------|--------|----------|",
    ]
    for fw, f in catalog.get("frameworks", {}).items():
        caps = f.get("capabilities", [])
        keys = [capability_key(fw, c["name"]) for c in caps]
        fw_linked = [k for k in keys if k in linked]
        scoped_out = [k for k in fw_linked if k in non_applicable]
        gap = [k for k in keys if k in unchosen]
        lines.append(
            f"| {FRAMEWORK_TITLES.get(fw, fw)} | {len(caps)} | {len(fw_linked)} | "
            f"{len(scoped_out)} | {len(fw_linked) - len(scoped_out) - len(gap)} | {len(gap)} |"
        )
    lines += [
        "",
        (f"**{len(unchosen)} of {result['mandatory_total']} applicable mandatory-linked "
         "capabilities have no chosen component.**"),
        "",
    ]
    if non_applicable:
        lines += [
            (f"{len(non_applicable)} capability/-ies were scoped out of this product and are "
             "not counted above — see *Not applicable* below."),
            "",
        ]
    if result.get("unexplained_non_applicable"):
        lines += [
            ("> **Unexplained omission** — "
             f"{len(result['unexplained_non_applicable'])} capability/-ies are marked not "
             "applicable with no recorded reason. An untracked narrowing is indistinguishable "
             "from an oversight; re-run the product-scoping pass."),
            "",
        ]
    if result["stale"]:
        lines += [
            ("> **Stale** — stack.json was scaffolded against an older capabilities.json. "
             "Re-run `scripts/stack.py --scaffold`."),
            "",
        ]
    lines.append("---")
    lines.append("")

    for fw in catalog.get("frameworks", {}):
        keys = sorted(unchosen_by_fw.get(fw, []))
        if not keys:
            continue
        lines.append(f"### {FRAMEWORK_TITLES.get(fw, fw)} — {len(keys)} undecided")
        lines.append("")
        for key in keys:
            entry = choices.get(key) or {}
            name = entry.get("capability", key.split("/", 1)[1])
            opts = "; ".join(entry.get("options") or []) or "—"
            lines.append(f"- **{name}** (`{key}`) — options: {opts}")
        lines.append("")

    lines += ["## Informational", ""]
    if non_applicable:
        lines.append(
            f"**Not applicable ({len(non_applicable)})** — scoped out of this product by the "
            "`stack-compiler` product-scoping pass. Each is a recorded decision, not a gap:"
        )
        lines.append("")
        for key in sorted(non_applicable):
            entry = choices.get(key) or {}
            reason = (str(entry.get("applicability_reason") or "").strip()
                      or "**no reason recorded**")
            lines.append(f"- `{key}` — {reason}")
        lines.append("")
    if result["optional_unchosen"]:
        lines.append(
            f"**Unchosen, optional-only ({len(result['optional_unchosen'])})** — these "
            "capabilities satisfy no mandatory constraint, so they are not counted as gaps:"
        )
        lines.append("")
        for key in result["optional_unchosen"]:
            lines.append(f"- `{key}`")
        lines.append("")
    if result["off_catalog"]:
        lines.append(
            f"**Off-catalog choices ({len(result['off_catalog'])})** — chosen component is "
            "not among the catalog's recommendations. Deliberate choices are fine; listed "
            "so they stay visible:"
        )
        lines.append("")
        for item in result["off_catalog"]:
            opts = "; ".join(item["options"]) or "—"
            lines.append(f"- `{item['key']}` → **{item['chosen']}** (recommended: {opts})")
        lines.append("")
    if result["orphaned"]:
        lines.append(
            f"**Orphaned keys ({len(result['orphaned'])})** — recorded in stack.json but no "
            "longer in the capability catalog (renamed or removed upstream):"
        )
        lines.append("")
        for key in result["orphaned"]:
            lines.append(f"- `{key}`")
        lines.append("")
    if not (non_applicable or result["optional_unchosen"] or result["off_catalog"]
            or result["orphaned"]):
        lines += ["Nothing to report.", ""]
    return "\n".join(lines)


# ── I/O + CLI ─────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    """Read a JSON object, or ``{}`` if absent/corrupt. Never raises."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_json_atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record the chosen stack component per capability and report the gaps"
    )
    parser.add_argument("--scaffold", action="store_true",
                        help="Create/refresh catalog/stack.json (keeps existing choices)")
    parser.add_argument("--apply-scope", type=str, metavar="PATH",
                        help="Apply a product-scoping decisions file to the applicability fields")
    parser.add_argument("--apply-ranking", type=str, metavar="PATH",
                        help="Apply a component-ranking file to the applicable capabilities")
    args = parser.parse_args()

    from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude

    try:
        assert_in_repo_not_dotclaude(CATALOG_DIR, ROOT_DIR.parent)
    except WriteGuardError as e:
        print(f"Refusing to write catalog: {e}")
        return 1

    catalog = _load_json(CAPABILITIES_JSON)
    if not catalog.get("frameworks"):
        print("No capabilities.json — run scripts/capabilities.py first")
        return 1
    cap_hash = file_hash(CAPABILITIES_JSON)

    stack = _load_json(STACK_JSON)
    generated = today_iso()

    if args.scaffold:
        before = gaps(catalog, stack, capabilities_hash=cap_hash)
        prev_choices = stack.get("choices") or {}
        stack = scaffold(catalog, stack, generated=generated, capabilities_hash=cap_hash)
        _write_json_atomic(STACK_JSON, stack)
        carried = sum(1 for k in stack["choices"]
                      if (prev_choices.get(k) or {}).get("chosen"))
        added = sum(1 for k in stack["choices"] if k not in prev_choices)
        print(f"stack.json: {len(stack['choices'])} capabilities "
              f"({carried} choice(s) carried, {added} new)")
        if before["orphaned"]:
            print(f"  dropped {len(before['orphaned'])} orphaned key(s): "
                  f"{', '.join(before['orphaned'])}")

    if args.apply_scope:
        scope_path = Path(args.apply_scope)
        if not scope_path.exists():
            print(f"No such scope file: {scope_path}")
            return 1
        payload = _load_json(scope_path)
        decisions = payload.get("decisions")
        scoped_from = str(payload.get("scoped_from") or "").strip()
        if not isinstance(decisions, dict) or not decisions:
            print(f"{scope_path}: no 'decisions' object to apply")
            return 1
        if not scoped_from:
            print(f"{scope_path}: refusing to apply a scope with no 'scoped_from' hash")
            return 1
        try:
            stack = apply_scope(stack, decisions, scoped_from)
        except ValueError as e:
            print(f"Refusing to apply scope: {e}")
            return 1
        _write_json_atomic(STACK_JSON, stack)
        applicable = sum(1 for e in stack["choices"].values() if e.get("applicable", True))
        print(f"stack.json scoped from {scoped_from}: {applicable} applicable, "
              f"{len(stack['choices']) - applicable} not applicable")
        for key, entry in stack["choices"].items():
            if not entry.get("applicable", True) and str(entry.get("chosen") or "").strip():
                print(f"  ! {key}: scoped out but still carries chosen={entry['chosen']}")

    if args.apply_ranking:
        rank_path = Path(args.apply_ranking)
        if not rank_path.exists():
            print(f"No such ranking file: {rank_path}")
            return 1
        payload = _load_json(rank_path)
        rankings = payload.get("rankings")
        ranked_from = str(payload.get("ranked_from") or "").strip()
        if not isinstance(rankings, dict) or not rankings:
            print(f"{rank_path}: no 'rankings' object to apply")
            return 1
        if not ranked_from:
            print(f"{rank_path}: refusing to apply a ranking with no 'ranked_from' hash")
            return 1
        try:
            stack = apply_ranking(stack, rankings, ranked_from)
        except ValueError as e:
            print(f"Refusing to apply ranking: {e}")
            return 1
        _write_json_atomic(STACK_JSON, stack)
        components = sum(len(e.get("ranked") or []) for e in stack["choices"].values())
        print(f"stack.json ranked from {ranked_from}: {len(rankings)} applicable "
              f"capability/-ies, {components} component(s) ordered")

    result = gaps(catalog, stack, capabilities_hash=cap_hash)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"stack-gaps-{generated}.md"
    report_path.write_text(render_gap_report(catalog, stack, result, generated), encoding="utf-8")

    print(f"Stack gaps: {len(result['mandatory_unchosen'])} of {result['mandatory_total']} "
          "applicable mandatory-linked capabilities have no chosen component")
    if result["non_applicable"]:
        print(f"  ({len(result['non_applicable'])} capability/-ies scoped out of this product)")
    if result["unexplained_non_applicable"]:
        print(f"! {len(result['unexplained_non_applicable'])} capability/-ies are not applicable "
              "with no recorded reason: "
              f"{', '.join(result['unexplained_non_applicable'])}")
    print(f"report: {report_path}")
    if result["stale"]:
        print("! stack.json was scaffolded against an older capabilities.json — "
              "re-run with --scaffold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
