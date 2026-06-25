"""Pure-logic tests for utils helpers + the 6h update gate. No LLM/network."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import utils  # noqa: E402


class TestUtils(unittest.TestCase):
    def test_file_hash_stable_and_short(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("content")
            path = Path(f.name)
        try:
            h1 = utils.file_hash(path)
            h2 = utils.file_hash(path)
            self.assertEqual(h1, h2)
            self.assertEqual(len(h1), 16)
        finally:
            path.unlink()


class TestShouldUpdate(unittest.TestCase):
    AGE = 6  # hours
    NOW = 1_000_000.0

    def test_fresh_update_blocks(self) -> None:
        recent = self.NOW - 3600  # 1h ago < 6h
        self.assertFalse(utils.should_update(self.NOW, recent, self.AGE, True, False, False))

    def test_stale_with_new_daily_updates(self) -> None:
        old = self.NOW - 7 * 3600  # 7h ago > 6h
        self.assertTrue(utils.should_update(self.NOW, old, self.AGE, True, False, False))

    def test_no_new_daily_blocks(self) -> None:
        old = self.NOW - 7 * 3600
        self.assertFalse(utils.should_update(self.NOW, old, self.AGE, False, False, False))

    def test_worktree_blocks(self) -> None:
        old = self.NOW - 7 * 3600
        self.assertFalse(utils.should_update(self.NOW, old, self.AGE, True, True, False))

    def test_fresh_lock_blocks(self) -> None:
        old = self.NOW - 7 * 3600
        self.assertFalse(utils.should_update(self.NOW, old, self.AGE, True, False, True))

    def test_missing_stamp_with_new_daily_updates(self) -> None:
        self.assertTrue(utils.should_update(self.NOW, None, self.AGE, True, False, False))

    def test_missing_stamp_no_daily_blocks(self) -> None:
        self.assertFalse(utils.should_update(self.NOW, None, self.AGE, False, False, False))


if __name__ == "__main__":
    unittest.main()
