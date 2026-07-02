"""Worktree-aware git context helper (pure stdlib, never raises).

Lets a session running inside a git WORKTREE redirect its captured output into
the MAIN checkout instead of the worktree's gitignored dirs (which die on
`git worktree remove`).

Detection contract: a linked worktree has a per-worktree git dir
(`git rev-parse --git-dir`) that differs from the shared common git dir
(`git rev-parse --git-common-dir`). In the main checkout both resolve to the
same `.git`. Both values may be RELATIVE to cwd, so always resolve() before
comparing. Every function degrades to the safe non-worktree answer on any error
— a hook must NEVER crash the session.

Ported clean (own implementation, same contract) from coding-suite's
engines/continuous-learner/git_context.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(args: list[str], start: str | None = None) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=start or ".",
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
        )
        if out.returncode != 0:
            return None
        val = out.stdout.strip()
        return val or None
    except (OSError, subprocess.SubprocessError):
        return None


def _resolved(args: list[str], start: str | None = None) -> Path | None:
    val = _git(args, start)
    if not val:
        return None
    try:
        # Relative git-dir / git-common-dir are relative to cwd (start or ".").
        base = Path(start) if start else Path.cwd()
        p = Path(val)
        return (p if p.is_absolute() else (base / p)).resolve()
    except OSError:
        return None


def repo_root(start: str | None = None) -> Path | None:
    """Absolute path of the working tree top-level, or None if not a git repo."""
    return _resolved(["rev-parse", "--show-toplevel"], start)


def in_worktree(start: str | None = None) -> bool:
    """True iff cwd is inside a LINKED git worktree (not the main checkout).

    Safe default: False on any error (treat as main checkout -> no redirect).
    """
    git_dir = _resolved(["rev-parse", "--git-dir"], start)
    common = _resolved(["rev-parse", "--git-common-dir"], start)
    if git_dir is None or common is None:
        return False
    return git_dir != common


def main_checkout_root(start: str | None = None) -> Path | None:
    """Absolute path of the MAIN checkout's working tree, or None.

    Derived from --git-common-dir: for a normal repo/worktree the common dir is
    `<main-root>/.git`, so the main root is its parent. Returns None for bare or
    otherwise unexpected layouts (caller falls back to the local dir).
    """
    common = _resolved(["rev-parse", "--git-common-dir"], start)
    if common is None:
        return None
    if common.name == ".git":
        return common.parent
    return None


def state_home(local_dir: Path, start: str | None = None) -> Path:
    """Where a per-session OUTPUT dir should live so it survives worktree removal.

    If inside a worktree AND the main root resolves, map ``local_dir`` (which
    lives under the worktree root) to the same relative path under the main root.
    Otherwise return ``local_dir`` unchanged. Never raises.
    """
    try:
        if not in_worktree(start):
            return local_dir
        main_root = main_checkout_root(start)
        wt_root = _resolved(["rev-parse", "--show-toplevel"], start)
        if main_root is None or wt_root is None:
            return local_dir
        rel = Path(local_dir).resolve().relative_to(wt_root)
        return main_root / rel
    except (OSError, ValueError):
        return local_dir
