"""Stdlib tests for gitctx worktree detection. Mirrors coding-suite's
test_git_context.py: builds a throwaway repo + linked worktree with real git.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gitctx  # noqa: E402


def _run(args: list[str], cwd: str) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@unittest.skipUnless(shutil.which("git"), "git not on PATH")
class TestGitCtx(unittest.TestCase):
    def test_main_vs_worktree_vs_nongit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            r = str(root)
            _run(["git", "init", "-q"], r)
            _run(["git", "config", "user.email", "t@t"], r)
            _run(["git", "config", "user.name", "t"], r)
            (root / "x.txt").write_text("hi\n", encoding="utf-8")
            _run(["git", "add", "."], r)
            _run(["git", "commit", "-qm", "init"], r)

            wt = Path(tmp) / "repo-wt"
            _run(["git", "worktree", "add", str(wt), "-b", "feat"], r)
            w = str(wt)

            # Main checkout: not a worktree; main root resolves to repo root.
            self.assertFalse(gitctx.in_worktree(r))
            self.assertEqual(gitctx.main_checkout_root(r), root.resolve())
            self.assertEqual(gitctx.repo_root(r), root.resolve())

            # Linked worktree: is a worktree; main root still resolves to repo root.
            self.assertTrue(gitctx.in_worktree(w))
            self.assertEqual(gitctx.main_checkout_root(w), root.resolve())

            # state_home redirects a worktree-local dir back under the main root.
            local = wt / ".claude" / "x"
            redirected = gitctx.state_home(local, w)
            self.assertEqual(redirected, root.resolve() / ".claude" / "x")
            # In the main checkout, state_home is a no-op.
            main_local = root / ".claude" / "x"
            self.assertEqual(gitctx.state_home(main_local, r), main_local)

    def test_nongit_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as nogit:
            self.assertFalse(gitctx.in_worktree(nogit))
            self.assertIsNone(gitctx.main_checkout_root(nogit))
            self.assertIsNone(gitctx.repo_root(nogit))


if __name__ == "__main__":
    unittest.main()
