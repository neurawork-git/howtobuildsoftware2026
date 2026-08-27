"""Install + recon tests: real git temp repo, subprocess, no LLM/network.

Runs install.py and recon.py exactly as the skill would (as scripts with the repo
as cwd), then asserts the scaffold, _shared copy, hook merge, and RECON_JSON.
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

sys.path.insert(0, str(ENGINE_DIR.parent))  # engines/ for _shared
from _shared.recon import parse_recon_json  # noqa: E402

KDIR = "kb"


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
            [sys.executable, str(INSTALL), "--knowledge-dir", KDIR],
            cwd=repo, capture_output=True, text=True,
        )

    def test_fresh_scaffold_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)

            kb = repo / KDIR
            self.assertTrue((kb / "daily").is_dir())
            self.assertTrue((kb / "knowledge" / "concepts").is_dir())
            self.assertTrue((kb / "knowledge" / "connections").is_dir())
            self.assertTrue((kb / "knowledge" / "index.md").exists())
            self.assertTrue((kb / "_shared" / "hookio.py").exists())
            self.assertTrue((kb / "scripts" / "compile.py").exists())
            self.assertTrue((kb / "hooks" / "session-start.py").exists())
            self.assertTrue((kb / "hooks" / "pre-skill.py").exists())
            self.assertTrue((kb / "hooks" / "user-prompt-submit.py").exists())
            self.assertTrue((kb / "scripts" / "research_directive.py").exists())
            self.assertTrue((kb / ".gitignore").exists())
            self.assertTrue((kb / "config.json").exists())

            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            for event in ("SessionStart", "PreCompact", "SessionEnd",
                          "UserPromptSubmit", "PreToolUse"):
                self.assertIn(event, settings["hooks"])

    def test_pre_tool_use_hook_is_scoped_to_the_skill_matcher(self) -> None:
        # In the catch-all group this hook would spawn a process on EVERY tool call.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            # A pre-existing catch-all PostToolUse group stands in for the compliance
            # engine's: the new group must be created alongside, never joined to it.
            settings_path = repo / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(json.dumps({"hooks": {"PostToolUse": [
                {"matcher": "", "hooks": [
                    {"type": "command", "command": "co-post-tooluse.py", "timeout": 15}
                ]}
            ]}}), encoding="utf-8")

            self.assertEqual(self._install(repo).returncode, 0)
            settings = json.loads(settings_path.read_text())

            groups = settings["hooks"]["PreToolUse"]
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["matcher"], "Skill")
            self.assertIn("hooks/pre-skill.py", groups[0]["hooks"][0]["command"])
            # Everything that was already there is untouched.
            post = [h["command"] for g in settings["hooks"]["PostToolUse"] for h in g["hooks"]]
            self.assertEqual(post, ["co-post-tooluse.py"])

    def test_hook_list_declares_both_new_events(self) -> None:
        sys.path.insert(0, str(ENGINE_DIR))  # the engine dir, for install
        import install

        hooks = {h[0]: h for h in install._hooks("kb")}
        self.assertIn("UserPromptSubmit", hooks)
        self.assertEqual(len(hooks["UserPromptSubmit"]), 4)  # catch-all group
        self.assertEqual(hooks["PreToolUse"][4], "Skill")

    def test_idempotent_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            # Drop a user article; ADOPT must not clobber it.
            article = repo / KDIR / "knowledge" / "concepts" / "keep.md"
            article.write_text("keep me", encoding="utf-8")
            self.assertEqual(self._install(repo).returncode, 0)

            self.assertTrue(article.exists())
            self.assertEqual(article.read_text(encoding="utf-8"), "keep me")
            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            entries = [h for g in settings["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)  # no duplicate after second install

    def test_recon_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "README.md").write_text("# demo", encoding="utf-8")
            res = subprocess.run([sys.executable, str(RECON)], cwd=repo,
                                 capture_output=True, text=True)
            info = parse_recon_json(res.stdout)
            self.assertIsNotNone(info)
            self.assertEqual(info["status"], "OK")
            self.assertIsNone(info["existing_kdir"])
            self.assertTrue(info["seed_recommended"])  # README present, no install

    def test_recon_not_a_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run([sys.executable, str(RECON)], cwd=tmp,
                                 capture_output=True, text=True)
            self.assertIn("NOT_A_GIT_REPO", res.stdout)


if __name__ == "__main__":
    unittest.main()
