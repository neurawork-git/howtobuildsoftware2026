"""Stdlib tests for the plugin-level version-check staleness nudge."""

from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

# version-check.py lives in the plugin's hooks/ dir (hyphenated filename → load by path).
_VC_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "hooks" / "version-check.py"
)
_spec = importlib.util.spec_from_file_location("version_check", _VC_PATH)
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)


def _settings(dirname: str, marker: str) -> dict:
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'uv run --directory "$CLAUDE_PROJECT_DIR/{dirname}" python {marker}',
                            "timeout": 15,
                        }
                    ],
                }
            ]
        }
    }


class TestInstalledDirFor(unittest.TestCase):
    def test_default_dir(self) -> None:
        s = _settings("knowledge-base", "hooks/session-start.py")
        self.assertEqual(vc.installed_dir_for(s, "hooks/session-start.py"), "knowledge-base")

    def test_renamed_dir(self) -> None:
        s = _settings("my-kb", "hooks/session-start.py")
        self.assertEqual(vc.installed_dir_for(s, "hooks/session-start.py"), "my-kb")

    def test_missing_marker(self) -> None:
        s = _settings("knowledge-base", "hooks/session-start.py")
        self.assertIsNone(vc.installed_dir_for(s, "hooks/co-post-tooluse.py"))

    def test_no_hooks(self) -> None:
        self.assertIsNone(vc.installed_dir_for({}, "hooks/session-start.py"))


class TestIsBehind(unittest.TestCase):
    def test_int_behind(self) -> None:
        self.assertTrue(vc.is_behind("1", "2"))

    def test_int_current(self) -> None:
        self.assertFalse(vc.is_behind("2", "2"))

    def test_int_ahead(self) -> None:
        self.assertFalse(vc.is_behind("2", "1"))

    def test_non_int_differs(self) -> None:
        self.assertTrue(vc.is_behind("a", "b"))

    def test_non_int_equal(self) -> None:
        self.assertFalse(vc.is_behind("a", "a"))


class TestFindStale(unittest.TestCase):
    def _setup(self, installed: str, shipped: str):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        repo = root / "repo"
        plugin = root / "plugin"
        (repo / "knowledge-base").mkdir(parents=True)
        (repo / "knowledge-base" / "VERSION").write_text(installed)
        (plugin / "engines" / "knowledge-compiler").mkdir(parents=True)
        (plugin / "engines" / "knowledge-compiler" / "VERSION").write_text(shipped)
        settings = _settings("knowledge-base", "hooks/session-start.py")
        return tmp, repo, plugin, settings

    def test_stale_detected(self) -> None:
        tmp, repo, plugin, settings = self._setup("1", "2")
        with tmp:
            stale = vc.find_stale(repo, plugin, settings)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["engine"], "knowledge-compiler")
            self.assertEqual(stale[0]["dir"], "knowledge-base")
            self.assertEqual((stale[0]["installed"], stale[0]["shipped"]), ("1", "2"))

    def test_stale_stack_compiler_detected(self) -> None:
        # The fourth engine only reaches the nudge once it has an installer to name:
        # find_stale skips any engine with no install_skill.
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            root = Path(tmp.name)
            repo, plugin = root / "repo", root / "plugin"
            (repo / "stack-base").mkdir(parents=True)
            (repo / "stack-base" / "VERSION").write_text("1")
            (plugin / "engines" / "stack-compiler").mkdir(parents=True)
            (plugin / "engines" / "stack-compiler" / "VERSION").write_text("2")
            settings = _settings("stack-base", "hooks/st-post-tooluse.py")

            stale = vc.find_stale(repo, plugin, settings)
            self.assertEqual(len(stale), 1)
            self.assertEqual(stale[0]["engine"], "stack-compiler")
            self.assertEqual(stale[0]["dir"], "stack-base")

    def test_current_no_stale(self) -> None:
        tmp, repo, plugin, settings = self._setup("2", "2")
        with tmp:
            self.assertEqual(vc.find_stale(repo, plugin, settings), [])

    def test_missing_installed_version_skipped(self) -> None:
        tmp, repo, plugin, settings = self._setup("1", "2")
        with tmp:
            (repo / "knowledge-base" / "VERSION").unlink()
            self.assertEqual(vc.find_stale(repo, plugin, settings), [])

    def test_no_install_silent(self) -> None:
        tmp, repo, plugin, _ = self._setup("1", "2")
        with tmp:
            self.assertEqual(vc.find_stale(repo, plugin, {"hooks": {}}), [])


class TestMainNoop(unittest.TestCase):
    def test_no_env_no_output(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            buf = io.StringIO()
            with redirect_stdout(buf):
                vc.main()
            self.assertEqual(buf.getvalue(), "")

    def test_stale_prints_context(self) -> None:
        tmp, repo, plugin, settings = TestFindStale()._setup("1", "2")
        with tmp:
            (repo / ".claude").mkdir()
            (repo / ".claude" / "settings.json").write_text(json.dumps(settings))
            env = {"CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_PLUGIN_ROOT": str(plugin)}
            with mock.patch.dict("os.environ", env, clear=True):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    vc.main()
            out = json.loads(buf.getvalue())
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertIn("knowledge-compiler", ctx)
            self.assertIn("/neurawork-cc-harness:knowledge-compiler", ctx)


if __name__ == "__main__":
    unittest.main()
