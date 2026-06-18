"""Idempotent merge of hooks into a repo's .claude/settings.json (pure stdlib).

Used by skill installers to register their SessionEnd/SessionStart/PreCompact
hooks WITHOUT clobbering existing hooks or unrelated keys. Re-running an install
is a no-op (idempotent). A hook is recognized as "ours" when its command string
contains the given marker.

Ported clean from coding-suite's continuous-learner install.merge_settings,
generalized to take a hooks list and an explicit per-hook timeout.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class SettingsError(Exception):
    """Raised when an existing settings.json cannot be parsed (left untouched)."""


def merge_hooks(repo_root: Path | str, hooks: list[tuple[str, str, int, str]]) -> bool:
    """Merge ``hooks`` into ``<repo_root>/.claude/settings.json``.

    Each hook is ``(event, command, timeout, marker)``. Returns True if the file
    was changed, False if every hook was already present (idempotent no-op).

    - Creates ``.claude/settings.json`` (and the dir) if absent.
    - For each hook: if a hook whose command contains ``marker`` already exists
      under ``event``, update only its command if it drifted (keeps hand-edited
      timeout/type); otherwise append a new entry, reusing a ``matcher == ""``
      group if one exists, else creating one.
    - Writes atomically (tmp + os.replace).

    Raises SettingsError if an existing settings.json is invalid JSON.
    """
    root = Path(repo_root)
    settings_path = root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SettingsError(
                f"{settings_path} is not valid JSON — not touched"
            ) from e
        if not isinstance(loaded, dict):
            raise SettingsError(f"{settings_path} top level is not an object — not touched")
        data = loaded

    hooks_obj = data.setdefault("hooks", {})
    changed = False

    for event, command, timeout, marker in hooks:
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
        target = next((g for g in groups if g.get("matcher", "") == ""), None)
        if target is None:
            groups.append({"matcher": "", "hooks": [entry]})
        else:
            target.setdefault("hooks", []).append(entry)
        changed = True

    if changed:
        tmp = settings_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, settings_path)
    return changed
