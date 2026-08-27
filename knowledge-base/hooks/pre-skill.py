"""PreToolUse hook — inject the kb-researcher directive on a MODEL-INVOKED research skill.

The half of the trigger that `user-prompt-submit.py` cannot see. When Claude invokes a
skill itself, the call arrives here as `tool_name: "Skill"` with
`tool_input: {"skill": "prp-core:prp-prd"}` and no new prompt, so `UserPromptSubmit` never
fires. Both paths are real, so both hooks exist and both render the SAME text from
`scripts/research_directive.py`, which documents both probed payloads.

Note `tool_input["skill"]` carries the PLUGIN-QUALIFIED name, which is why
`research_skill_match` makes the `<plugin>:` prefix optional.

THREE HARD CONSTRAINTS:

1. NEVER exit non-zero. Exit code 2 on this event BLOCKS THE TOOL CALL. Every path ends at
   exit 0.
2. NEVER print anything but the JSON envelope. Stray stdout here is not injected as
   context — it breaks the JSON parse, so the additionalContext that was built silently
   fails to attach.
3. STAY FAST, and NEVER emit `permissionDecision`. This hook injects; it never allows,
   denies or asks. It reads no corpus files — the directive is a static string and the
   config is one small file.

It is registered in its OWN `matcher: "Skill"` group. In the catch-all group it would
spawn a process on every tool call in the session.

Emits NOTHING (no stdout at all) when the tool is not `Skill`, the skill is not a research
workflow, or the directive is disabled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))                       # _shared
sys.path.insert(0, str(KDIR / "scripts"))           # config, research_directive

from _shared.hookio import read_hook_input, recursion_guard

recursion_guard()

from config import load_cfg
from research_directive import directive, research_enabled


def build_context(tool_name: str, tool_input: dict) -> str:
    """The directive when a research skill is being invoked, else ""."""
    if tool_name != "Skill":
        return ""
    skill = tool_input.get("skill", "")
    if not isinstance(skill, str) or not skill:
        return ""
    if not research_enabled(load_cfg(), "research_skill_match", skill):
        return ""
    return directive(KDIR)


def main() -> None:
    try:
        hook_input = read_hook_input()
        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})
        if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
            return
        context = build_context(tool_name, tool_input)
        if not context:
            return  # not a research skill -> emit nothing at all
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            }
        }))
    except Exception:  # noqa: BLE001 — fail open; a non-zero exit would block the tool call
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
