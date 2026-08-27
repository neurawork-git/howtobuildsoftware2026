#!/usr/bin/env python3
"""Plugin-level SessionStart staleness nudge.

Runs FROM the plugin (so it has CLAUDE_PLUGIN_ROOT — the installed engine copies
inside a target repo do NOT, which is why this check cannot live in them). For each
harness engine installed in the current repo, it compares the installed VERSION
(stamped into <repo>/<dir>/VERSION at install time) against the plugin's currently
shipped VERSION (<plugin>/engines/<engine>/VERSION). When an install is behind, it
prints a SessionStart additionalContext note telling the user to re-run the
installer (ADOPT) to propagate the upgrade.

The engine registry and the discovery/comparison primitives live in
``scripts/harness_probe.py`` — one map read by this nudge and by ``scripts/doctor.py``.
A second copy is what let this hook's own list fall a whole engine behind reality.

Stdlib-only, runs under system python3 (no uv). Silent no-op when nothing is stale
or when the repo has no harness install. Never raises — a hook crash must not break
session start, so even the probe import degrades to a silent no-op.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# File-relative, NOT CLAUDE_PLUGIN_ROOT: the probe is the module sitting next to this
# hook, so it is found from __file__ even when the env var is absent or points elsewhere.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    # The three re-exports are this module's public surface: engines/_shared/tests/
    # test_version_check.py calls them here, and its passing unmodified is the proof
    # that lifting them into the probe changed no behaviour.
    from harness_probe import (
        find_stale,
        installed_dir_for,
        is_behind,
        read_version,
    )
except Exception:  # noqa: BLE001 — a missing probe must not break session start
    find_stale = installed_dir_for = is_behind = read_version = None  # type: ignore[assignment]


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
        if not project_dir or find_stale is None:
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
