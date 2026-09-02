"""CLI tests for hooks/co-post-tooluse.py — which plan writes it reacts to.

Only the path filter, over a temp install: a plan in the canonical location, one in
the store layout, and — the case a symlinked PRP store creates — one a worktree
session writes that physically lives in the MAIN checkout. No LLM, no network, no
API key; the deep validator never spawns because the catalog is left unbuilt, which
the advisory says in one line.
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

ENGINE = Path(__file__).resolve().parent.parent
ENGINES = ENGINE.parent
PAYLOAD = ENGINE / "payload"

PLAN = "# Plan\n\n## Compliance\n\n**Capabilities**: none — tooling only.\n"


def _git(args: list[str], cwd: Path) -> None:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
           "PATH": os.environ.get("PATH", ""), "HOME": str(cwd)}
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   text=True, env=env)


class TestHookPaths(unittest.TestCase):
    def _install(self, repo: Path) -> Path:
        """A real install layout: hooks/ and scripts/ next to _shared/."""
        root = repo / "compliance-base"
        (root / "scripts").mkdir(parents=True)
        (root / "hooks").mkdir(parents=True)
        (root / "catalog").mkdir(parents=True)
        for script in (PAYLOAD / "scripts").glob("*.py"):
            shutil.copy2(script, root / "scripts" / script.name)
        for hook in (PAYLOAD / "hooks").glob("*.py"):
            shutil.copy2(hook, root / "hooks" / hook.name)
        shutil.copytree(ENGINES / "_shared", root / "_shared",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        return root

    def _plan(self, root_dir: Path, rel: str) -> Path:
        path = root_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PLAN, encoding="utf-8")
        return path

    def _run(self, root: Path, path_str: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, COMPLIANCE_ROOT=str(root))
        env.pop("CLAUDE_INVOKED_BY", None)  # the recursion guard would exit(0) on it
        return subprocess.run(
            [sys.executable, str(root / "hooks" / "co-post-tooluse.py")],
            input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": path_str}}),
            capture_output=True, text=True, env=env, timeout=60, check=False,
        )

    def test_both_plan_layouts_are_matched_and_other_paths_are_not(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t)
            root = self._install(repo)
            for rel in (".claude/PRPs/plans/feature.plan.md",
                        ".claude/PRPs/repo-1a2b3c4d/plans/feature.plan.md"):
                plan = self._plan(repo, rel)
                res = self._run(root, str(plan))
                self.assertEqual(res.returncode, 0)
                self.assertNotEqual(res.stdout, "", f"{rel}: the gate stayed silent")

            for rel in ("docs/notes.md", ".claude/PRPs/plans/completed/old.plan.md"):
                other = self._plan(repo, rel)
                res = self._run(root, str(other))
                self.assertEqual(res.returncode, 0)
                self.assertEqual(res.stdout, "", f"{rel}: the gate should stay silent")

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_a_worktree_session_writing_through_the_linked_store_is_matched(self) -> None:
        # The symlinked store puts a worktree session's plan in the MAIN checkout, so
        # `relative_to(<worktree>)` finds nothing. The install under test is the
        # worktree's; the plan it must still match lives in the main checkout.
        with tempfile.TemporaryDirectory() as t:
            base = Path(t).resolve()
            main, wt = base / "main", base / "wt"
            _git(["init", "-q", "-b", "main", str(main)], base)
            _git(["-C", str(main), "commit", "-q", "--allow-empty", "-m", "init"], base)
            _git(["-C", str(main), "worktree", "add", "-q", str(wt), "-b", "side"], base)

            root = self._install(wt)
            self._plan(main, ".claude/PRPs/plans/feature.plan.md")
            link = base / "prp-home" / "main-key"
            link.parent.mkdir(parents=True)
            link.symlink_to(main / ".claude" / "PRPs", target_is_directory=True)

            res = self._run(root, str(link / "plans" / "feature.plan.md"))
            self.assertEqual(res.returncode, 0)
            self.assertNotEqual(res.stdout, "",
                                "the gate stayed silent for a worktree write")


if __name__ == "__main__":
    unittest.main()
