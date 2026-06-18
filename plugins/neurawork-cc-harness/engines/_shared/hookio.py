"""Hook stdin parsing + recursion guard (pure stdlib, never raises on input).

Claude Code invokes hooks with a JSON payload on stdin (session_id,
transcript_path, cwd, reason/source, ...). These helpers parse that payload
safely and prevent infinite recursion when a hook spawns `claude -p`, which
would fire the same hooks again.

Patterns mirrored from coding-suite's continuous-learner hooks
(recursion guard + Windows-safe stdin parse).
"""

from __future__ import annotations

import json
import os
import re
import sys

# Set by spawners (see child_env) so a nested headless session bails out of hooks.
INVOKED_BY_VALUE = "neurawork_cc_harness"


def recursion_guard() -> None:
    """Exit 0 immediately if we were (transitively) spawned by our own compiler.

    Call this at the very top of a hook entrypoint, before heavy imports/work.
    """
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)


def read_hook_input() -> dict:
    """Read and parse the hook JSON from stdin. Returns {} on any failure.

    Windows may send unescaped backslashes in paths, which breaks a strict
    json.loads; retry once with backslashes doubled before giving up.
    """
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError, EOFError):
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            fixed = re.sub(r'(?<!\\)\\(?!["\\])', r"\\\\", raw)
            data = json.loads(fixed)
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def child_env() -> dict:
    """Environment for a spawned `claude -p` child: marks it to skip our hooks."""
    return {**os.environ, "CLAUDE_INVOKED_BY": INVOKED_BY_VALUE}
