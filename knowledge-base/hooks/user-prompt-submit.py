"""UserPromptSubmit hook — inject the kb-researcher directive on a TYPED research command.

The half of the trigger that `pre-skill.py` cannot see. A slash command the user types is
expanded into the prompt, never routed as a `Skill` tool call, so `PreToolUse` never fires
for it. The other half lives in `pre-skill.py` and renders the SAME text from
`scripts/research_directive.py`, which documents both probed payloads.

THREE HARD CONSTRAINTS:

1. NEVER exit non-zero. A non-zero exit on this event blocks prompt processing and erases
   the user's prompt. Every path ends at exit 0.
2. NEVER print anything but the JSON envelope. Stray stdout is injected as model-visible
   context on this event, so a debug line becomes context.
3. STAY FAST. This event has no matcher support — it fires on EVERY prompt in the repo.
   This hook reads no corpus files: the directive is a static string and the config is one
   small file.

Emits NOTHING (no stdout at all) when the prompt does not start a research workflow or the
directive is disabled.
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


def build_context(prompt: str) -> str:
    """The directive when the prompt STARTS a research workflow, else ""."""
    if not research_enabled(load_cfg(), "research_prompt_match", prompt):
        return ""
    return directive(KDIR)


def main() -> None:
    try:
        prompt = read_hook_input().get("prompt", "")
        if not isinstance(prompt, str):
            return
        context = build_context(prompt)
        if not context:
            return  # not a research workflow -> emit nothing at all
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }))
    except Exception:  # noqa: BLE001 — fail open; a non-zero exit would erase the prompt
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
