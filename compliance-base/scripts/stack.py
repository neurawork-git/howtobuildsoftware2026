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
the human-owned ``chosen`` and ``rationale`` are carried over by key. New
capabilities appear with ``chosen: null``; keys the catalog no longer knows are
reported as orphaned before being dropped.

A plain run computes the gap — mandatory-linked capabilities with no chosen
component — writes ``reports/stack-gaps-<date>.md`` and prints a one-line summary.
It is deliberately REPORT-ONLY and always exits 0: an unfilled stack is the normal
starting state, not a regression. Enforcement belongs to the plan validator.

Usage:
    uv run python scripts/stack.py --scaffold   # create/refresh catalog/stack.json
    uv run python scripts/stack.py              # report gaps (report-only, exit 0)
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

    Machine-owned fields are recomputed from ``catalog``; the human-owned
    ``chosen``/``rationale`` are carried over from ``existing`` by key. Keys are
    emitted sorted so a re-scaffold produces a stable, reviewable diff.
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

    ``mandatory_unchosen`` is the headline gap. ``off_catalog`` is informational —
    a human may deliberately choose something the catalog did not list.
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
    for key in sorted(catalog_keys):
        entry = choices.get(key) or {}
        chosen = str(entry.get("chosen") or "").strip()
        if not chosen:
            (mandatory_unchosen if key in linked else optional_unchosen).append(key)
            continue
        options = entry.get("options") or []
        if chosen not in options:
            off_catalog.append({"key": key, "chosen": chosen, "options": list(options)})

    stack_hash = stack.get("capabilities_hash")
    return {
        "mandatory_total": len(linked),
        "mandatory_linked": sorted(linked),
        "mandatory_unchosen": mandatory_unchosen,
        "optional_unchosen": optional_unchosen,
        "off_catalog": off_catalog,
        "orphaned": sorted(set(choices) - catalog_keys),
        "stale": bool(capabilities_hash and stack_hash and stack_hash != capabilities_hash),
    }


def render_gap_report(catalog: dict, stack: dict, result: dict, generated: str) -> str:
    """Render reports/stack-gaps-<date>.md from a ``gaps()`` result."""
    choices = stack.get("choices") or {}
    unchosen = set(result["mandatory_unchosen"])
    linked = set(result["mandatory_linked"])
    unchosen_by_fw: dict[str, list[str]] = {}
    for key in unchosen:
        unchosen_by_fw.setdefault(key.split("/", 1)[0], []).append(key)

    lines = [
        "# Stack Gap Report",
        "",
        f"Generated {generated} by `scripts/stack.py` from `catalog/capabilities.json` "
        f"(derived {catalog.get('generated', '?')}) and `catalog/stack.json`.",
        "Report-only: an unchosen capability is a pending decision, not a failure.",
        "",
        "| Framework | Capabilities | Mandatory-linked | Chosen | Unchosen |",
        "|-----------|--------------|------------------|--------|----------|",
    ]
    for fw, f in catalog.get("frameworks", {}).items():
        caps = f.get("capabilities", [])
        keys = [capability_key(fw, c["name"]) for c in caps]
        fw_linked = [k for k in keys if k in linked]
        gap = [k for k in keys if k in unchosen]
        lines.append(
            f"| {FRAMEWORK_TITLES.get(fw, fw)} | {len(caps)} | {len(fw_linked)} | "
            f"{len(fw_linked) - len(gap)} | {len(gap)} |"
        )
    lines += [
        "",
        f"**{len(unchosen)} of {result['mandatory_total']} mandatory-linked capabilities "
        "have no chosen component.**",
        "",
    ]
    if result["stale"]:
        lines += [
            "> **Stale** — stack.json was scaffolded against an older capabilities.json. "
            "Re-run `scripts/stack.py --scaffold`.",
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
    if not (result["optional_unchosen"] or result["off_catalog"] or result["orphaned"]):
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

    result = gaps(catalog, stack, capabilities_hash=cap_hash)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"stack-gaps-{generated}.md"
    report_path.write_text(render_gap_report(catalog, stack, result, generated), encoding="utf-8")

    print(f"Stack gaps: {len(result['mandatory_unchosen'])} of {result['mandatory_total']} "
          "mandatory-linked capabilities have no chosen component")
    print(f"report: {report_path}")
    if result["stale"]:
        print("! stack.json was scaffolded against an older capabilities.json — "
              "re-run with --scaffold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
