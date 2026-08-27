"""Guard: the plugin manifest and hooks.json keep the shape the loader requires."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"
CHANGELOG = PLUGIN_ROOT / "CHANGELOG.md"


class TestManifest(unittest.TestCase):
    def manifest(self) -> dict:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_valid_json_with_semver_version(self) -> None:
        data = self.manifest()
        self.assertEqual(data["name"], "neurawork-cc-harness")
        self.assertRegex(data["version"], r"^\d+\.\d+\.\d+$")

    def test_the_plugin_is_traceable_from_the_manifest_alone(self) -> None:
        # A marketplace reader has the manifest and nothing else; without these there is
        # no route from an installed copy back to the source or the install guide.
        data = self.manifest()
        for key in ("homepage", "repository"):
            with self.subTest(key=key):
                self.assertTrue(
                    str(data.get(key, "")).startswith("https://"),
                    f"{key} must be an absolute URL",
                )
        keywords = data.get("keywords") or []
        self.assertIsInstance(data.get("keywords"), list)
        self.assertTrue(keywords, "an empty keywords list makes the plugin unsearchable")
        for keyword in keywords:
            with self.subTest(keyword=keyword):
                self.assertIsInstance(keyword, str)
                self.assertTrue(keyword.strip())

    def test_the_changelog_covers_the_shipped_version(self) -> None:
        # The bump-discipline guard: the version is the ONLY signal an installed copy has
        # that a newer one exists, so a release has to say what it contains. Deterministic
        # and offline — a git-diff "bump required" check needs a base ref, which a shallow
        # clone does not have and a merge commit reports falsely.
        version = self.manifest()["version"]
        self.assertTrue(CHANGELOG.is_file(), "CHANGELOG.md is missing from the plugin root")
        self.assertIn(
            f"## [{version}]",
            CHANGELOG.read_text(encoding="utf-8"),
            f"plugin.json is {version} but CHANGELOG.md has no section for it — an "
            "entry-less release tells an upgrading user nothing about what changed",
        )


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
