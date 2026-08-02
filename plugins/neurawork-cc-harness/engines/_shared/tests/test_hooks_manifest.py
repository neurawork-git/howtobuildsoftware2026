"""Guard: hooks/hooks.json keeps the shape Claude Code actually loads.

Why this exists: `test_manifest.py` guards `plugin.json` only. Nothing guarded
`hooks/hooks.json`, and a missing top-level `hooks` wrapper there does not fail
loudly in one component -- it makes Claude Code refuse the **entire plugin**:

    $ claude plugin validate plugins/neurawork-cc-harness
    hooks: Invalid input: expected record, received undefined
    $ claude plugin list
    Status: failed to load / Hook load failed

All seven skills are then unavailable, with no hint that a single JSON nesting
level is the cause. A one-line defect that costs the whole product deserves a
test, so it can only happen once.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOKS = PLUGIN_ROOT / "hooks" / "hooks.json"

#: Hook events Claude Code recognises. A typo in an event name is silent -- the hook
#: simply never fires -- so the allowlist is the only place it can be caught.
KNOWN_EVENTS = frozenset({
    "PreToolUse", "PostToolUse", "UserPromptSubmit", "Notification",
    "Stop", "SubagentStop", "PreCompact", "SessionStart", "SessionEnd",
})


class TestHooksManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(HOOKS.is_file(), f"{HOOKS} is missing")
        self.data = json.loads(HOOKS.read_text(encoding="utf-8"))

    def test_events_are_wrapped_in_a_hooks_object(self) -> None:
        """The regression guard: events must sit under a top-level "hooks" key.

        Listing them at the top level parses as JSON and reads fine to a human, which
        is exactly why it slipped through -- only the loader rejects it.
        """
        self.assertIsInstance(self.data, dict)
        self.assertIn(
            "hooks", self.data,
            'hooks.json must be {"hooks": {"<Event>": [...]}} -- events listed at the '
            "top level make Claude Code reject the whole plugin",
        )
        self.assertIsInstance(self.data["hooks"], dict)
        # Guards against the inverse mistake: a stray event left outside the wrapper.
        strays = KNOWN_EVENTS & set(self.data)
        self.assertFalse(strays, f"event(s) {sorted(strays)} sit outside the hooks wrapper")

    def test_event_names_are_known(self) -> None:
        for event in self.data["hooks"]:
            self.assertIn(event, KNOWN_EVENTS, f"unknown hook event {event!r}")

    def test_every_entry_declares_a_command(self) -> None:
        for event, entries in self.data["hooks"].items():
            self.assertIsInstance(entries, list, f"{event} must map to a list")
            self.assertTrue(entries, f"{event} maps to an empty list")
            for entry in entries:
                self.assertIn("hooks", entry, f"{event}: matcher block without 'hooks'")
                for hook in entry["hooks"]:
                    self.assertEqual(hook.get("type"), "command", f"{event}: type must be 'command'")
                    self.assertTrue(str(hook.get("command", "")).strip(), f"{event}: empty command")

    def test_commands_reference_the_plugin_root(self) -> None:
        """Scripts are addressed via ${CLAUDE_PLUGIN_ROOT}, never by a relative path.

        A relative path resolves against the user's cwd at session start, not against
        the plugin -- it works in the checkout and fails everywhere else.
        """
        for entries in self.data["hooks"].values():
            for entry in entries:
                for hook in entry["hooks"]:
                    befehl = hook["command"]
                    if ".py" in befehl:
                        self.assertIn(
                            "${CLAUDE_PLUGIN_ROOT}", befehl,
                            f"script path without ${{CLAUDE_PLUGIN_ROOT}}: {befehl!r}",
                        )


if __name__ == "__main__":
    unittest.main()
