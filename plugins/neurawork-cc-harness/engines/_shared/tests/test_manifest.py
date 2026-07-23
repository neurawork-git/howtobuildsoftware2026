"""Guard: the plugin manifest stays valid JSON with a semver version."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

MANIFEST = (
    Path(__file__).resolve().parent.parent.parent.parent
    / ".claude-plugin"
    / "plugin.json"
)


class TestManifest(unittest.TestCase):
    def test_valid_json_with_semver_version(self) -> None:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "neurawork-cc-harness")
        self.assertRegex(data["version"], r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
