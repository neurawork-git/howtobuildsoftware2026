"""The learner must RUN the way production runs it, and only stamp real progress.

`test_markers_wiring.py` puts the install dir on `PYTHONPATH`, which is exactly what
`update.py`'s missing `sys.path` bootstrap should supply — so it stayed green while
every real invocation died at import. These tests run `update.py` as the hook does:
plain `python scripts/update.py` from the install dir, with nothing helping the import.

They also pin the stamp contract: `last-update.json` shuts the SessionStart gate for
`update_age_hours`, so a run that ingested nothing must leave it alone. No network,
no LLM, no API key.
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
PAYLOAD = ENGINE_DIR / "payload"
SELF_HOST = ENGINE_DIR.parents[3] / "claudemd-lerner"

# Two stubs, one shape: `query` either edits nothing and completes, or raises. The
# learner's own bookkeeping (state.json, last-update.json) is what is under test.
STUB_OK = '''
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
    yield ResultMessage()
'''

STUB_FAILS = '''
import os


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
    if os.environ.get("STUB_FAIL_ONLY") in (None, "", prompt_log(prompt)):
        raise RuntimeError("the SDK blew up")
    yield ResultMessage()


def prompt_log(prompt):
    """The daily log file name this prompt carries (the stub's only way to tell them
    apart — update.py passes one log per call)."""
    for line in (prompt or "").splitlines():
        if line.startswith("## Session Daily Log to Apply — "):
            return line.rsplit("— ", 1)[1].strip()
    return ""
'''


class UpdateRuntimeTests(unittest.TestCase):
    def _stage(self, tmp: Path, stub: str, logs: tuple[str, ...] = ("2026-01-01.md",)) -> Path:
        """A lerner install carrying only what `update.py` imports at run time."""
        repo = tmp / "repo"
        lerner = repo / "lerner"
        (lerner / "scripts").mkdir(parents=True)
        (lerner / "daily").mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

        for name in ("update.py", "config.py", "utils.py", "markers.py"):
            shutil.copy2(PAYLOAD / "scripts" / name, lerner / "scripts" / name)
        shutil.copy2(PAYLOAD / "AGENTS.md", lerner / "AGENTS.md")
        shutil.copytree(ENGINE_DIR.parent / "_shared", lerner / "_shared",
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
        (lerner / "config.json").write_text(
            '{"claudemd_depth": 1, "docs_dir": "docs", "language": "en", '
            '"excluded_dirs": []}\n', encoding="utf-8")
        for name in logs:
            (lerner / "daily" / name).write_text(
                f"# Daily Log: {name[:-3]}\n\n## Sessions\n", encoding="utf-8")
        (repo / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")

        stub_dir = tmp / "stub"
        stub_dir.mkdir()
        (stub_dir / "claude_agent_sdk.py").write_text(stub, encoding="utf-8")
        return lerner

    def _run(self, lerner: Path, *args: str, **env_extra: str) -> subprocess.CompletedProcess:
        """Invoke exactly as `cl-session-start.py` does: `python scripts/update.py`
        from the install dir. Only the SDK stub is on PYTHONPATH — never the install
        dir, whose absence is the defect under test."""
        env = {
            **os.environ,
            "PYTHONPATH": str(lerner.parent.parent / "stub"),
            "LERNER_ROOT": str(lerner),
        }
        env.pop("ANTHROPIC_API_KEY", None)
        env.update(env_extra)
        return subprocess.run(
            [sys.executable, "scripts/update.py", *args],
            cwd=lerner, capture_output=True, text=True, env=env, timeout=60, check=False,
        )

    def _stamp(self, lerner: Path) -> Path:
        return lerner / "scripts" / "last-update.json"

    def _state(self, lerner: Path) -> dict:
        path = lerner / "scripts" / "state.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    # ── Task 1 — it starts at all ──────────────────────────────────────

    def test_update_runs_without_the_install_dir_on_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lerner = self._stage(Path(tmp), STUB_OK)
            result = self._run(lerner, "--dry-run")
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("2026-01-01.md", result.stdout)

    def test_the_hooks_exact_command_starts(self) -> None:
        # `cl-session-start.py` spawns `python scripts/update.py --all`. A crash there
        # is invisible to the hook, so it must be proved here.
        with tempfile.TemporaryDirectory() as tmp:
            lerner = self._stage(Path(tmp), STUB_OK)
            result = self._run(lerner, "--all")
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_payload_and_self_host_copies_do_not_drift(self) -> None:
        # No installer runs between edits; only this assertion stops one copy from
        # being fixed while the other stays broken.
        if not SELF_HOST.is_dir():
            self.skipTest("no self-host install in this checkout")
        for rel in ("scripts/update.py", "hooks/cl-session-start.py"):
            with self.subTest(rel=rel):
                self.assertEqual(
                    (PAYLOAD / rel).read_bytes(),
                    (SELF_HOST / rel).read_bytes(),
                    f"{rel} differs between the shipped payload and the self-host install",
                )

    # ── Task 2 — the stamp means progress ──────────────────────────────

    def test_a_run_where_every_log_errors_leaves_the_stamp_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lerner = self._stage(Path(tmp), STUB_FAILS)
            result = self._run(lerner, "--all")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                self._stamp(lerner).exists(),
                "stamping a failed run shuts the 6-hour gate over work that never happened",
            )
            self.assertEqual(self._state(lerner).get("ingested", {}), {})

    def test_one_success_among_failures_stamps_and_records_only_that_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lerner = self._stage(
                Path(tmp), STUB_FAILS, logs=("2026-01-01.md", "2026-01-02.md")
            )
            result = self._run(lerner, "--all", STUB_FAIL_ONLY="2026-01-01.md")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(self._stamp(lerner).exists(), result.stdout)
            self.assertEqual(
                sorted(self._state(lerner).get("ingested", {})), ["2026-01-02.md"]
            )

    # ── Task 3 — the failure leaves a trace ────────────────────────────

    def test_the_session_start_hook_does_not_discard_the_childs_output(self) -> None:
        source = (PAYLOAD / "hooks" / "cl-session-start.py").read_text(encoding="utf-8")
        self.assertIn("update.log", source)
        self.assertNotIn(
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL",
            source,
            "a detached child with both streams at /dev/null is why the import crash "
            "survived undetected",
        )

    def test_the_hook_survives_a_log_that_cannot_be_opened(self) -> None:
        # `update.log` occupied by a DIRECTORY: the open fails. Logging is an
        # observability nicety — it must never be the reason the gate stops firing, so
        # the proof is that the spawn still happened, not merely that the hook exited 0
        # (`main()` swallows every exception, so the exit code alone proves nothing).
        with tempfile.TemporaryDirectory() as tmp:
            lerner = self._stage(Path(tmp), STUB_OK)
            (lerner / "hooks").mkdir()
            shutil.copy2(PAYLOAD / "hooks" / "cl-session-start.py",
                         lerner / "hooks" / "cl-session-start.py")
            (lerner / "scripts" / "update.log").mkdir()

            # A stub `uv` so the spawn is observable without a real detached run
            # building a venv in a temp dir that is about to be deleted.
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            stub_uv = bin_dir / "uv"
            stub_uv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            stub_uv.chmod(0o755)

            env = {
                **os.environ,
                "LERNER_ROOT": str(lerner),
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            result = subprocess.run(
                [sys.executable, "hooks/cl-session-start.py"],
                cwd=lerner, capture_output=True, text=True, env=env, timeout=60,
                input="{}", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (lerner / "scripts" / "cl-update.lock").exists(),
                "the gate did not fire — an unopenable log must not stop the spawn",
            )


if __name__ == "__main__":
    unittest.main()
