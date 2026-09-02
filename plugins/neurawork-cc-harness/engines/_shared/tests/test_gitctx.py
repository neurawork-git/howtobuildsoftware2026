"""Stdlib tests for gitctx worktree detection. Mirrors a prior continuous-learner's
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

            # checkout_roots: one root in the main checkout, two in a worktree — the
            # worktree first, the main checkout behind it (where a symlinked PRP store
            # puts a document a worktree session writes).
            self.assertEqual(gitctx.checkout_roots(r), [root.resolve()])
            self.assertEqual(gitctx.checkout_roots(w), [wt.resolve(), root.resolve()])
            # `local` overrides only the nearest root, and never duplicates the main one.
            self.assertEqual(gitctx.checkout_roots(w, local=wt.resolve()),
                             [wt.resolve(), root.resolve()])
            self.assertEqual(gitctx.checkout_roots(r, local=root.resolve()),
                             [root.resolve()])

    def test_nongit_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as nogit:
            self.assertFalse(gitctx.in_worktree(nogit))
            self.assertIsNone(gitctx.main_checkout_root(nogit))
            self.assertIsNone(gitctx.repo_root(nogit))
            # Outside git a hook still knows its own working tree, and that answer wins:
            # classifying against a root the rest of the hook does not use finds nothing.
            here = Path(nogit).resolve()
            self.assertEqual(gitctx.checkout_roots(nogit), [here])
            self.assertEqual(gitctx.checkout_roots(nogit, local=here / "wt"),
                             [here / "wt"])


if __name__ == "__main__":
    unittest.main()
