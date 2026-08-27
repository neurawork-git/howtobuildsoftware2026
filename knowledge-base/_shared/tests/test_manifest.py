"""Guard: the plugin manifest and hooks.json keep the shape the loader requires."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"


class TestManifest(unittest.TestCase):
    def test_valid_json_with_semver_version(self) -> None:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "neurawork-cc-harness")
        self.assertRegex(data["version"], r"^\d+\.\d+\.\d+$")


class TestHooksJson(unittest.TestCase):
    """The loader rejects a hooks.json whose events sit at the top level.

    It requires ``{"hooks": {<Event>: [...]}}``; a bare ``{<Event>: [...]}`` fails
    with `expected record, received undefined` at path ["hooks"] and the plugin's
    hooks silently never run.
    """

    def test_events_are_nested_under_a_hooks_key(self) -> None:
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        self.assertIn("hooks", data, "hook events must be nested under a 'hooks' key")
        self.assertIsInstance(data["hooks"], dict)
        self.assertNotIn(
            "SessionStart", data, "hook events must not sit at the top level"
        )

    def test_every_hook_entry_is_a_command_with_a_timeout(self) -> None:
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        for event, groups in data["hooks"].items():
            self.assertIsInstance(groups, list, event)
            for group in groups:
                for hook in group["hooks"]:
                    with self.subTest(event=event, command=hook.get("command")):
                        self.assertEqual(hook["type"], "command")
                        self.assertIn("${CLAUDE_PLUGIN_ROOT}", hook["command"])
                        self.assertIsInstance(hook["timeout"], int)


if __name__ == "__main__":
    unittest.main()
