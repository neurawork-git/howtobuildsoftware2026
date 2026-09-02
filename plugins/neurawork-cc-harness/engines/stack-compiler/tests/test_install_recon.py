"""Install + recon tests: real git temp repo, subprocess, no LLM/network.

Runs install.py and recon.py exactly as the skill would (as scripts with the repo
as cwd), then asserts the scaffold, _shared copy, hook merge, and RECON_JSON.
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

ENGINE_DIR = Path(__file__).resolve().parent.parent
INSTALL = ENGINE_DIR / "install.py"
RECON = ENGINE_DIR / "recon.py"
SHARED_SRC = ENGINE_DIR.parent / "_shared"

sys.path.insert(0, str(ENGINE_DIR.parent))  # engines/ for _shared
from _shared import prp_store
from _shared.recon import parse_recon_json  # noqa: E402

SDIR = "sb"
CDIR = "cb"

SCRIPTS = ("config.py", "gate_lib.py", "rank.py", "rank_lib.py", "scope.py",
           "scope_lib.py", "selection.py", "selection_lib.py", "validate.py")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")


def _fake_compliance(repo: Path) -> None:
    """The sibling install the passes read through — signature files only."""
    (repo / CDIR / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / CDIR / "scripts" / "stack.py").write_text("# stub", encoding="utf-8")
    (repo / CDIR / "catalog").mkdir(parents=True, exist_ok=True)
    (repo / CDIR / "catalog" / "capabilities.json").write_text(
        '{"frameworks": {}}', encoding="utf-8")


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestInstall(unittest.TestCase):
    def _install(self, repo: Path, stack_dir: str = SDIR, prp_home: Path | None = None):
        # PRP_HOME is prp-core's own store prefix, and the installer links into it.
        # Point it inside the temp repo so no test ever touches the real ~/.prp.
        env = dict(os.environ, PRP_HOME=str(prp_home or repo / ".prp-home"))
        return subprocess.run(
            [sys.executable, str(INSTALL),
             "--stack-dir", stack_dir, "--compliance-dir", CDIR],
            cwd=repo, capture_output=True, text=True, env=env,
        )

    def _store_link(self, repo: Path) -> Path:
        return repo / ".prp-home" / prp_store.store_key(repo)

    def test_fresh_scaffold_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _fake_compliance(repo)
            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)

            sb = repo / SDIR
            self.assertTrue((sb / "reports").is_dir())
            self.assertTrue((sb / "hooks" / "st-post-tooluse.py").exists())
            for name in SCRIPTS:
                self.assertTrue((sb / "scripts" / name).exists(), f"{name} missing")
            self.assertTrue((sb / "AGENTS.md").exists())
            self.assertTrue((sb / "pyproject.toml").exists())
            self.assertTrue((sb / ".gitignore").exists())
            self.assertTrue((sb / "_shared" / "hookio.py").exists())
            self.assertTrue((sb / "_shared" / "tests" / "test_settings.py").exists())
            # plugin-scope tests assert facts an installed copy does not have
            self.assertFalse((sb / "_shared" / "tests" / "test_manifest.py").exists())
            self.assertFalse((sb / "_shared" / "tests" / "test_version_check.py").exists())

            config = json.loads((sb / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["stack_dir"], SDIR)
            self.assertEqual(config["compliance_dir"], CDIR)

            gitignore = (sb / ".gitignore").read_text(encoding="utf-8")
            for rule in ("reports/", ".shards/", "uv.lock"):
                self.assertIn(rule, gitignore)
            # product.md is the tracked scoping input of record — named in the comment
            # that says so, never in a rule
            rules = [line.strip() for line in gitignore.splitlines()
                     if line.strip() and not line.strip().startswith("#")]
            self.assertNotIn("product.md", " ".join(rules))

            self.assertEqual(
                (sb / "VERSION").read_text(encoding="utf-8").strip(),
                (ENGINE_DIR / "VERSION").read_text(encoding="utf-8").strip(),
            )

            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            self.assertNotIn("SessionStart", settings["hooks"])
            groups = settings["hooks"]["PostToolUse"]
            self.assertEqual([g["matcher"] for g in groups], ["Write|Edit|MultiEdit"])
            entries = [h for g in groups for h in g["hooks"]]
            self.assertEqual(len(entries), 1)
            self.assertIn("hooks/st-post-tooluse.py", entries[0]["command"])
            # The store is wired by symlink, so PRP_HOME stays out of settings.json.
            self.assertNotIn("PRP_HOME", settings.get("env", {}))
            link = self._store_link(repo)
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), (repo / ".claude" / "PRPs").resolve())

    def test_an_unlinkable_store_falls_back_to_prp_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _fake_compliance(repo)
            # A real directory at the store key: another store's artifacts, never
            # replaced. The installer falls back and says so.
            occupied = self._store_link(repo)
            occupied.mkdir(parents=True)
            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)

            self.assertFalse(occupied.is_symlink())
            settings = json.loads(
                (repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["env"]["PRP_HOME"], ".claude/PRPs")
            self.assertIn("falling back to PRP_HOME", res.stdout)

    def test_a_relative_prp_home_in_the_environment_is_not_a_link_prefix(self) -> None:
        # The upgrade path: a repo wired before 0.8 exports PRP_HOME=".claude/PRPs" into
        # the session. Resolved against the installer's cwd it would put the link inside
        # the repo's own store, pointing at its own parent.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _fake_compliance(repo)
            env = dict(os.environ, PRP_HOME=".claude/PRPs", HOME=str(repo / "home"))
            res = subprocess.run(
                [sys.executable, str(INSTALL),
                 "--stack-dir", SDIR, "--compliance-dir", CDIR],
                cwd=repo, capture_output=True, text=True, env=env,
            )
            self.assertEqual(res.returncode, 0, res.stderr)

            store = repo / ".claude" / "PRPs"
            self.assertEqual([p for p in store.iterdir() if p.is_symlink()], [],
                             "a link was written inside the repo's own store")
            link = repo / "home" / ".prp" / prp_store.store_key(repo)
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), store.resolve())
            self.assertIn(str(link), res.stdout)

    def test_idempotent_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _fake_compliance(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            config = repo / SDIR / "config.json"
            data = json.loads(config.read_text(encoding="utf-8"))
            data["validate_mode"]["prd"] = "block"
            config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            product = repo / SDIR / "product.md"
            product.write_text("# our product\n", encoding="utf-8")

            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("ADOPT", res.stdout)
            self.assertEqual(
                json.loads(config.read_text(encoding="utf-8"))["validate_mode"]["prd"],
                "block",
            )
            self.assertEqual(product.read_text(encoding="utf-8"), "# our product\n")
            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            entries = [h for g in settings["hooks"]["PostToolUse"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)  # no duplicate after second install

    def test_adopt_migrates_a_catch_all_registration(self) -> None:
        # The upgrade path for the hand install: the entry must MOVE, or the narrow
        # matcher reaches fresh installs only and every tool call keeps paying for a
        # `uv run` subprocess that reads stdin and exits.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _fake_compliance(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            sp = repo / ".claude" / "settings.json"
            settings = json.loads(sp.read_text())
            entry = settings["hooks"]["PostToolUse"][0]["hooks"][0]
            settings["hooks"]["PostToolUse"] = [{"matcher": "", "hooks": [entry]}]
            sp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

            self.assertEqual(self._install(repo).returncode, 0)
            groups = json.loads(sp.read_text())["hooks"]["PostToolUse"]
            self.assertEqual([g["matcher"] for g in groups], ["Write|Edit|MultiEdit"])
            self.assertEqual(len([h for g in groups for h in g["hooks"]]), 1)

    def test_adopt_refreshes_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _fake_compliance(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            drifted = repo / SDIR / "_shared" / "settings.py"
            drifted.write_text("# a stale hand copy\n", encoding="utf-8")
            shutil.rmtree(repo / SDIR / "_shared" / "tests")

            self.assertEqual(self._install(repo).returncode, 0)
            self.assertEqual(drifted.read_bytes(), (SHARED_SRC / "settings.py").read_bytes())
            self.assertTrue((repo / SDIR / "_shared" / "tests" / "test_settings.py").exists())

    def test_install_without_compliance_dir_warns_and_succeeds(self) -> None:
        # Independently installable, not independently operable: install order must
        # not be load-bearing.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            res = self._install(repo)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue((repo / SDIR / "scripts" / "scope.py").exists())
            self.assertIn("compliance-compiler", res.stdout)

    def test_refuses_dotclaude_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            res = self._install(repo, stack_dir=".claude/stack")
            self.assertNotEqual(res.returncode, 0)
            self.assertFalse((repo / ".claude" / "stack").exists())
            self.assertFalse((repo / ".claude" / "settings.json").exists())

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
            self.assertIsNone(info["compliance_dir"])
            self.assertFalse(info["stack_state"]["exists"])

    def test_recon_finds_the_install_and_the_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            _fake_compliance(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            (repo / CDIR / "catalog" / "stack.json").write_text(
                json.dumps({"choices": {
                    "a": {"applicable": True, "scoped_from": "h1", "chosen": "Postgres"},
                    "b": {"applicable": True, "scoped_from": "h1", "chosen": None},
                    # scaffolded but never scoped: stack.py defaults `applicable` to True,
                    # so only `scoped_from` distinguishes this from a scoped entry
                    "c": {"applicable": True, "chosen": None},
                }}), encoding="utf-8")

            res = subprocess.run([sys.executable, str(RECON)], cwd=repo,
                                 capture_output=True, text=True)
            info = parse_recon_json(res.stdout)
            self.assertEqual(info["existing_dir"], SDIR)
            self.assertEqual(info["compliance_dir"], CDIR)
            self.assertTrue(info["existing_hooks"]["PostToolUse"])
            self.assertEqual(info["stack_state"],
                             {"exists": True, "total": 3, "scoped": 2, "chosen": 1})

    def test_recon_not_a_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run([sys.executable, str(RECON)], cwd=tmp,
                                 capture_output=True, text=True)
            self.assertIn("NOT_A_GIT_REPO", res.stdout)


if __name__ == "__main__":
    unittest.main()
