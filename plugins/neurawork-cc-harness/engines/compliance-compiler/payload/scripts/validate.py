"""Deep LLM validation of a PRP plan against the compliance catalog.

Spawned detached by the PostToolUse hook (or run via /neurawork-cc-harness:co-validate).
Reads the plan + the built catalog, then a single Claude Agent SDK agent writes a
gap report to ``reports/<plan-stem>.md`` per the AGENTS.md validation rules.

The agent also judges which derived **capabilities** the plan makes applicable and
writes them to ``reports/<plan-stem>.capabilities.json``; this script then does the
set math (applicable ∩ mandatory-linked − declared) and **exits non-zero** when the
plan omits a capability its own content makes applicable. The agent never asserts its
own verdict — same split as the coverage gate in ``capabilities.py``.

Exit: 0 when nothing mandatory is undeclared (or the capability layer is not built /
the verdict is unusable, both reported out loud); 1 when the gate fails.

Usage:
    uv run python scripts/validate.py .claude/PRPs/plans/<name>.plan.md
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

import stack
from config import (
    AGENTS_FILE,
    CATALOG_DIR,
    REPORTS_DIR,
    ROOT_DIR,
    load_cfg,
)
from precheck import capability_verdict, declared_capabilities, known_capabilities
from utils import load_stack, validation_frameworks

from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude


def _catalog_text(frameworks: list[str]) -> str:
    parts = []
    for fw in frameworks:
        path = CATALOG_DIR / f"{fw}.json"
        if path.exists():
            parts.append(f"### {fw}\n```json\n{path.read_text(encoding='utf-8')}\n```")
    return "\n\n".join(parts) if parts else "(catalog not built yet)"


def _capabilities_text(known: dict[str, dict], mandatory_linked: set[str]) -> str:
    """One compact line per capability — key, name, category, and the decision state
    recorded in stack.json. The 247 component records stay out: which component is
    right is the `st-` gate's question, not this one."""
    if not known:
        return "(capability catalog not built yet)"
    choices = load_stack().get("choices") or {}
    lines = []
    for key, cap in known.items():
        entry = choices.get(key) or {}
        lines.append(
            f"- `{key}` — {cap['name']} [{cap.get('category', '')}] · "
            f"mandatory-linked: {'yes' if key in mandatory_linked else 'no'} · "
            f"applicable: {'no' if entry.get('applicable') is False else 'yes'} · "
            f"chosen: {entry.get('chosen') or '(none)'}"
        )
    return "\n".join(lines)


def _build_prompt(
    plan_text: str,
    catalog_text: str,
    report_path: Path,
    capabilities_text: str,
    declared: dict,
    verdict_path: Path,
) -> str:
    constitution = AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""
    declared_text = (
        "none — " + (declared["reason"] or "(no reason given)") if declared["none"]
        else ", ".join(declared["keys"]) or "(no declaration in the plan)"
    )
    return f"""You are the compliance validator. Check the PRP plan below against the
catalog, following the constitution's validation rules exactly.

## Constitution (AGENTS.md)

{constitution}

## Compliance catalog

{catalog_text}

## Capability catalog (derived)

{capabilities_text}

## Capabilities the plan declares

{declared_text}

## PRP plan under review

{plan_text}

## Task 1 — constraints

Decide which catalog constraints APPLY to this plan (via each constraint's
`applies_when`), then for every applicable MANDATORY constraint decide addressed /
unaddressed / unclear by reasoning over the plan. Write the report using the Write
tool to exactly this file:

    {report_path}

The report: a one-line summary, a markdown table (constraint id | title | status |
evidence-or-gap), then a short 'Recommended additions' list. Cite constraint ids.
Do not flag inapplicable constraints. Close it with a short 'Capabilities' section
naming the applicable capability keys and which of them the plan does not declare.

## Task 2 — capabilities

Decide which capabilities in the capability catalog above this plan MAKES APPLICABLE
— judge the plan's own content, not its declaration; a plan that stores personal
data makes the data-protection capabilities applicable whether or not it says so.
Write the verdict using the Write tool to exactly this file:

    {verdict_path}

Write only this JSON object, nothing else:

    {{"applicable": ["<capability key>", ...], "reasoning": "<one or two sentences>"}}

Every key must be copied verbatim from the capability catalog above — never invent
one. An empty list is a valid verdict for a plan with no compliance surface.

Write these two files and nothing else."""


async def validate_one(
    plan_text: str,
    report_path: Path,
    cfg: dict,
    known: dict,
    mandatory_linked: set,
    declared: dict,
    verdict_path: Path,
) -> float:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    catalog_text = _catalog_text(validation_frameworks(cfg))
    cost = 0.0
    async for message in query(
        prompt=_build_prompt(
            plan_text,
            catalog_text,
            report_path,
            _capabilities_text(known, mandatory_linked),
            declared,
            verdict_path,
        ),
        options=ClaudeAgentOptions(
            cwd=str(ROOT_DIR),
            system_prompt={"type": "preset", "preset": "claude_code"},
            allowed_tools=["Read", "Write"],
            permission_mode="acceptEdits",
            max_turns=30,
            setting_sources=[],
            strict_mcp_config=True,
            model=(cfg.get("model") or None),
        ),
    ):
        if isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0
    return cost


def _load_verdict(path: Path) -> dict | None:
    """The agent's capability verdict, or ``None`` when it is absent or unusable —
    the caller then says so out loud rather than passing silently."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("applicable"), list) else None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate.py <path-to-plan.plan.md>")
        return 2
    plan_path = Path(sys.argv[1])
    if not plan_path.is_absolute():
        plan_path = (ROOT_DIR.parent / plan_path).resolve()
    if not plan_path.exists():
        print(f"Plan not found: {plan_path}")
        return 1

    cfg = load_cfg()
    repo_root = ROOT_DIR.parent
    report_path = REPORTS_DIR / f"{plan_path.stem}.md"
    verdict_path = REPORTS_DIR / f"{plan_path.stem}.capabilities.json"
    try:
        assert_in_repo_not_dotclaude(report_path, repo_root)
        assert_in_repo_not_dotclaude(verdict_path, repo_root)
    except WriteGuardError as e:
        print(f"Refusing to write report: {e}")
        return 1
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    plan_text = plan_path.read_text(encoding="utf-8")
    catalog, known = known_capabilities(validation_frameworks(cfg), None)
    mandatory_linked = stack.mandatory_linked_keys(catalog) if known else set()
    declared = declared_capabilities(plan_text)
    verdict_path.unlink(missing_ok=True)  # never judge on a previous run's verdict

    cost = asyncio.run(
        validate_one(plan_text, report_path, cfg, known, mandatory_linked,
                     declared, verdict_path)
    )
    out: dict = {"report": str(report_path), "cost_usd": cost}

    if not known:
        print(json.dumps({**out, "capabilities": "not built — gate skipped"}))
        return 0

    raw = _load_verdict(verdict_path)
    if raw is None:
        print(json.dumps({**out, "capabilities": f"gate skipped: no usable verdict at "
                                                 f"{verdict_path}"}))
        return 0

    verdict = capability_verdict(
        raw.get("applicable") or [], declared["keys"], mandatory_linked, known_keys=known
    )
    out["verdict"] = str(verdict_path)
    out["capabilities"] = verdict
    print(json.dumps(out))
    return 1 if verdict["undeclared_mandatory"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
