"""PostToolUse hook — validate a PRP plan against the compliance catalog on write.

Fires after every tool call; fast-exits unless the tool was a Write/Edit to a live
PRP plan file (``.claude/PRPs/plans/*.plan.md``). For a plan write it runs the
deterministic ``precheck`` inline (<1s), emits an advisory summary as
additionalContext, and spawns the deep LLM ``validate.py`` detached (a report lands
in ``reports/``). ``validate_mode: "block"`` additionally returns a block decision
when mandatory constraints are unaddressed.

The exact PostToolUse payload field names are read defensively; on any unexpected
shape the hook no-ops rather than crashing the session.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))                       # _shared
sys.path.insert(0, str(KDIR / "scripts"))           # config, precheck

from _shared.hookio import child_env, read_hook_input, recursion_guard

recursion_guard()

from _shared.gitctx import in_worktree, main_checkout_root
from config import load_cfg
from precheck import is_plan_path, precheck

WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def effective_root() -> Path:
    """Compliance install dir to use — main checkout's when inside a worktree."""
    if in_worktree(str(KDIR)):
        main_root = main_checkout_root(str(KDIR))
        if main_root is not None:
            return main_root / KDIR.name
    return KDIR


def _plan_path_from(data: dict) -> str:
    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    return tool_input.get("file_path") or tool_input.get("path") or ""


def _capability_summary(cp: dict) -> str:
    """One advisory sentence about the plan's capability declaration — or, when the
    capability layer is not built, about how to build it. Never blocks — applicability
    is decided by the detached validator, not here."""
    if not cp["catalog_built"]:
        return (" Capability layer not built — run "
                "`/neurawork-cc-harness:co-capabilities` to derive it; until then plans "
                "are checked against constraints only.")
    if not cp["declaration_present"]:
        return (" No '**Capabilities**:' declaration found — add one to the '## Compliance' "
                "section listing the capability keys this plan delivers (e.g. "
                "`gdpr/audit-logging`, see catalog/capabilities.md), or "
                "`**Capabilities**: none — <reason>`.")
    if cp["unknown_keys"]:
        return (f" {len(cp['unknown_keys'])} declared capability key(s) not in the catalog: "
                f"{', '.join(cp['unknown_keys'])}.")
    if cp["declared_none"]:
        reason = "" if cp["none_reason"] else " (no reason given)"
        return f" Plan declares no compliance capabilities{reason}."
    extra = []
    if cp["declared_unchosen"]:
        extra.append(f"{len(cp['declared_unchosen'])} with no chosen component in stack.json")
    if cp["declared_not_applicable"]:
        extra.append(f"{len(cp['declared_not_applicable'])} marked not applicable")
    tail = f" ({'; '.join(extra)})" if extra else ""
    return f" Plan declares {len(cp['declared'])} capability/capabilities{tail}."


def _summary(pc: dict) -> str:
    if not pc["catalog_built"]:
        return ("Compliance catalog not built yet — run "
                "`/neurawork-cc-harness:co-extract` to enable plan checks.")
    caps = _capability_summary(pc["capabilities"])
    missing = pc["missing_mandatory_ids"]
    if not missing:
        return (f"Compliance precheck: all {pc['mandatory_total']} mandatory "
                f"constraints are referenced by this plan.{caps}")
    shown = ", ".join(missing[:15]) + (" …" if len(missing) > 15 else "")
    section = "" if pc["has_compliance_section"] else " (plan has no '## Compliance' section)"
    return (f"Compliance precheck: {len(missing)}/{pc['mandatory_total']} mandatory "
            f"constraints not referenced by this plan{section}. A deeper report is "
            f"being generated in the compliance reports/ dir. Unreferenced: {shown}{caps}")


def main() -> None:
    data = read_hook_input()
    if data.get("tool_name") not in WRITE_TOOLS:
        return

    path_str = _plan_path_from(data)
    repo_root = KDIR.parent  # the working-tree root (main checkout or worktree)
    if not is_plan_path(path_str, repo_root):
        return

    plan_path = Path(path_str)
    if not plan_path.is_absolute():
        plan_path = (repo_root / plan_path).resolve()
    if not plan_path.exists():
        return

    cfg = load_cfg()
    root = effective_root()
    catalog_dir = root / "catalog"
    try:
        pc = precheck(plan_path.read_text(encoding="utf-8"), cfg, catalog_dir)
    except OSError:
        return

    # Spawn the deep validator (only worthwhile once the catalog exists).
    if pc["catalog_built"]:
        cmd = ["uv", "run", "--directory", str(root), "python",
               "scripts/validate.py", str(plan_path)]
        env = {**child_env(), "COMPLIANCE_ROOT": str(root)}
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        except OSError:
            pass

    summary = _summary(pc)
    output: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": summary,
        }
    }
    blocking = (
        cfg.get("validate_mode") == "block"
        and pc["catalog_built"]
        and pc["missing_mandatory_ids"]
    )
    if blocking:
        output["decision"] = "block"
        output["reason"] = summary
    print(json.dumps(output))


if __name__ == "__main__":
    main()
