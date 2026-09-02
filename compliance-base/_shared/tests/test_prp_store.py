"""Stdlib tests for prp_store: the store key prp-core computes, and the symlink
that wires one store per repo.

``prp_home`` is always a temp dir — the real ``~/.prp`` is never touched. The key
is checked against ``git hash-object`` itself, since reproducing it byte for byte
is the whole contract.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # engines/, for _shared
from _shared import prp_store


def _git_hash(path: str) -> str:
    out = subprocess.run(["git", "hash-object", "--stdin"], input=path,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()[:8]


class TestStoreKey(unittest.TestCase):
    def test_the_key_matches_git_hash_object(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            key = prp_store.store_key(root)
            slug, _, digest = key.rpartition("-")
            self.assertEqual(digest, _git_hash(str(root)))
            self.assertEqual(slug, prp_store._slug(root.name))

    def test_the_slug_lowercases_and_collapses_runs(self) -> None:
        self.assertEqual(prp_store._slug("HowToBuildSoftware2026"),
                         "howtobuildsoftware2026")
        self.assertEqual(prp_store._slug("My Repo -- v2!"), "my-repo-v2")
        self.assertEqual(prp_store._slug("!!!"), "project")


class TestLinkPrpStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        self.repo = base / "repo"
        self.repo.mkdir()
        self.home = base / "prp-home"
        self.link = self.home / prp_store.store_key(self.repo)
        self.target = self.repo / ".claude" / "PRPs"

    def test_a_fresh_link_points_into_the_repo(self) -> None:
        status, path = prp_store.link_prp_store(self.repo, self.home)
        self.assertEqual(status, "linked")
        self.assertEqual(path, str(self.target))
        self.assertTrue(self.link.is_symlink())
        self.assertEqual(self.link.resolve(), self.target.resolve())
        self.assertTrue(self.target.is_dir(), "the link must not dangle")

    def test_linking_twice_is_idempotent(self) -> None:
        prp_store.link_prp_store(self.repo, self.home)
        before = self.link.readlink()
        status, path = prp_store.link_prp_store(self.repo, self.home)
        self.assertEqual(status, "already")
        self.assertEqual(path, str(self.target))
        self.assertEqual(self.link.readlink(), before)

    def test_a_real_directory_is_a_conflict_and_is_left_untouched(self) -> None:
        self.link.mkdir(parents=True)
        (self.link / "plans").mkdir()
        status, path = prp_store.link_prp_store(self.repo, self.home)
        self.assertEqual(status, "conflict")
        self.assertEqual(path, str(self.link))
        self.assertFalse(self.link.is_symlink())
        self.assertTrue((self.link / "plans").is_dir(), "another store's artifacts")

    def test_a_symlink_to_somewhere_else_is_a_conflict(self) -> None:
        other = Path(self._tmp.name).resolve() / "other-store"
        other.mkdir()
        self.home.mkdir(parents=True)
        self.link.symlink_to(other, target_is_directory=True)
        status, path = prp_store.link_prp_store(self.repo, self.home)
        self.assertEqual(status, "conflict")
        self.assertEqual(path, str(other))
        self.assertEqual(self.link.resolve(), other)

    def test_a_platform_that_cannot_symlink_reports_unsupported(self) -> None:
        original = Path.symlink_to

        def refuse(*_args, **_kwargs) -> None:
            raise OSError("symbolic link privilege not held")

        Path.symlink_to = refuse  # type: ignore[method-assign]
        try:
            status, path = prp_store.link_prp_store(self.repo, self.home)
        finally:
            Path.symlink_to = original  # type: ignore[method-assign]
        self.assertEqual(status, "unsupported")
        self.assertIn("privilege", str(path))
        self.assertFalse(self.link.exists())

    def test_a_relative_prp_home_never_links_inside_the_repo(self) -> None:
        # The upgrade path: every pre-0.8 install wrote PRP_HOME=".claude/PRPs" into
        # settings.json, and Claude Code exports it into the session. Honouring a
        # relative value would resolve it against the installer's cwd and write a link
        # into the repo's own store pointing at its own parent — no shared store, and a
        # recursive symlink among tracked artifacts.
        previous = os.environ.get("PRP_HOME")
        os.environ["PRP_HOME"] = ".claude/PRPs"
        cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            self.assertEqual(prp_store.default_prp_home(), Path.home() / ".prp")
            self.assertEqual(prp_store.store_link(self.repo).parent,
                             Path.home() / ".prp")
        finally:
            os.chdir(cwd)
            if previous is None:
                os.environ.pop("PRP_HOME", None)
            else:
                os.environ["PRP_HOME"] = previous
        self.assertFalse((self.target / prp_store.store_key(self.repo)).exists())

    def test_an_absolute_prp_home_is_honoured(self) -> None:
        previous = os.environ.get("PRP_HOME")
        os.environ["PRP_HOME"] = str(self.home)
        try:
            self.assertEqual(prp_store.store_link(self.repo), self.link)
        finally:
            if previous is None:
                os.environ.pop("PRP_HOME", None)
            else:
                os.environ["PRP_HOME"] = previous

    def test_the_reported_path_is_the_link_that_was_written(self) -> None:
        status, lines = prp_store.wire_store(self.repo, self.home)
        self.assertEqual(status, "linked")
        self.assertIn(str(self.link), lines[0])
        self.assertIn(str(self.target), lines[0])
        self.assertEqual(len(lines), 1, "no settings PRP_HOME, so nothing to warn about")

    def test_an_existing_settings_prp_home_is_reported_as_winning(self) -> None:
        settings = self.repo / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"env": {"PRP_HOME": ".claude/PRPs"}}),
                            encoding="utf-8")
        status, lines = prp_store.wire_store(self.repo, self.home)
        self.assertEqual(status, "linked")
        self.assertEqual(len(lines), 2)
        self.assertIn("takes precedence", lines[1])
        self.assertIn(".claude/PRPs", lines[1])

    def test_installing_from_a_worktree_links_the_main_checkout(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git not on PATH")
        base = Path(self._tmp.name).resolve()
        main, wt = base / "main", base / "wt"
        _run(["git", "init", "-q", "-b", "main", str(main)], str(base))
        _run(["git", "-C", str(main), "commit", "-q", "--allow-empty", "-m", "init"],
             str(base))
        _run(["git", "-C", str(main), "worktree", "add", "-q", str(wt), "-b", "side"],
             str(base))

        self.assertEqual(prp_store.store_key(wt), prp_store.store_key(main))
        status, path = prp_store.link_prp_store(wt, self.home)
        self.assertEqual(status, "linked")
        self.assertEqual(path, str(main / ".claude" / "PRPs"))


def _run(args: list[str], cwd: str) -> None:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
           "PATH": os.environ.get("PATH", ""), "HOME": cwd}
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, env=env)


if __name__ == "__main__":
    unittest.main()
