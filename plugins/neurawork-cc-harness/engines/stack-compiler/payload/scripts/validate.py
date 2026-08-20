"""Deep LLM check of a PRD or PRP plan against the recorded component stack.

Spawned detached by ``hooks/st-post-tooluse.py``. The hook's inline precheck already
knows which catalog components the document names and what ``stack.json`` records
about each; what it cannot know is whether the document *proposes* a component or
merely mentions one — a comparison, a prior-art note, an example. One Claude Agent
SDK agent reads the document for that intent, per the AGENTS.md gate rules, and
writes a report to ``reports/<stem>.md`` plus a verdict to
``reports/<stem>.stack.json``.

The agent never asserts its own pass/fail: this script filters the agent's
``proposed`` components against the catalog and its ``ignored_capabilities`` against
this product's applicable keys, then does the set math and owns the exit code — the
same split ``compliance-base``'s ``validate.py`` uses for capabilities.

This engine reads ``stack.json``. It never writes it; ``chosen`` is recorded only by
``scripts/selection.py``, through the schema owner.

Exit: 0 when no proposed component contradicts a recorded choice or the license
policy (or the verdict is unusable / there is nothing to enforce — both reported out
loud); 1 when the gate fails.

``--repo-root`` names the working tree the document belongs to, which the catalog is
then read from. The hook passes it because the two can differ: inside a worktree the
reports and the ledger belong next to the main checkout (they must survive
``git worktree remove``), while the decisions the document is judged against are the
ones its own branch records.

Usage:
    uv run python scripts/validate.py .claude/PRPs/prds/<name>.prd.md
    uv run python scripts/validate.py <document> --repo-root <working-tree>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

import gate_lib
import rank_lib
import scope_lib
from config import (
    AGENTS_FILE,
    GATE_STATE_FILE,
    REPORTS_DIR,
    ROOT_DIR,
    load_cfg,
    now_iso,
)

# _shared/ is imported inside main(), as in selection.py: it exists next to scripts/
# only in an installed repo, so the pure logic stays importable from payload/scripts.


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


def _precheck_text(result: dict) -> str:
    """The deterministic finding per mentioned component — the agent's starting point."""
    if not result["mentions"]:
        return "(this document names no catalog component)"
    lines = []
    for item in result["mentions"]:
        detail = ""
        if item["status"] == "on_stack":
            detail = " · chosen for " + ", ".join(f"`{k}`" for k in item["chosen_for"])
        elif item["status"] == "off_stack":
            detail = " · " + "; ".join(
                f"`{c['key']}` records {c['chosen']}" for c in item["conflicts"]
            )
        elif item["status"] == "undecided":
            detail = " · options of " + ", ".join(f"`{k}`" for k in item["capabilities"])
        elif item["status"] == "scoped_out":
            detail = " · ruled out: " + (item["reasons"][0] if item["reasons"] else "no reason recorded")
        lic = "" if item["license_verdict"] == "ok" else f" · license {item['license_verdict']}"
        lines.append(f"- **{item['component']}** — {item['status']}{detail}{lic}")
    return "\n".join(lines)


def _applicable_text(stack: dict) -> str:
    """One line per applicable capability: the key, its name, and what is chosen."""
    choices = stack.get("choices") or {}
    lines = []
    for key in gate_lib.applicable_keys(stack):
        entry = choices.get(key) or {}
        lines.append(f"- `{key}` — {entry.get('capability', '')} · "
                     f"chosen: {entry.get('chosen') or '(none)'}")
    return "\n".join(lines) or "(no applicable capability)"


def _build_prompt(
    doc_text: str,
    kind: str,
    result: dict,
    stack: dict,
    report_path: Path,
    verdict_path: Path,
) -> str:
    constitution = AGENTS_FILE.read_text(encoding="utf-8") if AGENTS_FILE.exists() else ""
    noun = "PRD" if kind == "prd" else "PRP plan"
    return f"""You are the stack gate. Check the {noun} below against this product's
recorded component stack, following the constitution's gate rules exactly.

## Constitution (AGENTS.md)

{constitution}

## This product's applicable capabilities and recorded choices

{_applicable_text(stack)}

## Deterministic precheck — the catalog components this document names

{_precheck_text(result)}

## The {noun} under review

{doc_text}

## Task 1 — the report

Decide, for every component in the precheck above, whether this document *proposes*
it or merely *mentions* it. A comparison, a prior-art note, an example, or a
description of something the repository already runs is a mention, not a proposal.
Then name the applicable capabilities this document plainly needs and does not
address. Write the report using the Write tool to exactly this file:

    {report_path}

The report: a one-line summary, a markdown table (component | proposed or mentioned |
what stack.json records | what to do), then a short 'Capabilities this document
ignores' list. Report contradictions; never argue against a recorded choice or a
recorded applicability decision.

## Task 2 — the verdict

Write the verdict using the Write tool to exactly this file:

    {verdict_path}

Write only this JSON object, nothing else:

    {{"proposed": ["<component name>", ...],
      "ignored_capabilities": ["<capability key>", ...],
      "reasoning": "<one or two sentences>"}}

Every component name must be copied verbatim from the precheck above and every
capability key verbatim from the applicable-capabilities list — never invent one.
Empty lists are a valid verdict for a document that proposes nothing.

Write these two files and nothing else."""


