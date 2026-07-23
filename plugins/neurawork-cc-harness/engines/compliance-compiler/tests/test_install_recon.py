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

CDIR = "cb"


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
            [sys.executable, str(INSTALL), "--catalog-dir", CDIR],
            cwd=repo, capture_output=True, text=True,
        )

    def test_fresh_scaffold_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)

            cb = repo / CDIR
            self.assertTrue((cb / "catalog").is_dir())
            self.assertTrue((cb / "catalog" / ".shards").is_dir())
            self.assertTrue((cb / "reports").is_dir())
            self.assertTrue((cb / "_shared" / "hookio.py").exists())
            self.assertTrue((cb / "scripts" / "extract.py").exists())
            self.assertTrue((cb / "scripts" / "validate.py").exists())
            self.assertTrue((cb / "scripts" / "precheck.py").exists())
            self.assertTrue((cb / "scripts" / "capabilities.py").exists())
            self.assertTrue((cb / "scripts" / "cap_lib.py").exists())
            self.assertTrue((cb / "hooks" / "co-session-start.py").exists())
            self.assertTrue((cb / "hooks" / "co-post-tooluse.py").exists())
            self.assertTrue((cb / ".gitignore").exists())
            self.assertTrue((cb / "config.json").exists())
            self.assertTrue((cb / "AGENTS.md").exists())

            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            for event in ("SessionStart", "PostToolUse"):
                self.assertIn(event, settings["hooks"])

    def test_idempotent_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            # Drop a catalog file; ADOPT must not clobber it.
            catalog = repo / CDIR / "catalog" / "gdpr.json"
            catalog.write_text('{"framework": "gdpr", "constraints": []}', encoding="utf-8")
            self.assertEqual(self._install(repo).returncode, 0)

            self.assertTrue(catalog.exists())
            self.assertIn("gdpr", catalog.read_text(encoding="utf-8"))
            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            entries = [h for g in settings["hooks"]["PostToolUse"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)  # no duplicate after second install

    def test_recon_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            res = subprocess.run([sys.executable, str(RECON)], cwd=repo,
                                 capture_output=True, text=True)
            info = parse_recon_json(res.stdout)
            self.assertIsNotNone(info)
            self.assertEqual(info["status"], "OK")
            self.assertIsNone(info["existing_dir"])
            self.assertFalse(info["catalog_built"])

    def test_recon_not_a_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run([sys.executable, str(RECON)], cwd=tmp,
                                 capture_output=True, text=True)
            self.assertIn("NOT_A_GIT_REPO", res.stdout)


if __name__ == "__main__":
    unittest.main()
