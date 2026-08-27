"""The kb-researcher spawn directive, shared by the two hooks that can trigger it.

WHY TWO HOOKS SHARE THIS MODULE: a research skill is entered by two paths, and no single
hook event sees both (probed on Claude Code 2.1.234, 2026-08-18):

    user types `/prp-prd …`   -> UserPromptSubmit, `prompt` = the RAW slash text.
                                 PreToolUse/Skill NEVER fires: a typed slash command is
                                 expanded into the prompt, not routed as a tool call.
    model invokes the skill   -> PreToolUse, tool_name "Skill",
                                 tool_input {"skill": "<plugin>:<name>"}.
                                 No new prompt, so UserPromptSubmit never fires.

Both paths occur in practice, so both hooks exist and both render the SAME text from
here. Duplicating the wording instead would let the two drift — and the two halves
disagreeing about which workflow counts as research is exactly the bug that produced
the `$`-not-`\\b` note below.

Pure stdlib, no file I/O, never raises.
"""

from __future__ import annotations

import re
from pathlib import Path

# ── The research workflows that must consult the knowledge base ────────────────
# Two patterns, not one, because the two hooks see two different surfaces.
#
# `research_skill_match` is matched against `tool_input["skill"]`, which carries the
# PLUGIN-QUALIFIED name (`prp-core:prp-prd`) — hence the optional prefix. Anchored at
# both ends so it rejects `prp-core:prp-prd-update`, a real prp-core skill.
DEFAULT_SKILL_MATCH = r"^([\w-]+:)?prp-(plan|prd|debug)$"
# `research_prompt_match` is matched against the raw prompt and anchored at its start,
# so a mid-sentence "like /prp-prd does" is discussion, not an invocation.
#
# NOT `\b` at the end: `-` is a word boundary, so `\b` matches `/prp-prd-update` and
# `/prp-plan-b` too. The skill half is anchored with `$` and rejects those, so a `\b`
# here would make the two halves disagree about the same workflow.
DEFAULT_PROMPT_MATCH = r"^\s*/(?:[\w-]+:)?prp-(plan|prd|debug)(?![\w-])"

DEFAULT_MATCH = {
    "research_skill_match": DEFAULT_SKILL_MATCH,
    "research_prompt_match": DEFAULT_PROMPT_MATCH,
}

# The directive is kept SHORT on purpose. A large `additionalContext` payload is
# offloaded to a short preview instead of being inlined, which would silently truncate
# it. That threshold was measured in a sibling repo's engine, not in this one — treat
# the ceiling as a cheap precaution rather than a proven limit.
MAX_DIRECTIVE_CHARS = 900


def directive(kdir: Path | str) -> str:
    """The spawn directive for the resolved knowledge dir `kdir`.

    Every line earns its place:
      - it names the agent EXACTLY as the Agent tool needs it (plugin-qualified),
        because a name the model cannot use verbatim is one it will approximate — and
        another enabled plugin may export a bare `kb-researcher` written for a
        different corpus schema;
      - it names the three prp-core agents so the model places this one AMONG them
        rather than substituting it for one;
      - "SAME message" is what makes the four run concurrently instead of serially;
      - it passes the resolved absolute knowledge dir so the agent never globs for it;
      - it states the traversal contract, because `connections/` articles in this
        corpus are reachable by backlink and by nothing else.
    """
    return (
        "## Knowledge-base research is required for this workflow\n"
        "\n"
        "Spawn `neurawork-cc-harness:kb-researcher` as part of this run — it is the "
        "FOURTH research axis next to `prp-core:codebase-explorer` (where code lives), "
        "`prp-core:codebase-analyst` (how it behaves) and `prp-core:web-researcher` "
        "(what external sources say). It searches this repo's compiled knowledge base: "
        "prior findings, decisions and gotchas that exist nowhere else.\n"
        "\n"
        f"- Knowledge dir: `{kdir}` — pass it verbatim; the agent must not glob for it.\n"
        "- Launch it in the SAME message as the other research agents so they run "
        "concurrently.\n"
        "- Its report must cite full article paths, and must walk BACKLINKS after the "
        "index — `connections/` articles are reachable no other way.\n"
    )


def research_enabled(cfg: dict, key: str, value: str) -> bool:
    """True when the directive is on and `value` matches the configured pattern `key`.

    `key` is one of `research_skill_match` / `research_prompt_match`. A pattern that is
    empty or does not compile falls back to this module's default rather than raising or
    matching everything — both callers are hooks, and a typo in a repo's config.json must
    degrade to default behaviour, in exactly one place.
    """
    fallback = DEFAULT_MATCH.get(key)
    if fallback is None:
        return False
    if not cfg.get("research_directive", True):
        return False
    if not isinstance(value, str) or not value:
        return False
    pattern = str(cfg.get(key) or "") or fallback
    try:
        return re.match(pattern, value) is not None
    except re.error:
        return re.match(fallback, value) is not None
