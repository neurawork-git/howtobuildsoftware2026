"""Wire prp-core's artifact store into a repo (pure stdlib).

prp-core resolves its store as ``${PRP_HOME:-$HOME/.prp}/<slug>-<hash8>``, where the
key is derived from ``git rev-parse --git-common-dir`` and is therefore identical in
the main checkout and in every linked worktree. Only the *prefix* differs: a relative
``PRP_HOME`` written into ``.claude/settings.json`` is resolved by the shell against
the session's working directory, so a worktree session gets its own physical store.

Linking ``~/.prp/<slug>-<hash8>`` at the main checkout's ``.claude/PRPs`` moves that
decision out of cwd resolution and into the filesystem: one store per repo, reached
by the same absolute path from anywhere. ``set_env_default(root, "PRP_HOME", ...)``
stays the fallback for platforms that cannot symlink and for an occupied target.

Mirrors ``settings.set_env_default``'s status-tuple contract: never overwrite what
someone else owns, report what is there, and let the caller decide the severity.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import gitctx
from .settings import set_env_default

# The store's location inside the repo. prp-core's own layout — `plans/ prds/
# reports/ specs/` live directly below it.
STORE_SUBPATH = ".claude/PRPs"

# The fallback wiring: a *relative* PRP_HOME in .claude/settings.json. Relative on
# purpose — Claude Code does not expand ``${CLAUDE_PROJECT_DIR}`` inside a settings
# ``env`` value, and an absolute path would have to live in the gitignored
# settings.local.json, which ``git worktree add`` does not materialise. It leaves the
# store one ``<slug>-<hash8>`` segment deeper and one physical store per checkout,
# which is why it is the fallback and not the wiring of choice.
PRP_HOME_VALUE = STORE_SUBPATH


def _slug(name: str) -> str:
    """``basename | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-'``, trimmed.

    ``tr -s`` squeezes runs, so consecutive non-alphanumerics collapse to one ``-``.
    """
    out: list[str] = []
    for ch in name.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "project"


def key_for_root(root: Path | str) -> str:
    """prp-core's ``<slug>-<hash8>`` key for an already-resolved main-checkout path.

    ``hash8`` is git's blob object id of that path with **no** trailing newline, i.e.
    exactly ``printf %s "$path" | git hash-object --stdin``. Computed from ``hashlib``
    rather than a subprocess, so a caller that already knows the main checkout — the
    doctor reads it from the worktree's ``.git`` file — needs no git process at all.
    """
    root = Path(root)
    path = str(root).encode("utf-8")
    blob = b"blob %d\0" % len(path) + path
    return f"{_slug(root.name)}-{hashlib.sha1(blob).hexdigest()[:8]}"


def store_key(repo_root: Path | str) -> str:
    """``key_for_root`` for the main checkout behind ``repo_root``.

    The path hashed is the main checkout's, so the key is worktree-invariant — the
    same property prp-core gets from ``--git-common-dir``.
    """
    return key_for_root(main_checkout(repo_root))


def default_prp_home() -> Path:
    """``$PRP_HOME`` when it is ABSOLUTE, else ``~/.prp``.

    prp-core's prefix rule is ``"${PRP_HOME:-$HOME/.prp}"``, so the link belongs where
    the resolver will actually look. Only an absolute value names one place, though: a
    *relative* ``PRP_HOME`` — exactly what every pre-0.8 install wrote into
    ``.claude/settings.json``, and what Claude Code then exports into the session — is
    resolved against whatever directory the process stands in. Honouring it here would
    put the link under the repo's own ``.claude/PRPs`` on the ordinary upgrade path,
    pointing at its own parent, and no shared store would ever be created. The relative
    case is precisely the wiring this module replaces, so it falls through to ``~/.prp``.
    """
    env = os.environ.get("PRP_HOME")
    if env:
        home = Path(env).expanduser()
        if home.is_absolute():
            return home
    return Path.home() / ".prp"


def main_checkout(repo_root: Path | str) -> Path:
    """The main checkout's root, resolved. Falls back to ``repo_root`` itself.

    Installing from a worktree must wire the *main* checkout, or the link would
    point at a directory ``git worktree remove`` can delete.
    """
    root = Path(repo_root).resolve()
    main = gitctx.main_checkout_root(str(root))
    return main.resolve() if main is not None else root


def link_path(main_root: Path | str, prp_home: Path | str | None = None) -> Path:
    """Where the link lives, for an ALREADY-resolved main checkout.

    One place composes prefix and key, so an installer's message, the link it writes
    and the doctor's report can never name three different paths. Taking the main root
    rather than any path inside the repo keeps this free of a git call, which is what
    the doctor needs.
    """
    home = Path(prp_home) if prp_home is not None else default_prp_home()
    return home / key_for_root(main_root)


def store_link(repo_root: Path | str, prp_home: Path | str | None = None) -> Path:
    """``link_path`` for any path inside the repo — resolves the main checkout first."""
    return link_path(main_checkout(repo_root), prp_home)


def link_prp_store(
    repo_root: Path | str, prp_home: Path | str | None = None
) -> tuple[str, str | None]:
    """Point ``<prp_home>/<store_key>`` at the repo's ``.claude/PRPs``.

    Returns ``(status, path)`` where status is:

    - ``"linked"``      — the symlink was created; ``path`` is its target
    - ``"already"``     — a symlink already resolved to that target; nothing written
    - ``"conflict"``    — the key is taken by a real directory or a symlink pointing
      elsewhere; ``path`` is what is there. Never replaced: a real directory holds
      another store's artifacts, which an installer cannot attribute.
    - ``"unsupported"`` — the platform refused the symlink (Windows without Developer
      Mode); ``path`` is the error text. Not a failure — the caller falls back to
      ``PRP_HOME``.

    Creates the in-repo store directory first, so a created link never dangles.
    """
    target = main_checkout(repo_root) / STORE_SUBPATH
    link = store_link(repo_root, prp_home)
    home = link.parent

    try:
        target.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            current = Path(link).resolve()
            if current == target.resolve():
                return "already", str(target)
            return "conflict", str(current)
        if link.exists():
            return "conflict", str(link)
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as e:
        return "unsupported", str(e)
    return "linked", str(target)


def _settings_prp_home(repo_root: Path | str) -> str | None:
    """``env.PRP_HOME`` from the repo's settings, or None. Never raises.

    Read-only and tolerant on purpose: an unreadable or invalid settings.json is the
    hook merge's problem to report, not a reason for the store wiring to fail.
    """
    path = Path(repo_root) / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    env = data.get("env") if isinstance(data, dict) else None
    value = env.get("PRP_HOME") if isinstance(env, dict) else None
    return str(value) if value is not None else None


def wire_store(
    repo_root: Path | str, prp_home: Path | str | None = None
) -> tuple[str, list[str]]:
    """Wire the repo's store the best way this machine allows, and say what happened.

    Symlink first; on an occupied target or a platform that cannot symlink, fall back
    to the relative ``PRP_HOME`` both gates still read (the store layout it produces
    is accepted by ``is_plan_path`` and by ``document_kind``). Returns
    ``(status, lines)`` — the status the caller may act on, and the lines it prints.

    One implementation for both installers: the wiring decision has one owner, the
    same way ``set_env_default`` owns the settings write.

    Raises ``SettingsError``/``OSError`` only from the fallback write, which the
    caller already treats as a failed install.
    """
    status, path = link_prp_store(repo_root, prp_home)
    link = store_link(repo_root, prp_home)
    if status in ("linked", "already"):
        verb = "linked" if status == "linked" else "already linked"
        wired = (
            f"PRP store {verb}: {link} -> {path} — PRDs and plans land inside the repo,"
            " where the gates see them, from the main checkout and from every worktree"
        )
        lines = [wired]
        # An upgrade leaves the older wiring in place, and it WINS over the link, so the
        # line above would otherwise claim a shared store the repo does not have.
        existing = _settings_prp_home(repo_root)
        if existing is not None:
            lines.append(
                f"env.PRP_HOME={existing!r} is still set in .claude/settings.json and takes "
                "precedence — the link stays inert until that key is removed"
            )
        return status, lines

    why = (f"{path} is not a link to this repo's store"
           if status == "conflict" else f"this platform cannot symlink ({path})")
    lines = [f"PRP store not linked — {why}; falling back to PRP_HOME"]

    env_status, current = set_env_default(repo_root, "PRP_HOME", PRP_HOME_VALUE)
    if env_status == "wrote":
        lines.append(f"PRP_HOME set to {PRP_HOME_VALUE} in .claude/settings.json "
                     "— documents land inside the repo, in a per-checkout store")
    elif env_status == "already":
        lines.append(f"PRP_HOME already {PRP_HOME_VALUE} in .claude/settings.json")
    else:
        lines.append(f"PRP_HOME left at {current!r} (not {PRP_HOME_VALUE}) — documents may "
                     "land outside the repo, where no gate ever sees them")
    return "fallback", lines
