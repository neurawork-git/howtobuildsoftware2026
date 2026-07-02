"""Recon base helpers for skill installers (pure stdlib).

A skill's recon.py runs read-only at install time, prints a human-readable
summary, then emits a machine-parsable JSON blob delimited by ``RECON_JSON``
markers on its own segment. The install skill greps that blob to drive its
AskUserQuestion prompts.

Pattern mirrored from coding-suite's continuous-learner recon.py
(the ``RECON_JSON`` delimiter contract).
"""

from __future__ import annotations

import json
import subprocess

RECON_DELIMITER = "RECON_JSON"


def git_root_or_none(start: str | None = None) -> str | None:
    """Absolute repo top-level as a string, or None if not a git repo.

    Callers should print ``NOT_A_GIT_REPO`` and exit when this returns None.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start or ".",
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def emit_recon_json(info: dict) -> None:
    """Print the machine-parsable recon blob: ``RECON_JSON{...}RECON_JSON``."""
    print(f"{RECON_DELIMITER}{json.dumps(info)}{RECON_DELIMITER}")


def parse_recon_json(stdout: str) -> dict | None:
    """Extract and parse the recon blob from captured stdout, or None.

    Used by tests and (optionally) by an installer reading a recon subprocess.
    """
    start = stdout.find(RECON_DELIMITER)
    if start == -1:
        return None
    start += len(RECON_DELIMITER)
    end = stdout.find(RECON_DELIMITER, start)
    if end == -1:
        return None
    try:
        return json.loads(stdout[start:end])
    except json.JSONDecodeError:
        return None
