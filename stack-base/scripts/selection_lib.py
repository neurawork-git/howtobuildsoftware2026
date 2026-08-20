"""Pure (no-SDK) logic for selection.py: the selectable universe, the sheet a human
fills in, its parser, the selection gate, and the select-report renderer.

Stdlib only — no ``claude_agent_sdk`` import and no import of any ``compliance-base``
module — for the reasons ``scope_lib`` and ``rank_lib`` state. Selection needs no
agent at all: the ranking pass already ordered the closed pool and justified every
position, so this pass renders that proposal, reads back what the human decided, and
checks it. Render, parse, set math, subprocess — no LLM, no network, no API key.

The sheet is the interaction surface, and it is deliberately a file rather than a
prompt loop: every entry point in this harness is run non-interactively (often by an
agent, where stdin is not a terminal), and a file is resumable across sittings,
diffable, and parseable in a test.

Every ``choice:`` line arrives blank — **including the ones already decided**, whose
recorded state is shown as prose instead. Nothing is chosen without an explicit human
keystroke, and the blank line is what makes that true twice over:

- a pre-filled top-ranked default would make an inattentive apply indistinguishable
  from auto-picking, which is what the ranking/selection split exists to prevent;
- pre-filling an *existing* choice would re-submit it on every later sheet, and since
  a selection replaces both ``rationale`` and ``chosen_from``, an untouched block
  would silently drop its recorded reason and re-stamp a stale choice as current.

So a blank line means "leave this capability exactly as it is", and only what the
human writes reaches ``stack.json``. Re-confirming a choice the catalog has since made
stale is possible — by writing it again, which is the deliberate act it should be. A
bare rank number is accepted so confirming a shortlist stays cheap.
"""

from __future__ import annotations

import rank_lib

CHOICE_PREFIX = "choice:"
REASON_PREFIX = "reason:"


def selectable_universe(stack: dict, capabilities: dict) -> list[dict]:
    """Every capability this product still has to choose a component for.

    Built on ``rank_lib.rankable_universe`` so the join from ``options`` to the
    catalog's component metadata lives in one place. Adds what selection needs on
    top: ``order`` (the recorded best-fit-first ordering — what a numeric ``choice:``
    resolves against), ``rationales`` (component → the ranking's reason for that
    position), ``chosen`` (what is already recorded), and ``ranked``.

    ``order`` is always exactly ``options`` as a set: ranked components first in
    their recorded order, then anything the ranking did not cover. An applicable
    capability the ranking pass never saw therefore still appears, with its catalog
    order and ``ranked: False``, instead of silently dropping off the sheet.
    """
    entries = stack.get("choices") or {}
    out: list[dict] = []
    for u in rank_lib.rankable_universe(stack, capabilities):
        entry = entries.get(u["key"]) or {}
        ranked = entry.get("ranked") or []
        options = list(u["options"])
        order = [
            name for name in
            (str((r or {}).get("component") or "").strip() for r in ranked)
            if name in options
        ]
        order += [name for name in options if name not in order]
        out.append({
            **u,
            "order": order,
            "rationales": {
                str((r or {}).get("component") or "").strip():
                    str((r or {}).get("rationale") or "").strip()
                for r in ranked
            },
            "chosen": str(entry.get("chosen") or "").strip(),
            "rationale": str(entry.get("rationale") or "").strip(),
            "ranked": bool(ranked),
        })
    return out


# ── Sheet ─────────────────────────────────────────────────────────────

def render_sheet(
    universe: list[dict],
    generated: str,
    stack_path: str = "",
    apply_command: str = "scripts/selection.py --apply <this file>",
) -> str:
    """Render the sheet the human fills in — one block per applicable capability."""
    chosen = sum(1 for u in universe if u["chosen"])
    lines = [
        "# Stack Selection Sheet",
        "",
        (f"Generated {generated} by `scripts/selection.py` from "
         f"`{stack_path or 'catalog/stack.json'}`."),
        (f"{len(universe)} applicable capability/-ies: {chosen} chosen, "
         f"{len(universe) - chosen} undecided."),
        "",
        "Write the rank number (`1`) or the exact component name after `choice:`.",
        "Every `choice:` line starts blank, including the ones already decided: a blank",
        "line means *leave this capability exactly as it is*. Only what you write here is",
        "applied, so an untouched block can neither lose its reason nor be re-confirmed by",
        "accident. Writing into a decided block replaces its choice and its reason — that",
        "is also how you re-confirm a choice the catalog has since made stale.",
        "`reason:` is optional and lands in `stack.json`'s `rationale`.",
        "",
        "Apply with:",
        "",
        f"    {apply_command}",
        "",
        "---",
        "",
    ]
    for u in universe:
        flag = " — *mandatory-linked*" if u["mandatory_linked"] else ""
        lines += [f"## {u['key']}", "", f"**{u['capability']}**{flag}", ""]
        if not u["ranked"]:
            lines += [
                ("> Not ranked — `scripts/rank.py` has not seen this capability. The "
                 "components below are in catalog order, not fit order."),
                "",
            ]
        if u["chosen"]:
            recorded = f"> Recorded: **{u['chosen']}**"
            lines += [recorded + (f" — {u['rationale']}" if u["rationale"] else ""), ""]
        if u["description"]:
            lines += [u["description"], ""]
        for i, name in enumerate(u["order"], start=1):
            reason = u["rationales"].get(name, "")
            lines.append(f"{i}. **{name}**" + (f" — {reason}" if reason else ""))
        lines += ["", CHOICE_PREFIX, REASON_PREFIX, ""]
    return "\n".join(lines)


