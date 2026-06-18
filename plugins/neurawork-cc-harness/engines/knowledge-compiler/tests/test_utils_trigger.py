"""Pure-logic tests for utils helpers + the 6h compile gate. No LLM/network."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import utils  # noqa: E402


class TestUtils(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(utils.slugify("Hello, World!"), "hello-world")
        self.assertEqual(utils.slugify("  Multiple   Spaces "), "multiple-spaces")
        self.assertEqual(utils.slugify("under_score__case"), "under-score-case")

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

    def test_extract_wikilinks(self) -> None:
        content = "See [[concepts/a]] and [[connections/b]] plus [[daily/2026-06-18.md]]."
        self.assertEqual(
            utils.extract_wikilinks(content),
            ["concepts/a", "connections/b", "daily/2026-06-18.md"],
        )

    def test_build_index_entry_strips_md(self) -> None:
        row = utils.build_index_entry("concepts/x.md", "summary", "daily/d.md", "2026-06-18")
        self.assertEqual(row, "| [[concepts/x]] | summary | daily/d.md | 2026-06-18 |")


class TestShouldCompile(unittest.TestCase):
    AGE = 6  # hours
    NOW = 1_000_000.0

    def test_fresh_compile_blocks(self) -> None:
        recent = self.NOW - 3600  # 1h ago < 6h
        self.assertFalse(utils.should_compile(self.NOW, recent, self.AGE, True, False, False))

    def test_stale_with_new_daily_compiles(self) -> None:
        old = self.NOW - 7 * 3600  # 7h ago > 6h
        self.assertTrue(utils.should_compile(self.NOW, old, self.AGE, True, False, False))

    def test_no_new_daily_blocks(self) -> None:
        old = self.NOW - 7 * 3600
        self.assertFalse(utils.should_compile(self.NOW, old, self.AGE, False, False, False))

    def test_worktree_blocks(self) -> None:
        old = self.NOW - 7 * 3600
        self.assertFalse(utils.should_compile(self.NOW, old, self.AGE, True, True, False))

    def test_fresh_lock_blocks(self) -> None:
        old = self.NOW - 7 * 3600
        self.assertFalse(utils.should_compile(self.NOW, old, self.AGE, True, False, True))

    def test_missing_stamp_with_new_daily_compiles(self) -> None:
        self.assertTrue(utils.should_compile(self.NOW, None, self.AGE, True, False, False))

    def test_missing_stamp_no_daily_blocks(self) -> None:
        self.assertFalse(utils.should_compile(self.NOW, None, self.AGE, False, False, False))


if __name__ == "__main__":
    unittest.main()
