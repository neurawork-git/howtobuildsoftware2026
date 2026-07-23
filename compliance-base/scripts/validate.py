"""Deep LLM validation of a PRP plan against the compliance catalog.

Spawned detached by the PostToolUse hook (or run via /neurawork-cc-harness:co-validate).
Reads the plan + the built catalog, then a single Claude Agent SDK agent writes a
gap report to ``reports/<plan-stem>.md`` per the AGENTS.md validation rules.

Usage:
    uv run python scripts/validate.py .claude/PRPs/plans/<name>.plan.md
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

from config import (
    AGENTS_FILE,
    CATALOG_DIR,
    REPORTS_DIR,
    ROOT_DIR,
    load_cfg,
)
from utils import validation_frameworks

from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude


def _catalog_text(frameworks: list[str]) -> str:
    parts = []
    for fw in frameworks:
        path = CATALOG_DIR / f"{fw}.json"
        if path.exists():
            parts.append(f"### {fw}\n```json\n{path.read_text(encoding='utf-8')}\n```")
    return "\n\n".join(parts) if parts else "(catalog not built yet)"


def _build_prompt(plan_text: str, catalog_text: str, report_path: Path) -> str:
    constitution = AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""
    return f"""You are the compliance validator. Check the PRP plan below against the
catalog, following the constitution's validation rules exactly.

## Constitution (AGENTS.md)

{constitution}

## Compliance catalog

{catalog_text}

## PRP plan under review

{plan_text}

## Task

Decide which catalog constraints APPLY to this plan (via each constraint's
`applies_when`), then for every applicable MANDATORY constraint decide addressed /
unaddressed / unclear by reasoning over the plan. Write the report using the Write
tool to exactly this file, and write nothing else:

    {report_path}

The report: a one-line summary, a markdown table (constraint id | title | status |
evidence-or-gap), then a short 'Recommended additions' list. Cite constraint ids.
Do not flag inapplicable constraints."""


async def validate_one(plan_text: str, report_path: Path, cfg: dict) -> float:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    catalog_text = _catalog_text(validation_frameworks(cfg))
    cost = 0.0
    async for message in query(
        prompt=_build_prompt(plan_text, catalog_text, report_path),
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
    try:
        assert_in_repo_not_dotclaude(report_path, repo_root)
    except WriteGuardError as e:
        print(f"Refusing to write report: {e}")
        return 1
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    plan_text = plan_path.read_text(encoding="utf-8")
    cost = asyncio.run(validate_one(plan_text, report_path, cfg))
    print(json.dumps({"report": str(report_path), "cost_usd": cost}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
