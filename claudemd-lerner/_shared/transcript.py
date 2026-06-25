"""Read a Claude Code JSONL session transcript into recent markdown turns.

The transcript is newline-delimited JSON; each line is an entry whose `message`
holds a `role` ("user"/"assistant") and `content` (a string OR a list of content
blocks). We keep only user/assistant text, the last ``max_turns`` of it,
truncated to ``max_chars``.

Ported clean from coding-suite's continuous-learner extract_conversation_context.
"""

from __future__ import annotations

import json
from pathlib import Path


def extract_turns(transcript_path: Path | str, max_turns: int = 30, max_chars: int = 15000) -> str:
    """Return the last ``max_turns`` user/assistant turns as markdown, or "".

    Missing/unreadable file -> "". Never raises.
    """
    turns: list[str] = []
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message", {})
                if isinstance(msg, dict):
                    role, content = msg.get("role", ""), msg.get("content", "")
                else:
                    role, content = entry.get("role", ""), entry.get("content", "")
                if role not in ("user", "assistant"):
                    continue
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            parts.append(block)
                    content = "\n".join(parts)
                if isinstance(content, str) and content.strip():
                    label = "User" if role == "user" else "Assistant"
                    turns.append(f"**{label}:** {content.strip()}\n")
    except OSError:
        return ""

    context = "\n".join(turns[-max_turns:])
    if len(context) > max_chars:
        context = context[-max_chars:]
        boundary = context.find("\n**")
        if boundary > 0:
            context = context[boundary + 1:]
    return context
