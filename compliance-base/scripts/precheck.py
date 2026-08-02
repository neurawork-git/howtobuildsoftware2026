"""Fast, deterministic (no-LLM) structural check of a PRP plan vs the catalog.

Used inline by the PostToolUse validator hook (which has a hard timeout) to give
immediate feedback; the deep semantic check is delegated to ``validate.py``.
Pure stdlib + catalog readers — cheap to unit-test.
"""

from __future__ import annotations

import re
from pathlib import Path

import rules_block
import stack
from config import DEFAULT_CFG
from utils import (
    load_capability_catalog,
    load_constraints,
    load_stack,
    mandatory_ids,
    referenced_ids,
    validation_frameworks,
)

_COMPLIANCE_SECTION_RE = re.compile(r"^##\s+Compliance", re.MULTILINE)
_MISSING = object()

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

# The plan template's validation gate. A PREFIX match on purpose: 12 of this repo's 22
# plans write `## Validation` and 10 write `## Validation Commands`, so an exact match
# would report a missing section on 45% of the corpus on its first run.
_VALIDATION_HEADING_RE = re.compile(r"^##\s+Validation\b.*$", re.MULTILINE)
_NEXT_H2_RE = re.compile(r"^##\s", re.MULTILINE)

# Commands are read ONLY from delimited spans — inline single-backtick spans and fenced
# blocks. Same discipline as _CAP_KEY_RE's fullmatch: prose in this corpus discusses
# `pytest` without invoking it (nw-rules-init-baseline-rules.plan.md:286,341 compares
# pytest-vs-unittest DETECTION), and a substring match would report that as a gate.
_FENCE_RE = re.compile(r"^\s*`{3,}[A-Za-z0-9_+-]*\s*$")
_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")

# A delimited span counts as a command when its FIRST token is a bare program name or a
# slash command — `pytest`, `make test`, `cd x && pytest`, `/nw-ship-pr` pass; the file
# references that share those spans (`.claude/ship-pr.local.md`, `precheck.py:184-198`,
# `payload/scripts`) do not.
_COMMAND_HEAD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.+-]*|/[A-Za-z][A-Za-z0-9_-]*")

# Test files, searched across the WHOLE document: the plan template keeps the top-level
# validation gate at directory granularity and puts file names in the task-level
# `**Tests**` blocks, so section scope would find one in only 3 of the 22 plans instead
# of 20.
_TEST_FILE_RES = (
    re.compile(r"\btest_[A-Za-z0-9_]+\.py\b"),
    re.compile(r"\b[A-Za-z0-9_]+_test\.py\b"),
    re.compile(r"\b[A-Za-z0-9_.-]+\.(?:test|spec)\.[jt]sx?\b"),
)


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


def _matches(parts: tuple[str, ...], plans: tuple[str, ...]) -> bool:
    """True iff ``parts`` starts with ``plans``, where a ``*`` segment in ``plans``
    matches exactly one segment of ``parts`` (``.claude/PRPs/*/plans``)."""
    return len(parts) >= len(plans) and all(
        want == "*" or want == have for want, have in zip(plans, parts)
    )


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
        if plans and _matches(parts, plans):
            return not any(seg in archived for seg in parts[len(plans):])
    return False


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


def validation_section(plan_text: str) -> str | None:
    """The `## Validation` section body, or ``None`` when the plan has no such heading."""
    m = _VALIDATION_HEADING_RE.search(plan_text)
    if not m:
        return None
    rest = plan_text[m.end():]
    nxt = _NEXT_H2_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _delimited_spans(text: str) -> list[str]:
    """Every inline-backtick span and fenced-block line in ``text``, in order.

    Fenced lines are taken one per line — the rules block and every multi-command gate in
    this corpus write one command per line — and the fence markers themselves are dropped.
    """
    spans: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            if line.strip():
                spans.append(line.strip())
            continue
        spans.extend(s.strip() for s in _INLINE_CODE_RE.findall(line))
    return [s for s in spans if s]


def _looks_runnable(span: str) -> bool:
    head = span.split(maxsplit=1)[0] if span.split() else ""
    return bool(head) and bool(_COMMAND_HEAD_RE.fullmatch(head))


def _normalise(command: str) -> str:
    return " ".join(command.split())


def named_test_files(plan_text: str) -> list[str]:
    """Test-file paths named anywhere in the plan, inside delimited spans only."""
    found: set[str] = set()
    for span in _delimited_spans(plan_text):
        for pattern in _TEST_FILE_RES:
            found.update(pattern.findall(span))
    return sorted(found)


def validation_precheck(plan_text: str, repo_commands: list[str] | None = None) -> dict:
    """Deterministic signals about a plan's validation gate: is the section there, does it
    name a runnable command, and does the plan name a test file anywhere.

    Advisory by construction. ``repo_commands_named == 0`` with a non-empty repo command
    list is a COUNT, never a verdict: a plan may legitimately run a narrower focused
    command than the repo's whole suite. Nothing here is checked against the file tree —
    this reports what the plan SAYS, never what the repository contains.
    """
    repo_commands = [_normalise(c) for c in (repo_commands or []) if c.strip()]
    section = validation_section(plan_text)
    commands = (
        [_normalise(s) for s in _delimited_spans(section) if _looks_runnable(s)]
        if section is not None
        else []
    )
    named = {c for c in repo_commands if c in commands}
    return {
        "section_present": section is not None,
        "commands": commands,
        "named_test_files": named_test_files(plan_text),
        "repo_commands": repo_commands,
        "repo_commands_total": len(repo_commands),
        "repo_commands_named": len(named),
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


def precheck(
    plan_text: str,
    cfg: dict,
    catalog_dir: Path | None = None,
    repo_root: Path | str | None = None,
) -> dict:
    """Deterministic structural signals for a plan against the catalog.

    ``repo_root`` is optional so every existing caller (``validate.py``, the tests) keeps
    working unchanged: without it the validation check still runs, it just has no declared
    repo command list to compare the plan against.
    """
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
        "validation": validation_precheck(
            plan_text, rules_block.read(repo_root) if repo_root is not None else []
        ),
    }