async def validate_one(prompt: str, cfg: dict) -> float:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    cost = 0.0
    async for message in query(
        prompt=prompt,
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
    """The agent's verdict, or ``None`` when it is absent or unusable — the caller
    then says so out loud rather than passing silently."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("proposed"), list) else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a PRD or PRP plan against the recorded component stack"
    )
    parser.add_argument("document", nargs="?",
                        help="the .prd.md or .plan.md file to check")
    parser.add_argument("--repo-root", type=str, default="", metavar="PATH",
                        help="working tree the document belongs to; its catalog is the "
                             "one checked against (default: the install's own repo)")
    args = parser.parse_args()
    if not args.document:
        print("Usage: validate.py <path-to-document.prd.md|.plan.md> [--repo-root PATH]")
        return 2

    cfg = load_cfg()
    # Where the decisions are read from — the document's own working tree. Outputs
    # (REPORTS_DIR, the ledger) stay under ROOT_DIR, which a hook redirects to the main
    # checkout so they survive `git worktree remove`.
    repo_root = Path(args.repo_root).resolve() if args.repo_root else ROOT_DIR.parent
    doc_path = Path(args.document)
    if not doc_path.is_absolute():
        doc_path = (repo_root / doc_path).resolve()
    if not doc_path.exists():
        print(f"Document not found: {doc_path}")
        return 1
    kind = gate_lib.document_kind(str(doc_path), repo_root, cfg) or "plan"

    comp = repo_root / str(cfg.get("compliance_dir") or "compliance-base")
    capabilities_json = comp / "catalog" / "capabilities.json"
    stack_json = comp / "catalog" / "stack.json"
    if not comp.is_dir():
        print(f"No compliance install at {comp} — the stack gate has nothing to check "
              "against. Install compliance-compiler first, or set 'compliance_dir' in "
              "config.json.")
        return 1
    if not capabilities_json.exists():
        print(f"No {capabilities_json} — run "
              f"`uv run --directory {comp.name} python scripts/capabilities.py` first")
        return 1
    if not stack_json.exists():
        print(f"No {stack_json} — run "
              f"`uv run --directory {comp.name} python scripts/stack.py --scaffold` first")
        return 1

    capabilities = _load_json(capabilities_json)
    stack = _load_json(stack_json)
    if not rank_lib.is_scoped(stack):
        print(f"{stack_json} carries no scoping decisions — run "
              f"`uv run --directory {ROOT_DIR.name} python scripts/scope.py` first. "
              "An unscoped stack would check this document against every capability in "
              "the catalog.")
        return 1

    report_path = REPORTS_DIR / f"{doc_path.stem}.md"
    verdict_path = REPORTS_DIR / f"{doc_path.stem}.stack.json"
    from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude
    try:
        # Guarded against the INSTALL's repo, not the document's: the reports live under
        # ROOT_DIR, which is the main checkout when a worktree hook redirected us here.
        assert_in_repo_not_dotclaude(report_path, ROOT_DIR.parent)
        assert_in_repo_not_dotclaude(verdict_path, ROOT_DIR.parent)
    except WriteGuardError as e:
        print(f"Refusing to write report: {e}")
        return 1
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    doc_text = doc_path.read_text(encoding="utf-8")
    result = gate_lib.classify(
        gate_lib.mentions(doc_text, gate_lib.component_index(capabilities)), stack, capabilities
    )
    verdict_path.unlink(missing_ok=True)  # never judge on a previous run's verdict

    cost = asyncio.run(validate_one(
        _build_prompt(doc_text, kind, result, stack, report_path, verdict_path), cfg
    ))
    out: dict = {"document": str(doc_path), "report": str(report_path), "cost_usd": cost}

    state = gate_lib.load_state(GATE_STATE_FILE)
    text_hash = scope_lib.product_hash(doc_text)
    if not state.get("documents", {}).get(str(doc_path)):
        # Run by hand rather than by the hook — stamp the ledger so a later write of
        # the same content does not spend a second agent on it.
        state = gate_lib.record_spawn(state, str(doc_path), text_hash, now_iso())

    def _finish(ok: bool, note: object) -> int:
        gate_lib.save_state(
            GATE_STATE_FILE,
            gate_lib.record_outcome(state, str(doc_path), str(report_path), ok, now_iso()),
        )
        print(json.dumps({**out, "gate": note}))
        return 0 if ok else 1

    if not result["chosen_total"]:
        return _finish(True, "no component chosen yet — gate skipped")

    raw = _load_verdict(verdict_path)
    if raw is None:
        return _finish(True, f"gate skipped: no usable verdict at {verdict_path}")

    gate = gate_lib.verdict(raw, stack, capabilities)
    out["verdict"] = str(verdict_path)
    return _finish(gate["ok"], {
        "proposed": gate["proposed"],
        "off_stack": [{"component": i["component"], "conflicts": i["conflicts"]}
                      for i in gate["off_stack"]],
        "violations": [{"component": i["component"], "license": i["license"]}
                       for i in gate["violations"]],
        "ignored_capabilities": gate["ignored_capabilities"],
    })


if __name__ == "__main__":
    raise SystemExit(main())
