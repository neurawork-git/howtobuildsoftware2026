"""Stdlib tests for the shared engine registry and install discovery.

The registry is the single source of truth both `hooks/version-check.py` and
`scripts/doctor.py` read; these pin the properties whose loss is silent — an engine
that stops being discoverable, a hook/dir disagreement that stops being visible, and
a partial copy that starts counting as an install.

Temp repos only: the live self-host state changes as soon as the stall it exhibits is
fixed, so it is validation evidence, never a fixture. No network, no LLM.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import harness_probe as probe  # noqa: E402


def _settings(*commands: str) -> dict:
    """A settings.json holding one SessionStart group with the given hook commands."""
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": c, "timeout": 15}
                        for c in commands
                    ],
                }
            ]
        }
    }


def _hook_cmd(dirname: str, script: str) -> str:
    return f'uv run --directory "$CLAUDE_PROJECT_DIR/{dirname}" python {script}'


def _install_dir(root: Path, dirname: str, engine: str) -> Path:
    """Materialise both signature files of `engine` under `root/dirname`."""
    target = root / dirname
    for rel in probe.ENGINES[engine].signature:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stub\n", encoding="utf-8")
    return target


class RegistryTests(unittest.TestCase):
    def test_every_engine_has_a_shipped_payload(self) -> None:
        for name in probe.ENGINES:
            with self.subTest(engine=name):
                self.assertTrue(
                    (PLUGIN_ROOT / "engines" / name / "payload").is_dir(),
                    "a registry entry naming an engine that ships no payload makes every "
                    "integrity check for it vacuous",
                )

    def test_payload_files_are_read_from_the_shipped_payload(self) -> None:
        files = probe.payload_files(PLUGIN_ROOT, "knowledge-compiler")
        self.assertIn("hooks/session-start.py", files)
        self.assertIn("scripts/compile.py", files)
        self.assertIn("pyproject.toml", files)
        self.assertIn("AGENTS.md", files)

    def test_hook_markers_do_not_collide_across_engines(self) -> None:
        # "hooks/session-start.py" must not match the lerner's "hooks/cl-session-start.py",
        # or one engine's install dir is attributed to the other.
        markers = [
            (name, marker)
            for name, engine in probe.ENGINES.items()
            for marker in engine.hooks.values()
        ]
        for name, marker in markers:
            for other_name, other in markers:
                if name == other_name or marker == other:
                    continue
                with self.subTest(marker=marker, other=other):
                    self.assertNotIn(marker, other)


class CompareTests(unittest.TestCase):
    def test_behind(self) -> None:
        self.assertEqual(probe.compare("1", "2"), "behind")

    def test_same(self) -> None:
        self.assertEqual(probe.compare("2", "2"), "same")

    def test_ahead(self) -> None:
        self.assertEqual(probe.compare("3", "2"), "ahead")

    def test_unreadable(self) -> None:
        self.assertEqual(probe.compare(None, "2"), "unknown")

    def test_non_numeric_difference_is_unorderable(self) -> None:
        self.assertEqual(probe.compare("a", "b"), "unknown")


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _one(self, installs: list, engine: str):
        matches = [i for i in installs if i.engine == engine]
        self.assertEqual(len(matches), 1, f"{engine} not discovered exactly once")
        return matches[0]

    def test_renamed_dir_is_read_back_from_the_hook(self) -> None:
        _install_dir(self.root, "my-kb", "knowledge-compiler")
        settings = _settings(_hook_cmd("my-kb", "hooks/session-start.py"))
        install = self._one(probe.discover(self.root, settings), "knowledge-compiler")
        self.assertEqual(install.dirname, "my-kb")
        self.assertEqual(install.found_by, "both")
        self.assertTrue(install.signature_ok)

    def test_dir_without_hook_is_installed_but_not_wired(self) -> None:
        _install_dir(self.root, "claudemd-lerner", "claudemd-lerner")
        install = self._one(probe.discover(self.root, {}), "claudemd-lerner")
        self.assertEqual(install.found_by, "dir")
        self.assertEqual(
            sorted(install.missing_events),
            sorted(probe.ENGINES["claudemd-lerner"].hooks),
        )

    def test_hook_pointing_at_a_missing_dir_is_orphaned(self) -> None:
        settings = _settings(_hook_cmd("gone", "hooks/session-start.py"))
        install = self._one(probe.discover(self.root, settings), "knowledge-compiler")
        self.assertEqual(install.found_by, "hook")
        self.assertEqual(install.dirname, "gone")
        self.assertFalse(install.signature_ok)

    def test_engine_without_a_wired_hook_is_found_by_signature_alone(self) -> None:
        _install_dir(self.root, "stack-base", "stack-compiler")
        install = self._one(probe.discover(self.root, {}), "stack-compiler")
        self.assertEqual(install.found_by, "dir")
        self.assertEqual(install.dirname, "stack-base")

    def test_partial_copy_is_not_an_install(self) -> None:
        first = probe.ENGINES["knowledge-compiler"].signature[0]
        path = self.root / "half-kb" / first
        path.parent.mkdir(parents=True)
        path.write_text("# stub\n", encoding="utf-8")
        self.assertEqual(probe.discover(self.root, {}), [])

    def test_dot_dirs_are_never_scanned(self) -> None:
        _install_dir(self.root, ".hidden", "knowledge-compiler")
        self.assertEqual(probe.discover(self.root, {}), [])

    def test_partially_wired_install_reports_only_the_missing_events(self) -> None:
        _install_dir(self.root, "knowledge-base", "knowledge-compiler")
        settings = _settings(_hook_cmd("knowledge-base", "hooks/session-start.py"))
        install = self._one(probe.discover(self.root, settings), "knowledge-compiler")
        self.assertEqual(install.found_by, "both")
        self.assertNotIn("SessionStart", install.missing_events)
        self.assertIn("SessionEnd", install.missing_events)


class FindStaleTests(unittest.TestCase):
    """`find_stale` backs the SessionStart nudge, which may only name a real installer."""

    def test_every_engine_that_ships_an_installer_is_nudgeable(self) -> None:
        for name, engine in probe.ENGINES.items():
            with self.subTest(engine=name):
                has_installer = (
                    PLUGIN_ROOT / "engines" / name / "install.py"
                ).is_file()
                self.assertEqual(
                    bool(engine.install_skill),
                    has_installer,
                    "the nudge's whole payload is `re-run /neurawork-cc-harness:<engine>`: "
                    "an engine with an installer that is not nudgeable never tells anyone "
                    "to upgrade, and one without would name a command that does not exist",
                )


if __name__ == "__main__":
    unittest.main()
