"""Stdlib tests for settings.merge_hooks idempotency + non-clobber."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import settings  # noqa: E402

HOOK = ("SessionEnd", "python3 .claude/nw/end.py", 10, "nw/end.py")


class TestMergeHooks(unittest.TestCase):
    def test_creates_file_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            changed = settings.merge_hooks(tmp, [HOOK])
            self.assertTrue(changed)
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            entries = data["hooks"]["SessionEnd"][0]["hooks"]
            self.assertEqual(entries[0]["command"], HOOK[1])
            self.assertEqual(entries[0]["timeout"], 10)

    def test_idempotent_second_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(settings.merge_hooks(tmp, [HOOK]))
            self.assertFalse(settings.merge_hooks(tmp, [HOOK]))
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            # No duplicate hook entry.
            entries = [h for g in data["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)

    def test_preserves_unrelated_hooks_and_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text(json.dumps({
                "model": "opus",
                "hooks": {"SessionEnd": [
                    {"matcher": "", "hooks": [
                        {"type": "command", "command": "other.py", "timeout": 5}
                    ]}
                ]},
            }))
            settings.merge_hooks(tmp, [HOOK])
            data = json.loads(sp.read_text())
            self.assertEqual(data["model"], "opus")
            cmds = [h["command"] for g in data["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertIn("other.py", cmds)
            self.assertIn(HOOK[1], cmds)

    def test_migrates_drifted_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text(json.dumps({"hooks": {"SessionEnd": [
                {"matcher": "", "hooks": [
                    {"type": "command", "command": "old/nw/end.py", "timeout": 99}
                ]}
            ]}}))
            self.assertTrue(settings.merge_hooks(tmp, [HOOK]))
            data = json.loads(sp.read_text())
            hook = data["hooks"]["SessionEnd"][0]["hooks"][0]
            self.assertEqual(hook["command"], HOOK[1])  # command updated
            self.assertEqual(hook["timeout"], 99)  # hand-edited timeout kept

    def test_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text("{ not json")
            with self.assertRaises(settings.SettingsError):
                settings.merge_hooks(tmp, [HOOK])


if __name__ == "__main__":
    unittest.main()
