"""In-repo write-guard for knowledge/docs outputs (pure stdlib).

Hard product constraint: knowledge bases and docs are ALWAYS written inside the
repository and NEVER under ``.claude/``. This module enforces that for the
knowledge-compiler (knowledge/) and claudemd-lerner (CLAUDE.md, docs/) write
paths.

It does NOT govern a skill's own runtime state/config, which legitimately lives
under ``<repo>/.claude/<engine>/`` — call this only for knowledge/doc targets.
"""

from __future__ import annotations

from pathlib import Path


class WriteGuardError(Exception):
    """A knowledge/doc write target is outside the repo or under .claude/."""


def _resolve(p: Path | str) -> Path:
    # resolve() collapses ``..`` so traversal escapes are caught by the checks.
    return Path(p).resolve()


def assert_in_repo_not_dotclaude(target_path: Path | str, repo_root: Path | str) -> Path:
    """Validate a knowledge/doc write target. Return the resolved path or raise.

    Rejects when the target, after resolving ``..``:
      - is not inside ``repo_root``, or
      - is at or under ``<repo_root>/.claude/``.
    """
    root = _resolve(repo_root)
    target = _resolve(target_path)

    if not target.is_relative_to(root):
        raise WriteGuardError(f"target {target} is outside repo root {root}")

    dotclaude = root / ".claude"
    if target == dotclaude or target.is_relative_to(dotclaude):
        raise WriteGuardError(
            f"knowledge/docs must never be written under .claude/: {target}"
        )
    return target


def safe_join(repo_root: Path | str, *parts: str) -> Path:
    """Join ``parts`` onto ``repo_root`` and validate the result is a safe target."""
    candidate = Path(repo_root, *parts)
    return assert_in_repo_not_dotclaude(candidate, repo_root)
