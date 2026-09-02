"""Install + recon tests: real git temp repo, subprocess, no LLM/network.

Runs install.py and recon.py exactly as the skill would (as scripts with the repo
as cwd), then asserts the scaffold, _shared copy, hook merge, RECON_JSON, and that
the claudemd-lerner skill coexists with knowledge-compiler without clobbering hooks.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
INSTALL = ENGINE_DIR / "install.py"
RECON = ENGINE_DIR / "recon.py"
KC_INSTALL = ENGINE_DIR.parent / "knowledge-compiler" / "install.py"

sys.path.insert(0, str(ENGINE_DIR.parent))  # engines/ for _shared
from _shared.recon import parse_recon_json  # noqa: E402

LDIR = "lc"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestInstall(unittest.TestCase):
    def _install(self, repo: Path):
        return subprocess.run(
            [sys.executable, str(INSTALL), "--lerner-dir", LDIR],
            cwd=repo, capture_output=True, text=True,
        )

    def test_fresh_scaffold_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)

            lc = repo / LDIR
            self.assertTrue((lc / "daily").is_dir())
            self.assertFalse((lc / "knowledge").exists())  # no wiki tree
            self.assertTrue((lc / "_shared" / "hookio.py").exists())
            self.assertTrue((lc / "scripts" / "update.py").exists())
            self.assertTrue((lc / "scripts" / "flush.py").exists())
            self.assertTrue((lc / "hooks" / "cl-session-start.py").exists())
            self.assertTrue((lc / "hooks" / "cl-session-end.py").exists())
            self.assertTrue((lc / "hooks" / "cl-pre-compact.py").exists())
            self.assertTrue((lc / ".gitignore").exists())
            self.assertTrue((lc / "config.json").exists())

            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            for event in ("SessionStart", "PreCompact", "SessionEnd"):
                self.assertIn(event, settings["hooks"])
            # the merged command points at the cl- hooks
            ends = [h for g in settings["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertTrue(any("hooks/cl-session-end.py" in h["command"] for h in ends))

    def test_fresh_install_ships_no_plugin_only_test(self) -> None:
        # test_manifest.py and test_version_check.py assert plugin-level facts (the
        # manifest, <plugin>/hooks/version-check.py) that no target repo has — shipped
        # there they fail with FileNotFoundError on arrival.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            shared_tests = repo / LDIR / "_shared" / "tests"
            self.assertTrue((shared_tests / "test_settings.py").exists())
            self.assertFalse((shared_tests / "test_manifest.py").exists())
            self.assertFalse((shared_tests / "test_version_check.py").exists())

    def test_adopt_removes_plugin_only_tests_an_older_install_left(self) -> None:
        # The repair path: a repo installed before the exclusion carries both files.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            shared_tests = repo / LDIR / "_shared" / "tests"
            for name in ("test_manifest.py", "test_version_check.py"):
                (shared_tests / name).write_text("# stale", encoding="utf-8")

            self.assertEqual(self._install(repo).returncode, 0)
            self.assertFalse((shared_tests / "test_manifest.py").exists())
            self.assertFalse((shared_tests / "test_version_check.py").exists())
            self.assertTrue((shared_tests / "test_settings.py").exists())

    def test_adopt_prunes_the_uv_lock_ignore_rule(self) -> None:
        # uv.lock is tracked now — a committed lock file removes the dependency resolve
        # from a hook's cold start. The merge only appends, so the rule an earlier
        # release wrote has to be pruned or it stays in every existing install.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            gi = repo / LDIR / ".gitignore"
            gi.write_text("my-own-rule/\nuv.lock\n" + gi.read_text(encoding="utf-8"),
                          encoding="utf-8")

            self.assertEqual(self._install(repo).returncode, 0)
            lines = gi.read_text(encoding="utf-8").splitlines()
            self.assertNotIn("uv.lock", lines)
            self.assertEqual(lines[0], "my-own-rule/")
            self.assertIn(".venv/", lines)

    def test_idempotent_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            # Drop a daily log; ADOPT must not clobber it.
            daily = repo / LDIR / "daily" / "keep.md"
            daily.write_text("keep me", encoding="utf-8")
            self.assertEqual(self._install(repo).returncode, 0)

            self.assertTrue(daily.exists())
            self.assertEqual(daily.read_text(encoding="utf-8"), "keep me")
            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            entries = [h for g in settings["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)  # no duplicate after second install

    def test_coexists_with_knowledge_compiler(self) -> None:
        """Both skills installed in one repo → distinct hooks, no clobber."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            kc = subprocess.run(
                [sys.executable, str(KC_INSTALL), "--knowledge-dir", "kb"],
                cwd=repo, capture_output=True, text=True,
            )
            self.assertEqual(kc.returncode, 0, kc.stderr)
            lc = self._install(repo)
            self.assertEqual(lc.returncode, 0, lc.stderr)

            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            for event in ("SessionStart", "PreCompact", "SessionEnd"):
                cmds = [h["command"] for g in settings["hooks"][event] for h in g["hooks"]]
                # exactly two entries: one kc, one lerner — neither overwritten
                self.assertEqual(len(cmds), 2, f"{event}: {cmds}")
                self.assertTrue(any("/kb" in c and "hooks/cl-" not in c for c in cmds),
                                f"{event}: kc command missing/overwritten: {cmds}")
                self.assertTrue(any("hooks/cl-" in c and "/lc" in c for c in cmds),
                                f"{event}: lerner command missing: {cmds}")

    def test_recon_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "README.md").write_text("# demo", encoding="utf-8")
            res = subprocess.run([sys.executable, str(RECON)], cwd=repo,
                                 capture_output=True, text=True)
            info = parse_recon_json(res.stdout)
            self.assertIsNotNone(info)
            assert info is not None  # narrow for type-checkers
            self.assertEqual(info["status"], "OK")
            self.assertIsNone(info["existing_ldir"])
            self.assertTrue(info["seed_recommended"])  # README present, no install
            self.assertIn("suggested_depth", info)
            self.assertIn("language", info)

    def test_recon_not_a_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run([sys.executable, str(RECON)], cwd=tmp,
                                 capture_output=True, text=True)
            self.assertIn("NOT_A_GIT_REPO", res.stdout)


if __name__ == "__main__":
    unittest.main()
