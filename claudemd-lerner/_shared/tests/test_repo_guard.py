"""Stdlib tests for repo_guard: knowledge/docs in-repo, never under .claude/."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import repo_guard  # noqa: E402


class TestRepoGuard(unittest.TestCase):
    def test_allows_docs_and_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ok = repo_guard.assert_in_repo_not_dotclaude(Path(tmp) / "docs" / "x.md", tmp)
            self.assertEqual(ok, (Path(tmp) / "docs" / "x.md").resolve())
            repo_guard.assert_in_repo_not_dotclaude(Path(tmp) / "knowledge" / "index.md", tmp)
            repo_guard.assert_in_repo_not_dotclaude(Path(tmp) / "CLAUDE.md", tmp)

    def test_rejects_dotclaude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(repo_guard.WriteGuardError):
                repo_guard.assert_in_repo_not_dotclaude(Path(tmp) / ".claude" / "k.md", tmp)
            with self.assertRaises(repo_guard.WriteGuardError):
                repo_guard.assert_in_repo_not_dotclaude(Path(tmp) / ".claude", tmp)

    def test_rejects_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(repo_guard.WriteGuardError):
                repo_guard.assert_in_repo_not_dotclaude("/etc/passwd", tmp)

    def test_rejects_traversal_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(repo_guard.WriteGuardError):
                repo_guard.assert_in_repo_not_dotclaude(Path(tmp) / ".." / "x.md", tmp)
            # ..-traversal back into .claude is also rejected.
            with self.assertRaises(repo_guard.WriteGuardError):
                repo_guard.assert_in_repo_not_dotclaude(Path(tmp) / "docs" / ".." / ".claude" / "x", tmp)

    def test_safe_join(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = repo_guard.safe_join(tmp, "docs", "rules", "a.md")
            self.assertEqual(p, (Path(tmp) / "docs" / "rules" / "a.md").resolve())
            with self.assertRaises(repo_guard.WriteGuardError):
                repo_guard.safe_join(tmp, ".claude", "x")


if __name__ == "__main__":
    unittest.main()
