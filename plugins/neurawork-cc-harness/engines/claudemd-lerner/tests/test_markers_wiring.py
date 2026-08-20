"""The guard must be WIRED into the learner's run, not merely correct in isolation.

`test_markers.py` proves the helpers. The failure mode they cannot catch is a correct
guard nobody calls — so this runs `update.py` as a real subprocess against a stubbed
`claude_agent_sdk` whose `query` rewrites a marker block, exactly as an over-eager
learner would, and asserts the block came back. No network, no LLM, no API key.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PAYLOAD = ENGINE_DIR / "payload"

BLOCK = (
    "<!-- neurawork-cc-harness:rules BEGIN (auto-managed) -->\n"
    "### Coding Discipline\n"
    "\n"
    "- **Scope** — touch only what the request requires.\n"
    "<!-- neurawork-cc-harness:rules END -->"
)

DOC = f"""# CLAUDE.md

Some repo prose the learner owns.

{BLOCK}

Trailing prose.
"""

# STUB_REPO carries the repo root so the stub can find the file to vandalise
# (update.py parses argv, so an extra positional argument is not an option).
SDK_STUB = '''
import os
from pathlib import Path


class ClaudeAgentOptions:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class AssistantMessage:
    content = ()


class TextBlock:
    pass


class ResultMessage:
    total_cost_usd = 0.0


async def query(prompt=None, options=None):
    target = Path(os.environ["STUB_REPO"]) / "CLAUDE.md"
    text = target.read_text(encoding="utf-8")
    text = text.replace("- **Scope**", "- Scope, but I reworded it")
    text = text.replace("Trailing prose.", "Trailing prose.\\n\\n## Build\\n\\n`make test`")
    target.write_text(text, encoding="utf-8")
    yield ResultMessage()
'''


@unittest.skipUnless(shutil.which("git"), "git not available")
class GuardWiringTests(unittest.TestCase):
    def _stage(self, tmp: Path) -> tuple[Path, Path]:
        repo = tmp / "repo"
        lerner = repo / "lerner"
        (lerner / "scripts").mkdir(parents=True)
        (lerner / "daily").mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for name in ("update.py", "config.py", "utils.py", "markers.py"):
            shutil.copy2(PAYLOAD / "scripts" / name, lerner / "scripts" / name)
        shutil.copy2(PAYLOAD / "AGENTS.md", lerner / "AGENTS.md")
        shutil.copytree(ENGINE_DIR.parent / "_shared", lerner / "_shared",
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
        (lerner / "config.json").write_text(
            '{"claudemd_depth": 1, "docs_dir": "docs", "language": "en", '
            '"excluded_dirs": []}\n', encoding="utf-8")
        (lerner / "daily" / "2026-01-01.md").write_text(
            "# Daily Log: 2026-01-01\n\n## Sessions\n", encoding="utf-8")
        (repo / "CLAUDE.md").write_text(DOC, encoding="utf-8")

        stub_dir = tmp / "stub"
        stub_dir.mkdir()
        (stub_dir / "claude_agent_sdk.py").write_text(SDK_STUB, encoding="utf-8")
        return repo, stub_dir

    def _run_update(self, repo: Path, stub_dir: Path) -> subprocess.CompletedProcess:
        lerner = repo / "lerner"
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(stub_dir), str(lerner)]),
            "LERNER_ROOT": str(lerner),
            "STUB_REPO": str(repo),
        }
        return subprocess.run(
            [sys.executable, str(lerner / "scripts" / "update.py")],
            cwd=lerner, capture_output=True, text=True, env=env, timeout=60, check=False,
        )

    def test_update_run_restores_the_block_and_keeps_the_learning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, stub_dir = self._stage(Path(tmp))
            result = self._run_update(repo, stub_dir)
            self.assertEqual(result.returncode, 0, result.stderr)

            text = (repo / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn(BLOCK, text, "the guard is not wired into the update run")
            self.assertIn(
                "Marker guard:",
                result.stdout,
                "a restoration must be reported on stdout, not applied silently",
            )
            self.assertIn(
                "`make test`",
                text,
                "text outside the marker span is the learner's real work and must survive",
            )


if __name__ == "__main__":
    unittest.main()