def parse_sheet(text: str, universe: list[dict]) -> dict:
    """Read a filled sheet back into ``{key: {chosen, rationale}}``.

    Only three line shapes are read: a ``## <key>`` heading opens a block, ``choice:``
    and ``reason:`` fill it. The numbered list is human-facing prose and is never
    parsed — a numeric choice resolves against the universe's recorded ``order``, so
    the sheet's rendering and its meaning cannot drift apart.

    A blank ``choice:`` means "leave this capability as it is" — undecided or decided,
    it is simply absent from the result and therefore never written. Every problem is
    collected and raised once, so one edit pass fixes them all.
    """
    by_key = {u["key"]: u for u in universe}
    selections: dict[str, dict] = {}
    problems: list[str] = []
    seen: list[str] = []
    key: str | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("## "):
            key = line[3:].strip().strip("`")
            if key in seen:
                problems.append(f"line {lineno}: {key} appears twice in the sheet")
            seen.append(key)
            if key not in by_key:
                problems.append(f"line {lineno}: {key} is not an applicable capability "
                                "of this product")
                key = None
            continue
        if not line.startswith((CHOICE_PREFIX, REASON_PREFIX)):
            continue
        is_choice = line.startswith(CHOICE_PREFIX)
        value = line[len(CHOICE_PREFIX if is_choice else REASON_PREFIX):].strip()
        if key is None:
            if value:
                problems.append(f"line {lineno}: '{line}' does not belong to a capability block")
            continue
        if is_choice:
            if key in selections:
                problems.append(f"line {lineno}: {key} carries a second '{CHOICE_PREFIX}' line")
                continue
            if not value:
                continue  # still deciding
            order = by_key[key]["order"]
            if value.isdigit():
                idx = int(value)
                if not 1 <= idx <= len(order):
                    problems.append(f"line {lineno}: {key} has no rank {idx} "
                                    f"(1-{len(order)})")
                    continue
                value = order[idx - 1]
            elif value not in order:
                problems.append(f"line {lineno}: {key} has no component '{value}' "
                                f"({', '.join(order)})")
                continue
            selections[key] = {"chosen": value, "rationale": ""}
        elif value:
            if key in selections:
                selections[key]["rationale"] = value
            # A reason without a choice describes nothing yet; it is dropped with the
            # blank choice rather than reported, so a half-filled block is not an error.

    if problems:
        raise ValueError("; ".join(problems))
    return selections


# ── Gate ──────────────────────────────────────────────────────────────

def selection_gate(universe: list[dict], selections: dict, policy: dict) -> dict:
    """The invariant, as set math: an applicable capability, a component from its pool.

    ``unknown`` covers both a capability the catalog does not have and one this product
    scoped out — neither is in the universe, and the distinction only matters on the
    write side, where ``stack.py`` reports it precisely.

    ``violations`` fails the run; ``exceptions`` records the ``keep-exception``
    components a choice landed on, without failing — the exception travels with the
    choice. ``pending`` is informational: a partial pass is the normal way to work
    through 40-odd capabilities, so it never fails the gate.
    """
    by_key = {u["key"]: u for u in universe}
    unknown = sorted(set(selections) - set(by_key))
    blank: list[str] = []
    off_pool: list[dict] = []
    violations: list[dict] = []
    exceptions: list[dict] = []

    for key in sorted(set(selections) & set(by_key)):
        u = by_key[key]
        chosen = str((selections[key] or {}).get("chosen") or "").strip()
        if not chosen:
            blank.append(key)
            continue
        if chosen not in u["options"]:
            off_pool.append({"key": key, "chosen": chosen, "options": list(u["options"])})
            continue
        component = next((c for c in u["components"] if c["name"] == chosen), {})
        verdict = rank_lib.license_check(component, policy)
        if verdict == "violation":
            violations.append({"key": key, "component": chosen,
                               "license": component.get("license", ""),
                               "role": component.get("role", "")})
        elif verdict == "exception":
            exceptions.append({"key": key, "component": chosen,
                               "license": component.get("license", ""),
                               "why": component.get("why", "")})

    pending = sorted(u["key"] for u in universe
                     if not str((selections.get(u["key"]) or {}).get("chosen") or "").strip()
                     and not u["chosen"])
    return {
        "ok": not (unknown or blank or off_pool or violations),
        "unknown": unknown,
        "blank": blank,
        "off_pool": off_pool,
        "violations": violations,
        "exceptions": exceptions,
        "pending": pending,
    }


