"""Drift guard: the shipped payload must match this repo's own compliance-base/ self-host.

`install.py` propagates the payload into a self-host, but only when someone re-runs it:
a direct edit to `compliance-base/hooks/` still diverges silently. This test is what
keeps the two copies identical in between — a payload edit that is not mirrored, or a
self-host edit that never reaches the payload, fails here rather than shipping different
behaviour to installs than this repo runs.

`stack-compiler` has carried this guard since its self-host existed; compliance-compiler
did not, and the gap was real: the worktree-classification fix edited both hook copies by
hand, with nothing to catch a missed one. `_shared/` is deliberately out of scope (it is
not in `payload/` — the installer refreshes it), and so is `VERSION`, which the
plugin-root `test_selfhost_version.py` pins for every engine at once.

Skips gracefully when compliance-base/ is absent (a pure plugin checkout with no
self-host), so the test is a no-op there. No LLM, no network.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PAYLOAD = ENGINE_DIR / "payload"
FLAT_FILES = ("AGENTS.md", "pyproject.toml")


def _self_host() -> Path | None:
    for parent in ENGINE_DIR.parents:
        cand = parent / "compliance-base"
        if (cand / "scripts").is_dir():
            return cand
    return None


class TestPayloadDrift(unittest.TestCase):
    def setUp(self) -> None:
        target = _self_host()
        if target is None:
            self.skipTest("no compliance-base/ in this checkout")
        self.target: Path = target

    def _assert_tree_identical(self, subdir: str) -> None:
        """Compare the file *lists* first, then the bytes.

        The lists matter as much as the contents: a script or hook added to one side and
        not the other is exactly the drift this guard exists to catch, and a bytes-only
        comparison would pass it silently.
        """
        payload_files = sorted(p.name for p in (PAYLOAD / subdir).glob("*.py"))
        installed = sorted(p.name for p in (self.target / subdir).glob("*.py"))
        self.assertEqual(payload_files, installed,
                         f"payload/{subdir} and compliance-base/{subdir} hold different files")
        for name in payload_files:
            self.assertEqual((PAYLOAD / subdir / name).read_bytes(),
                             (self.target / subdir / name).read_bytes(),
                             f"{subdir}/{name} differs between payload and compliance-base")

    def test_scripts_are_identical(self) -> None:
        self._assert_tree_identical("scripts")

    def test_hooks_are_identical(self) -> None:
        self._assert_tree_identical("hooks")

    def test_flat_files_are_identical(self) -> None:
        for name in FLAT_FILES:
            self.assertEqual((PAYLOAD / name).read_bytes(),
                             (self.target / name).read_bytes(),
                             f"{name} differs between payload and compliance-base")


if __name__ == "__main__":
    unittest.main()
