#!/usr/bin/env python3
"""Plugin-level SessionStart staleness nudge.

Runs FROM the plugin (so it has CLAUDE_PLUGIN_ROOT — the installed engine copies
inside a target repo do NOT, which is why this check cannot live in them). For each
harness engine installed in the current repo, it compares the installed VERSION
(stamped into <repo>/<dir>/VERSION at install time) against the plugin's currently
shipped VERSION (<plugin>/engines/<engine>/VERSION). When an install is behind, it
prints a SessionStart additionalContext note telling the user to re-run the
installer (ADOPT) to propagate the upgrade.

Stdlib-only, runs under system python3 (no uv). Silent no-op when nothing is stale
or when the repo has no harness install. Never raises — a hook crash must not break
session start.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

# engine name -> a unique substring of that engine's installed hook command in
# .claude/settings.json. Used to locate where each engine was installed (the dir
# is user-configurable, so we read it back from the command line rather than
# assuming the default dir name).
ENGINES = {
    "knowledge-compiler": "hooks/session-start.py",
    "claudemd-lerner": "hooks/cl-session-start.py",
    "compliance-compiler": "hooks/co-post-tooluse.py",
}

_DIR_RE = re.compile(r"\$CLAUDE_PROJECT_DIR/([^\"'\s]+)")


def installed_dir_for(settings: dict, marker: str) -> str | None:
    """Return the install dir segment for the hook command containing `marker`."""
    hooks_obj = settings.get("hooks")
    if not isinstance(hooks_obj, dict):
        return None
    for groups in hooks_obj.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            for hook in group.get("hooks", []):
                command = str(hook.get("command", ""))
                if marker in command:
                    m = _DIR_RE.search(command)
                    if m:
                        return m.group(1)
    return None


def read_version(path: Path) -> str | None:
    """Return the stripped VERSION file content, or None (never raises)."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def is_behind(installed: str, shipped: str) -> bool:
    """True if the installed version is older than the shipped version."""
    try:
        return int(installed) < int(shipped)
    except ValueError:
        return installed != shipped


def find_stale(repo_root: Path, plugin_root: Path, settings: dict) -> list[dict]:
    """List engines whose installed VERSION is behind the shipped VERSION."""
    stale = []
    for engine, marker in ENGINES.items():
        dirname = installed_dir_for(settings, marker)
        if not dirname:
            continue
        installed = read_version(repo_root / dirname / "VERSION")
        shipped = read_version(plugin_root / "engines" / engine / "VERSION")
        if installed is None or shipped is None:
            continue
        if is_behind(installed, shipped):
            stale.append({
                "engine": engine,
                "dir": dirname,
                "installed": installed,
                "shipped": shipped,
            })
    return stale


def _build_note(stale: list[dict]) -> str:
    lines = [
        "neurawork-cc-harness: an installed engine copy is behind the plugin. "
        + "Re-run the installer (ADOPT — non-destructive) to upgrade the in-repo code:",
    ]
    for s in stale:
        lines.append(
            f"- {s['engine']} in {s['dir']}/ is behind "
            f"(installed {s['installed']} < shipped {s['shipped']}) — "
            f"re-run /neurawork-cc-harness:{s['engine']}"
        )
    return "\n".join(lines)


def main() -> None:
    try:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        if not project_dir:
            return
        repo_root = Path(project_dir)
        plugin_root = Path(
            os.environ.get("CLAUDE_PLUGIN_ROOT")
            or Path(__file__).resolve().parent.parent
        )

        settings_path = repo_root / ".claude" / "settings.json"
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(settings, dict):
            return

        stale = find_stale(repo_root, plugin_root, settings)
        if not stale:
            return

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": _build_note(stale),
            }
        }))
    except Exception:  # noqa: BLE001 — a hook crash must never break session start
        return


if __name__ == "__main__":
    main()