def selections_payload(selections: dict) -> dict:
    """The file ``stack.py --apply-selection`` consumes.

    This engine's internal shape and the schema owner's field names meet here, in one
    place, exactly as ``rank_lib.rankings_payload`` does for ranking. No hash travels
    with it: ``chosen_from`` is the hash of the *catalog capability*, and ``stack.py``
    computes it from the catalog it already holds.
    """
    return {
        "selections": {
            key: {
                "chosen": str((sel or {}).get("chosen") or "").strip(),
                "rationale": str((sel or {}).get("rationale") or "").strip(),
            }
            for key, sel in sorted(selections.items())
        },
    }


# ── Report ────────────────────────────────────────────────────────────

def render_select_report(
    universe: list[dict],
    selections: dict,
    gate: dict,
    generated: str,
    sheet_path: str = "",
) -> str:
    """Render reports/select-<date>.md — what was chosen, and what justified it."""
    by_key = {u["key"]: u for u in universe}
    lines = [
        "# Component Selection Report",
        "",
        (f"Generated {generated} by `scripts/selection.py` from "
         f"`{sheet_path or 'the selection sheet'}`."),
        (f"{len(selections)} choice(s) read, {len(universe)} applicable capability/-ies "
         "in this product."),
        "",
    ]
    if not gate["ok"]:
        lines += ["> **This run wrote nothing.** `stack.json` is unchanged.", ""]
        lines += ["## Gate failures", ""]
        if gate["unknown"]:
            lines.append(f"**Choices for capabilities this product does not have "
                         f"({len(gate['unknown'])})**")
            lines.append("")
            lines += [f"- `{k}` — unknown to the catalog, or scoped out of this product"
                      for k in gate["unknown"]]
            lines.append("")
        if gate["blank"]:
            lines.append(f"**Choices naming no component ({len(gate['blank'])})**")
            lines.append("")
            lines += [f"- `{k}`" for k in gate["blank"]]
            lines.append("")
        if gate["off_pool"]:
            lines.append(f"**Choices outside the capability's pool ({len(gate['off_pool'])})**")
            lines.append("")
            for item in gate["off_pool"]:
                lines.append(f"- `{item['key']}` — **{item['chosen']}** is not one of "
                             f"{', '.join(item['options']) or '—'}. The pool is closed; "
                             "widening it is `compliance-compiler`'s decision.")
            lines.append("")
        if gate["violations"]:
            lines.append(f"**License policy violations ({len(gate['violations'])})**")
            lines.append("")
            for v in gate["violations"]:
                lines.append(f"- `{v['key']}` — **{v['component']}** carries `{v['license']}` "
                             f"in an `{v['role']}` role, which the policy does not permit.")
            lines.append("")

    recorded = sorted(selections)
    if recorded:
        lines += ["## Chosen", ""]
        for key in recorded:
            u = by_key.get(key, {})
            chosen = str((selections[key] or {}).get("chosen") or "").strip() or "—"
            order = u.get("order") or []
            position = f"rank {order.index(chosen) + 1} of {len(order)}" \
                if chosen in order else "off the recorded ranking"
            reason = str((selections[key] or {}).get("rationale") or "").strip()
            lines.append(f"- **{u.get('capability', key)}** (`{key}`) → **{chosen}** "
                         f"({position})")
            lines.append(f"  - {reason or u.get('rationales', {}).get(chosen, '—')}")
        lines.append("")

    if gate["exceptions"]:
        lines += [
            f"## Recorded license exceptions ({len(gate['exceptions'])})",
            "",
            ("These chosen `in-product` components carry a license outside the embeddable "
             "policy, and the catalog already records the deviation as "
             "`verdict: \"keep-exception\"`. The exception travels with the choice:"),
            "",
        ]
        for e in gate["exceptions"]:
            lines.append(f"- `{e['key']}` — **{e['component']}** (`{e['license']}`)")
            if e["why"]:
                lines.append(f"  - {e['why']}")
        lines.append("")

    if gate["pending"]:
        lines += [
            f"## Still undecided ({len(gate['pending'])})",
            "",
            "Re-render the sheet to continue; these stay gaps until they carry a component:",
            "",
        ]
        lines += [f"- `{k}`" for k in gate["pending"]]
        lines.append("")

    return "\n".join(lines)
