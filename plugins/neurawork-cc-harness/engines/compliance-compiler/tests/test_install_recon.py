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
            self.assertTrue((cb / "_shared" / "tests" / "test_settings.py").exists())
            # plugin-scope tests assert facts an installed copy does not have
            self.assertFalse((cb / "_shared" / "tests" / "test_manifest.py").exists())
            self.assertFalse((cb / "_shared" / "tests" / "test_version_check.py").exists())
            self.assertTrue((cb / "scripts" / "extract.py").exists())
            self.assertTrue((cb / "scripts" / "validate.py").exists())
            self.assertTrue((cb / "scripts" / "precheck.py").exists())
            self.assertTrue((cb / "scripts" / "capabilities.py").exists())
            self.assertTrue((cb / "scripts" / "cap_lib.py").exists())
            self.assertTrue((cb / "scripts" / "stack.py").exists())
            self.assertFalse((cb / "hooks" / "co-session-start.py").exists())  # removed
            self.assertTrue((cb / "hooks" / "co-post-tooluse.py").exists())
            self.assertTrue((cb / ".gitignore").exists())
            self.assertTrue((cb / "config.json").exists())
            self.assertTrue((cb / "AGENTS.md").exists())

            # Prebuilt catalog seeded so a fresh install works with no LLM run.
            for name in ("gdpr.json", "soc2.json", "iso27001.json", "capabilities.json"):
                seeded = cb / "catalog" / name
                self.assertTrue(seeded.exists(), f"{name} not seeded")
                json.loads(seeded.read_text(encoding="utf-8"))  # valid JSON
            self.assertTrue((cb / "catalog" / "capabilities.md").exists())
            self.assertTrue((cb / "catalog" / "index.md").exists())
            # seeded catalog outputs must be tracked, not gitignored
            self.assertNotIn("capabilities.md", (cb / ".gitignore").read_text(encoding="utf-8"))

            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            self.assertIn("PostToolUse", settings["hooks"])
            # compliance-compiler no longer registers a SessionStart hook
            self.assertNotIn("SessionStart", settings["hooks"])
            # The matcher is what keeps the hook out of every non-write tool call: in the
            # catch-all group each one starts a `uv run` subprocess only to exit.
            self.assertEqual(
                [g["matcher"] for g in settings["hooks"]["PostToolUse"]],
                ["Write|Edit|MultiEdit"],
            )

    def test_adopt_narrows_a_catch_all_registration(self) -> None:
        # The upgrade path for a repo installed before the hook carried a matcher: the
        # entry must MOVE, or the narrowing reaches fresh installs only.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
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

    def test_adopt_appends_a_missing_ignore_rule(self) -> None:
        # `catalog/.shards/` shipped after the first releases. A create-if-absent write
        # left an existing install tracking its shard files forever; the merge appends
        # only what is missing and leaves the user's own rules in place.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            gi = repo / CDIR / ".gitignore"
            kept = [line for line in gi.read_text(encoding="utf-8").splitlines()
                    if line.strip() and "catalog/.shards/" not in line]
            gi.write_text("my-own-rule/\n" + "\n".join(kept) + "\n", encoding="utf-8")

            self.assertEqual(self._install(repo).returncode, 0)
            lines = gi.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "my-own-rule/")
            self.assertEqual(lines.count("catalog/.shards/"), 1)
            self.assertEqual(lines.count("reports/"), 1)

    def test_idempotent_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            # Overwrite a seeded catalog file with a sentinel; ADOPT + seed-only-if-absent
            # must not clobber it back to the shipped catalog.
            catalog = repo / CDIR / "catalog" / "gdpr.json"
            catalog.write_text('{"framework": "gdpr", "constraints": [], "_sentinel": true}',
                               encoding="utf-8")
            self.assertEqual(self._install(repo).returncode, 0)

            self.assertTrue(catalog.exists())
            self.assertEqual(json.loads(catalog.read_text(encoding="utf-8")).get("_sentinel"), True)
            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            entries = [h for g in settings["hooks"]["PostToolUse"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)  # no duplicate after second install

    def test_seeding_is_atomic(self) -> None:
        # A repo with its own constraint catalog but a missing capabilities.json (extract
        # ran, the capabilities stage crashed) must NOT get the shipped capabilities.json
        # spliced in — that would send the next capabilities.py run down a bogus delta path.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)
            catalog = repo / CDIR / "catalog"
            # keep the repo's own gdpr.json, drop the derived capabilities files
            (catalog / "capabilities.json").unlink()
            (catalog / "capabilities.md").unlink()
            (catalog / "stack.json").unlink()
            self.assertTrue((catalog / "gdpr.json").exists())
            self.assertEqual(self._install(repo).returncode, 0)
            # a present constraint json ⇒ seed skipped entirely, capabilities.json stays gone
            self.assertFalse((catalog / "capabilities.json").exists())
            self.assertFalse((catalog / "capabilities.md").exists())
            # ... and with no capability layer there is nothing to scaffold a stack from
            self.assertFalse((catalog / "stack.json").exists())

    def test_fresh_install_scaffolds_stack(self) -> None:
        # Deterministic, no API key: the seeded capability layer is enough to derive
        # catalog/stack.json, so a fresh install is decision-ready without an LLM run.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            catalog = repo / CDIR / "catalog"
            stack = json.loads((catalog / "stack.json").read_text(encoding="utf-8"))
            caps = json.loads((catalog / "capabilities.json").read_text(encoding="utf-8"))
            expected = sum(len(f.get("capabilities", []))
                           for f in caps["frameworks"].values())
            self.assertEqual(len(stack["choices"]), expected)
            self.assertTrue(all(e["chosen"] is None for e in stack["choices"].values()))
            # tracked artifact, not local machinery
            self.assertNotIn("stack.json", (repo / CDIR / ".gitignore").read_text())

    def test_adopt_never_clobbers_stack_choices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            stack_path = repo / CDIR / "catalog" / "stack.json"
            stack = json.loads(stack_path.read_text(encoding="utf-8"))
            key = min(stack["choices"])
            stack["choices"][key]["chosen"] = "Sentinel Component"
            stack["choices"][key]["applicable"] = False
            stack_path.write_text(json.dumps(stack, indent=2) + "\n", encoding="utf-8")
            before = stack_path.read_bytes()

            self.assertEqual(self._install(repo).returncode, 0)
            self.assertEqual(stack_path.read_bytes(), before)

    def test_fresh_install_points_prp_home_at_the_repo(self) -> None:
        # Without this, prp-core writes plans to ~/.prp and the validator hook — whose path
        # filter is repo-relative — never sees a single one.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            settings = json.loads((repo / ".claude" / "settings.json").read_text())
            self.assertEqual(settings["env"]["PRP_HOME"], ".claude/PRPs")
            self.assertIn("PostToolUse", settings["hooks"])  # both writers coexist

    def test_adopt_leaves_a_differing_prp_home_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            settings_path = repo / ".claude" / "settings.json"
            settings = json.loads(settings_path.read_text())
            settings["env"]["PRP_HOME"] = "/somewhere/else"
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

            res = self._install(repo)
            self.assertEqual(res.returncode, 0)
            settings = json.loads(settings_path.read_text())
            self.assertEqual(settings["env"]["PRP_HOME"], "/somewhere/else")
            self.assertIn("/somewhere/else", res.stdout)

    def test_adopt_prunes_stale_sessionstart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self.assertEqual(self._install(repo).returncode, 0)

            # Simulate a pre-upgrade install: a stale co-session-start.py hook file
            # and its SessionStart entry that older installs left behind.
            stale = repo / CDIR / "hooks" / "co-session-start.py"
            stale.write_text("# stale", encoding="utf-8")
            settings_path = repo / ".claude" / "settings.json"
            settings = json.loads(settings_path.read_text())
            settings["hooks"]["SessionStart"] = [{"matcher": "", "hooks": [
                {"type": "command",
                 "command": f'uv run --directory "$CLAUDE_PROJECT_DIR/{CDIR}" '
                            "python hooks/co-session-start.py",
                 "timeout": 15}]}]
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

            # Reinstall (ADOPT) must prune both.
            self.assertEqual(self._install(repo).returncode, 0)
            self.assertFalse(stale.exists())
            settings = json.loads(settings_path.read_text())
            self.assertNotIn("SessionStart", settings["hooks"])
            self.assertIn("PostToolUse", settings["hooks"])

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
