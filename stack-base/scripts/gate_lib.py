"""Pure (no-SDK) logic for the component gate: which documents it reads, which
catalog components they name, and what the recorded stack says about each one.

Stdlib only — no ``claude_agent_sdk`` import and no import of any
``compliance-base`` module — for the reasons ``scope_lib`` and ``rank_lib`` state.
Unlike its siblings this module serves **two** entry points, which is why it is
named after neither: ``hooks/st-post-tooluse.py`` runs it inline on every PRD/plan
write (it must stay well inside the hook's timeout and needs no API key), and
``scripts/validate.py`` runs it again to hand the agent a precheck it did not
produce itself.

The gate never decides *which* component is right — Phases 1–3 recorded that in
``stack.json``. It reads that decision back and reports contradictions. Nothing
here writes ``stack.json`` or ``capabilities.json``.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import rank_lib
from config import DEFAULT_CFG  # type: ignore[reportMissingImports]

# Where a catalog name stops being the component and starts being a description:
# ``"PostgreSQL (append-only disclosure ledger via …)"`` is the component
# PostgreSQL, and a document that says "PostgreSQL" means it. The head before the
# first of these markers is indexed alongside the exact catalog spelling.
_SPLIT_MARKERS = (" — ", " (", " with ", " / ")

# Spellings prose uses for a component the catalog spells differently. Deliberately
# tiny and explicit, in the shape and spirit of ``rank_lib._LICENSE_ALIASES``: it
# maps spellings, it does not interpret. A missing alias costs a missed mention,
# never a false accusation — which is the trade this gate wants.
_COMPONENT_ALIASES = {
    "Postgres": "PostgreSQL",
    "ArgoCD": "Argo CD",
}

# Below this, a "component name" is an ordinary word or an abbreviation that would
# match everywhere. Both index variants and aliases are held to it.
MIN_VARIANT_LEN = 3

_STATUS_ORDER = ("on_stack", "off_stack", "undecided", "scoped_out", "orphaned")


# ── Which documents this gate reads ───────────────────────────────────

_MISSING = object()


def _cfg_strings(cfg: dict, key: str) -> tuple[str, ...]:
    """A document-matching config value as a tuple of strings (accepts one or many).

    Falls back to the default when the key is absent or not a string/list, so an
    ADOPT install whose ``config.json`` predates these keys keeps the documented
    behaviour instead of silently matching nothing. An explicitly empty list is
    honoured — that is how you switch one document kind off without uninstalling.
    """
    value = cfg.get(key, _MISSING)
    if not isinstance(value, (str, list, tuple)):
        value = DEFAULT_CFG[key]
    if isinstance(value, str):
        value = [value]
    return tuple(v.strip() for v in value if isinstance(v, str) and v.strip())


def _segments(subpath: str) -> tuple[str, ...]:
    """Split a configured subpath into path segments, tolerating either slash style
    and stray separators (``./.planning/phases/`` → ``.planning``, ``phases``)."""
    return tuple(s for s in subpath.replace("\\", "/").split("/") if s and s != ".")


def _matches(parts: tuple[str, ...], head: tuple[str, ...]) -> bool:
    """True iff ``parts`` starts with ``head``, where a ``*`` segment in ``head``
    matches exactly one segment of ``parts`` (``.claude/PRPs/*/plans``)."""
    return len(parts) >= len(head) and all(
        want == "*" or want == have for want, have in zip(head, parts)
    )


def document_kind(path_str: str, repo_root: Path | str, cfg: dict) -> str:
    """``"prd"`` | ``"plan"`` | ``""`` for a written path.

    Same shape and the same ``(ValueError, OSError)`` tolerance as
    ``compliance-base``'s ``precheck.is_plan_path``, widened to the two document
    kinds this gate covers and reading its keys from ``cfg`` rather than importing
    the sibling engine's constants. Which files qualify is configurable via
    ``prds_subpath`` / ``plans_subpath``, ``prd_suffix`` / ``plan_suffix`` and
    ``doc_archive_segments`` (see ``config.DEFAULT_CFG``); an archived document — one
    carrying an archive segment below the subpath — is a record, not pending work,
    and never matches.
    """
    if not path_str:
        return ""
    p = Path(path_str)
    for kind, suffix_key, subpath_key in (
        ("prd", "prd_suffix", "prds_subpath"),
        ("plan", "plan_suffix", "plans_subpath"),
    ):
        if not any(p.name.endswith(s) for s in _cfg_strings(cfg, suffix_key)):
            continue
        try:
            rel = p.resolve().relative_to(Path(repo_root).resolve())
        except (ValueError, OSError):
            return ""
        parts = rel.parts
        archived = _cfg_strings(cfg, "doc_archive_segments")
        for subpath in _cfg_strings(cfg, subpath_key):
            head = _segments(subpath)
            if head and _matches(parts, head):
                if any(seg in archived for seg in parts[len(head):]):
                    return ""
                return kind
    return ""


# ── The closed pool, and finding it in prose ──────────────────────────

def _variants(name: str) -> set[str]:
    """The exact catalog spelling plus its component head, both length-filtered."""
    out = {name}
    cut = len(name)
    for marker in _SPLIT_MARKERS:
        i = name.find(marker)
        if i > 0:
            cut = min(cut, i)
    head = name[:cut].strip()
    if head:
        out.add(head)
    return {v for v in out if len(v) >= MIN_VARIANT_LEN}


def component_index(capabilities: dict) -> dict[str, set[str]]:
    """Variant spelling → the canonical catalog component name(s) it stands for.

    The pool is closed: every key traces back to a ``stack[].name`` in
    ``capabilities.json``. One variant can carry several canonical names (two
    capabilities may list ``PostgreSQL`` with different parenthesised roles), which
    is why the value is a set.
    """
    index: dict[str, set[str]] = {}
    for framework in (capabilities.get("frameworks") or {}).values():
        for cap in (framework or {}).get("capabilities") or []:
            for comp in (cap or {}).get("stack") or []:
                name = str((comp or {}).get("name") or "").strip()
                if not name:
                    continue
                for variant in _variants(name):
                    index.setdefault(variant, set()).add(name)
    for spelling, catalog_variant in _COMPONENT_ALIASES.items():
        if len(spelling) >= MIN_VARIANT_LEN and catalog_variant in index:
            index.setdefault(spelling, set()).update(index[catalog_variant])
    return index


@lru_cache(maxsize=4096)
def _variant_re(variant: str) -> re.Pattern[str]:
    """Whole-word matcher for one variant, hyphens counting as word characters.

    Compiled once per variant per process: the hook rebuilds the index on every
    write, and re-compiling ~200 patterns each time would spend its budget on the
    regex engine rather than on the document.
    """
    return re.compile(r"(?<![\w-])" + re.escape(variant) + r"(?![\w-])")


def mentions(text: str, index: dict[str, set[str]]) -> list[str]:
    """The catalog components a document names, sorted, deduplicated.

    **Case-sensitive, and that is load-bearing.** Measured over this repo's own
    corpus, lowercasing the pool puts ``fleet``, ``fides``, ``cedar`` and ``probo``
    — ordinary English words — into the index and turns every "GitHub" into two
    catalog entries. Case-sensitive matching returns 5 components for
    ``stack-compiler.prd.md``, 2 for the Phase-3 plan, and 0 for ``CLAUDE.md`` and
    ``docs/ARCHITECTURE.md``: a measured zero-false-positive floor, which is worth
    more here than recall the advisory would only spend on noise.
    """
    found: set[str] = set()
    for variant, canonical in index.items():
        if canonical - found and _variant_re(variant).search(text):
            found |= canonical
    return sorted(found)


# ── What the recorded stack says about each mention ───────────────────

def _catalog_records(capabilities: dict) -> dict[str, list[dict]]:
    """Component name → every catalog record carrying that name.

    A component listed under two capabilities can carry two roles (``in-product``
    in one, ``internal-infra`` in another), so the license verdict is taken over
    all of them rather than over whichever one was read first.
    """
    out: dict[str, list[dict]] = {}
    for framework in (capabilities.get("frameworks") or {}).values():
        for cap in (framework or {}).get("capabilities") or []:
            for comp in (cap or {}).get("stack") or []:
                name = str((comp or {}).get("name") or "").strip()
                if name:
                    out.setdefault(name, []).append(comp)
    return out


def _license_verdict(records: list[dict], policy: dict) -> tuple[str, str]:
    """The worst ``rank_lib.license_check`` verdict over a component's records.

    Worst-case, because one permissive listing must not excuse a role in which the
    same license is not permitted. Returns the verdict and the license it applies to.
    """
    worst, license_text = "ok", ""
    for record in records:
        verdict = rank_lib.license_check(record, policy)
        if verdict == "violation":
            return "violation", str(record.get("license") or "")
        if verdict == "exception" and worst == "ok":
            worst, license_text = "exception", str(record.get("license") or "")
    if worst == "ok" and records:
        license_text = str(records[0].get("license") or "")
    return worst, license_text


def classify(mentioned: list[str], stack: dict, capabilities: dict) -> dict:
    """Classify every mentioned component against the recorded stack.

    Each component gets exactly one status — ``on_stack``, ``off_stack``,
    ``undecided``, ``scoped_out``, ``orphaned`` — plus a license verdict from the
    catalog's own ``license_policy``. ``catalog_built`` / ``scoped`` /
    ``chosen_total`` let the caller degrade honestly instead of guessing: with
    nothing chosen yet, "not this product's component" is not a finding anyone can
    act on, and the caller says so rather than reporting 41 phantom contradictions.
    """
    choices = stack.get("choices") or {}
    records = _catalog_records(capabilities)
    policy = capabilities.get("license_policy") or {}

    applicable_total = sum(1 for e in choices.values() if (e or {}).get("applicable", True))
    chosen_total = sum(1 for e in choices.values() if str((e or {}).get("chosen") or "").strip())

    items: list[dict] = []
    for name in mentioned:
        owners = [(key, entry or {}) for key, entry in choices.items()
                  if name in ((entry or {}).get("options") or [])]
        verdict, license_text = _license_verdict(records.get(name) or [], policy)
        item = {
            "component": name,
            "status": "orphaned",
            "capabilities": sorted(key for key, _ in owners),
            "chosen_for": [],
            "conflicts": [],
            "reasons": [],
            "license": license_text,
            "license_verdict": verdict,
        }
        applicable = [(k, e) for k, e in owners if e.get("applicable", True)]
        item["chosen_for"] = sorted(
            k for k, e in applicable if str(e.get("chosen") or "").strip() == name
        )
        item["conflicts"] = [
            {"key": k, "chosen": str(e.get("chosen") or "").strip()}
            for k, e in sorted(applicable, key=lambda kv: kv[0])
            if str(e.get("chosen") or "").strip() and str(e.get("chosen") or "").strip() != name
        ]
        if item["chosen_for"]:
            item["status"] = "on_stack"
        elif item["conflicts"]:
            item["status"] = "off_stack"
        elif applicable:
            item["status"] = "undecided"
        elif owners:
            item["status"] = "scoped_out"
            item["reasons"] = [
                str(e.get("applicability_reason") or "").strip()
                for _, e in sorted(owners, key=lambda kv: kv[0])
                if str(e.get("applicability_reason") or "").strip()
            ]
        items.append(item)

    result = {
        "catalog_built": bool(records),
        "scoped": rank_lib.is_scoped(stack),
        "applicable_total": applicable_total,
        "chosen_total": chosen_total,
        "mentions": items,
        "violations": [i for i in items if i["license_verdict"] == "violation"],
        "exceptions": [i for i in items if i["license_verdict"] == "exception"],
    }
    for status in _STATUS_ORDER:
        result[status] = [i for i in items if i["status"] == status]
    return result


def catalog_names(capabilities: dict) -> set[str]:
    """Every component name the catalog describes — the closed pool, by identity."""
    return set(_catalog_records(capabilities))


def applicable_keys(stack: dict) -> list[str]:
    """The capability keys this product still has to deliver, sorted."""
    return sorted(key for key, entry in (stack.get("choices") or {}).items()
                  if (entry or {}).get("applicable", True))


# ── The agent proposes, this decides ──────────────────────────────────

def verdict(raw: dict, stack: dict, capabilities: dict) -> dict:
    """Turn the validator agent's judgment into a pass/fail.

    A *mention* is not a proposal — this PRD names Keycloak as an illustration, and
    the whole point of spending an LLM call is to tell that from "we will use
    Keycloak". Only the agent can read that intent, and only this function decides
    what it means: ``proposed`` is filtered against the catalog's own component
    names and ``ignored_capabilities`` against this product's applicable keys, so a
    name the agent invented can neither inflate nor deflate the result — the same
    split as ``compliance-base``'s ``precheck.capability_verdict``.

    The run fails when a *proposed* component contradicts a recorded choice or
    carries a license the policy forbids. An ignored capability is reported, never
    fatal: it is a gap in a document, not a contradiction of a decision.
    """
    proposed = sorted(
        {str(name).strip() for name in (raw.get("proposed") or []) if str(name).strip()}
        & catalog_names(capabilities)
    )
    ignored = sorted(
        {str(key).strip() for key in (raw.get("ignored_capabilities") or []) if str(key).strip()}
        & set(applicable_keys(stack))
    )
    classified = classify(proposed, stack, capabilities)
    return {
        "proposed": proposed,
        "ignored_capabilities": ignored,
        "off_stack": classified["off_stack"],
        "scoped_out": classified["scoped_out"],
        "violations": classified["violations"],
        "ok": not (classified["off_stack"] or classified["violations"]),
    }


# ── The advisory the hook prints ──────────────────────────────────────

def render_summary(result: dict, kind: str, cfg: dict) -> str:
    """One advisory paragraph, mirroring ``co-post-tooluse.py``'s ``_summary``.

    Names the unbuilt / unscoped / nothing-chosen state and the command that fixes
    it, otherwise leads with the contradictions. Advisory only: an ``undecided``
    capability is pending work, never a violation.
    """
    stack_dir = str(cfg.get("stack_dir") or "stack-base")
    compliance_dir = str(cfg.get("compliance_dir") or "compliance-base")
    noun = "PRD" if kind == "prd" else "plan"

    if not result["catalog_built"]:
        return (f"Stack gate: no component catalog — run "
                f"`/neurawork-cc-harness:co-capabilities` in {compliance_dir} to derive it; "
                f"until then this {noun}'s components are not checked.")
    if not result["scoped"]:
        return (f"Stack gate: the stack carries no scoping decisions — run "
                f"`uv run --directory {stack_dir} python scripts/scope.py` first; "
                f"until then this {noun}'s components are not checked.")

    named = len(result["mentions"])
    if not named:
        return f"Stack gate: this {noun} names no catalog component."

    if not result["chosen_total"]:
        return (f"Stack gate: this {noun} names {named} catalog component(s), but no component "
                f"is chosen yet — run `uv run --directory {stack_dir} python "
                f"scripts/selection.py` to record this product's choices; until then there is "
                f"no allowlist to check them against.")

    parts: list[str] = []
    if result["off_stack"]:
        shown = "; ".join(
            f"{i['component']} (`{i['conflicts'][0]['key']}` records "
            f"{i['conflicts'][0]['chosen']})"
            for i in result["off_stack"][:5]
        )
        more = " …" if len(result["off_stack"]) > 5 else ""
        parts.append(f"{len(result['off_stack'])} off-stack: {shown}{more}")
    if result["scoped_out"]:
        parts.append(f"{len(result['scoped_out'])} on a scoped-out capability: "
                     + ", ".join(i["component"] for i in result["scoped_out"][:5]))
    if result["violations"]:
        parts.append(f"{len(result['violations'])} license violation(s): "
                     + ", ".join(f"{i['component']} ({i['license']})"
                                 for i in result["violations"][:5]))
    if result["undecided"]:
        parts.append(f"{len(result['undecided'])} filling a capability still undecided")
    if result["orphaned"]:
        parts.append(f"{len(result['orphaned'])} not in any capability's options "
                     "(stack.json is stale — re-run `scripts/stack.py --scaffold`)")
    if result["exceptions"]:
        parts.append(f"{len(result['exceptions'])} carrying a recorded license exception")

    head = (f"Stack gate: {named} catalog component(s) named, "
            f"{len(result['on_stack'])} of them this product's recorded choice.")
    if not parts:
        return head
    return head + " " + "; ".join(parts) + "."


# ── Debounce ──────────────────────────────────────────────────────────

def load_state(path: Path | str) -> dict:
    """Read the gate's spawn ledger, or ``{}`` when absent/corrupt. Never raises."""
    p = Path(path)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(path: Path | str, state: dict) -> None:
    """Write the ledger atomically (tmp + replace), as ``scope.save_state`` does."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def should_spawn(state: dict, doc_path: str, text_hash: str, result: dict) -> bool:
    """Whether this write earns an LLM run.

    False when the document's content already hashed to this value (a save that
    changed nothing is not a new question), and false when there is nothing to
    enforce — an unbuilt catalog, or a stack with no chosen component, where every
    finding would be "you have not decided yet" and the advisory already said so.
    """
    if not result.get("catalog_built") or not result.get("chosen_total"):
        return False
    entry = (state.get("documents") or {}).get(str(doc_path)) or {}
    return entry.get("hash") != text_hash


def record_spawn(state: dict, doc_path: str, text_hash: str, at: str) -> dict:
    """The ledger with this spawn stamped in — written *before* the spawn, so two
    writes in the same second cannot both fire. ``validate.py`` completes the entry."""
    documents = dict(state.get("documents") or {})
    documents[str(doc_path)] = {"hash": text_hash, "spawned_at": at,
                                "report": None, "ok": None}
    return {**state, "documents": documents}


def record_outcome(state: dict, doc_path: str, report: str, ok: bool, at: str) -> dict:
    """The ledger with the validator's outcome added to an existing entry, so
    "did the agent actually run for this edit, and what did it find" is answerable."""
    documents = dict(state.get("documents") or {})
    entry = dict(documents.get(str(doc_path)) or {})
    entry.update({"report": report, "ok": ok, "completed_at": at})
    documents[str(doc_path)] = entry
    return {**state, "documents": documents}
