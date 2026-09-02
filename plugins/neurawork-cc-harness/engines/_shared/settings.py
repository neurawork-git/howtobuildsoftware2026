"""Idempotent merges into a repo's local config files (pure stdlib).

Used by skill installers to register their SessionEnd/SessionStart/PreCompact
hooks in .claude/settings.json WITHOUT clobbering existing hooks or unrelated keys,
and to merge their ignore rules into an install dir's .gitignore. Re-running an
install is a no-op (idempotent). A hook is recognized as "ours" when its command
string contains the given marker.

Ported clean from a prior continuous-learner install.merge_settings,
generalized to take a hooks list and an explicit per-hook timeout.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
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
    # Sequence, not list: list is invariant, so an installer whose _hooks() returns a
    # uniform list of 5-tuples would not type-check against a list of the union.
    hooks: Sequence[tuple[str, str, int, str] | tuple[str, str, int, str, str]],
) -> bool:
    """Merge ``hooks`` into ``<repo_root>/.claude/settings.json``.

    Each hook is ``(event, command, timeout, marker)`` or
    ``(event, command, timeout, marker, matcher)``; the 4-tuple form means
    ``matcher == ""``. Returns True if the file was changed, False if every hook
    was already present (idempotent no-op).

    - Creates ``.claude/settings.json`` (and the dir) if absent.
    - For each hook: if a hook whose command contains ``marker`` already exists
      under ``event`` — in ANY matcher group — update only its command if it
      drifted (keeps its type), RAISE its timeout to the shipped value when it sits
      below it (a hand-edited HIGHER value is kept), and MOVE it into the requested
      matcher's group when it sits under a different one, dropping the group it
      leaves behind once empty; otherwise append a new entry, reusing the group
      whose ``matcher`` equals the requested one if it exists, else creating it.
      The matcher is not hand-editable state: the engine owns which tools its hook
      must see, so an install that predates a narrowing is narrowed on re-run.
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
        existing, source = None, None
        for group in groups:
            for candidate in group.get("hooks", []):
                if marker in str(candidate.get("command", "")):
                    existing, source = candidate, group
                    break
            if existing is not None:
                break
        if existing is not None and source is not None:
            # Migration: replace a stale command in place; keep timeout/type.
            if existing.get("command") != command:
                existing["command"] = command
                changed = True
            # Migration: the shipped timeout is a FLOOR, not a default. A value below it
            # is not a preference — it is an install made before the engine knew what its
            # own cold start costs, and it kills the hook mid-bootstrap. Raise it; a
            # higher hand-edited value is still that user's choice and is left alone.
            current_timeout = existing.get("timeout")
            if not isinstance(current_timeout, int) or current_timeout < timeout:
                existing["timeout"] = timeout
                changed = True
            # Migration: an install made before this hook carried a matcher registered it
            # under the wrong one. MOVE the entry — leaving it where it is would keep the
            # wider registration firing forever, which is the defect the matcher fixes,
            # and appending a second one would run the hook twice.
            if source.get("matcher", "") != matcher:
                source["hooks"].remove(existing)
                if not source["hooks"]:
                    groups.remove(source)
                target = next((g for g in groups if g.get("matcher", "") == matcher), None)
                if target is None:
                    groups.append({"matcher": matcher, "hooks": [existing]})
                else:
                    target.setdefault("hooks", []).append(existing)
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


def merge_gitignore(target: Path | str, content: str) -> bool:
    """Merge the shipped ignore rules in ``content`` into ``<target>/.gitignore``.

    Returns True when the file was written, False when every shipped rule was
    already there (idempotent no-op). Same contract as merge_hooks.

    Append-only, by design. A create-if-absent write reaches fresh installs only, so
    a rule added in a later release never lands in a repo that already installed the
    engine; a wholesale rewrite would reach them and destroy the user's own rules.
    Appending exactly the missing lines does both: nothing existing is reordered,
    rewritten, or removed.

    A rule counts as present when some existing line matches it after stripping
    surrounding whitespace. Comments and blank lines are carried along with the rule
    directly below them when that rule is missing, so an appended group keeps the
    heading that explains it and a fully-covered group adds nothing.
    """
    path = Path(target) / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    present = {line.strip() for line in existing.splitlines() if line.strip()}

    missing: list[str] = []
    pending: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            pending.append(line)
            continue
        if stripped in present:
            pending = []
            continue
        missing.extend(pending)
        pending = []
        missing.append(line)
        present.add(stripped)
    if not missing:
        return False

    prefix = existing
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / ".gitignore.tmp"
    tmp.write_text(prefix + "\n".join(missing) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return True


def prune_gitignore(target: Path | str, rules: Sequence[str]) -> bool:
    """Remove ``rules`` from ``<target>/.gitignore`` if they are there.

    Returns True when the file was written, False when no named rule was present
    (idempotent no-op) or the file does not exist. Same contract as merge_gitignore.

    The counterpart merge_gitignore needs: that merge is append-only, so dropping a
    rule from a shipped body reaches fresh installs only — every repo that already
    installed keeps the line forever. A line matches when its stripped form equals a
    named rule; every other line, including comments, blanks and the user's own
    rules, is left byte-identical in place.
    """
    path = Path(target) / ".gitignore"
    if not path.exists():
        return False
    existing = path.read_text(encoding="utf-8")
    drop = set(rules)
    kept = [line for line in existing.splitlines() if line.strip() not in drop]
    if len(kept) == len(existing.splitlines()):
        return False
    tmp = path.parent / ".gitignore.tmp"
    tmp.write_text("\n".join(kept) + "\n" if kept else "", encoding="utf-8")
    os.replace(tmp, path)
    return True
