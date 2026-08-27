"""Idempotent merge of hooks into a repo's .claude/settings.json (pure stdlib).

Used by skill installers to register their SessionEnd/SessionStart/PreCompact
hooks WITHOUT clobbering existing hooks or unrelated keys. Re-running an install
is a no-op (idempotent). A hook is recognized as "ours" when its command string
contains the given marker.

Ported clean from a prior continuous-learner install.merge_settings,
generalized to take a hooks list and an explicit per-hook timeout.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class SettingsError(Exception):
    """Raised when an existing settings.json cannot be parsed (left untouched)."""


def _load(settings_path: Path) -> dict:
    """Parse an existing settings.json, or return {} when there is none."""
    if not settings_path.exists():
        return {}
    try:
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SettingsError(f"{settings_path} is not valid JSON — not touched") from e
    if not isinstance(loaded, dict):
        raise SettingsError(f"{settings_path} top level is not an object — not touched")
    return loaded


def set_env_default(
    repo_root: Path | str, key: str, value: str
) -> tuple[str, str | None]:
    """Set ``env[key] = value`` in ``<repo_root>/.claude/settings.json`` unless it is taken.

    Returns ``(status, current_value)`` where status is:

    - ``"wrote"``   — the key was absent and is now set (``current_value`` is ``value``)
    - ``"already"`` — the key already held exactly ``value``; nothing written
    - ``"conflict"``— the key holds a different value; nothing written, the caller decides
      what to say about it. Someone else owns that setting.

    Same contract as merge_hooks: creates the file/dir when absent, writes atomically
    (tmp + os.replace), never touches unrelated keys, raises SettingsError on invalid JSON.
    """
    root = Path(repo_root)
    settings_path = root / ".claude" / "settings.json"
    data = _load(settings_path)

    env = data.get("env")
    if env is not None and not isinstance(env, dict):
        raise SettingsError(f"{settings_path} has a non-object 'env' — not touched")
    current = (env or {}).get(key)
    if current == value:
        return "already", current
    if current is not None:
        return "conflict", current

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("env", {})[key] = value
    tmp = settings_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, settings_path)
    return "wrote", value


def merge_hooks(
    repo_root: Path | str,
    hooks: list[tuple[str, str, int, str] | tuple[str, str, int, str, str]],
) -> bool:
    """Merge ``hooks`` into ``<repo_root>/.claude/settings.json``.

    Each hook is ``(event, command, timeout, marker)`` or
    ``(event, command, timeout, marker, matcher)``; the 4-tuple form means
    ``matcher == ""``. Returns True if the file was changed, False if every hook
    was already present (idempotent no-op).

    - Creates ``.claude/settings.json`` (and the dir) if absent.
    - For each hook: if a hook whose command contains ``marker`` already exists
      under ``event`` — in ANY matcher group — update only its command if it
      drifted (keeps hand-edited timeout/type); otherwise append a new entry,
      reusing the group whose ``matcher`` equals the requested one if it exists,
      else creating that group.
    - Writes atomically (tmp + os.replace).

    Raises SettingsError if an existing settings.json is invalid JSON.
    """
    root = Path(repo_root)
    settings_path = root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    data = _load(settings_path)
    hooks_obj = data.setdefault("hooks", {})
    changed = False

    for hook in hooks:
        event, command, timeout, marker = hook[:4]
        matcher = hook[4] if len(hook) > 4 else ""
        groups = hooks_obj.setdefault(event, [])
        existing = next(
            (h for g in groups for h in g.get("hooks", []) if marker in str(h.get("command", ""))),
            None,
        )
        if existing is not None:
            # Migration: replace a stale command in place; keep timeout/type.
            if existing.get("command") != command:
                existing["command"] = command
                changed = True
            continue
        entry = {"type": "command", "command": command, "timeout": timeout}
        target = next((g for g in groups if g.get("matcher", "") == matcher), None)
        if target is None:
            groups.append({"matcher": matcher, "hooks": [entry]})
        else:
            target.setdefault("hooks", []).append(entry)
        changed = True

    if changed:
        tmp = settings_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, settings_path)
    return changed
