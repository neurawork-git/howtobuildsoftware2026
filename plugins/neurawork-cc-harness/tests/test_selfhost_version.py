"""Every self-host's VERSION must equal its engine's shipped VERSION.

This repo runs all four engines as live installs, so a release bump has to move two
files per engine: `engines/<engine>/VERSION` and `<self-host>/VERSION`. Miss the second
and `/nw-doctor` reports "installed N is behind the shipped N+1" against code that is
byte-identical to the payload — a false staleness finding whose fix (re-run the
installer) changes nothing. It has happened once already (PR #45, caught in review) and
the store-wiring work moved four of these files by hand, so nothing but this test stands
between a bump and the next silent mismatch.

The engine registry is the source of truth for which self-host belongs to which engine.
An engine whose default dir is absent is skipped rather than failed — but "no self-host
at all" is not the same fact: in this repo it means the walk found nothing where it
should have, so the test asserts it checked something, and skips only where there is
nothing to check by construction (a checkout that is not the plugin's source repo).
No LLM, no network.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import harness_probe as probe


class TestSelfHostVersion(unittest.TestCase):
    def test_every_self_host_carries_its_engine_version(self) -> None:
        if not (REPO_ROOT / "plugins" / PLUGIN_ROOT.name).is_dir():
            self.skipTest("not the plugin's source repo — no self-hosts to pin here")
        checked = []
        for name, engine in probe.ENGINES.items():
            self_host = REPO_ROOT / engine.default_dir
            if not (self_host / "VERSION").exists():
                continue  # not installed in this checkout
            shipped = (PLUGIN_ROOT / "engines" / name / "VERSION").read_text(
                encoding="utf-8").strip()
            installed = (self_host / "VERSION").read_text(encoding="utf-8").strip()
            self.assertEqual(
                installed, shipped,
                f"{engine.default_dir}/VERSION is {installed!r} but "
                f"engines/{name}/VERSION is {shipped!r} — bump both, or /nw-doctor "
                "reports a staleness that does not exist",
            )
            checked.append(name)
        self.assertTrue(checked, "no self-host found — the walk asserted nothing")


class TestSkipOutsideTheSourceRepo(unittest.TestCase):
    """The skip branch, which every run in this repo takes the other way past.

    Untested, it is the branch that would quietly swallow a wrong `REPO_ROOT`: the walk
    would skip instead of failing, and nothing would say the guard stopped guarding.
    """

    def _run(self, repo_root: Path) -> unittest.TestResult:
        module = sys.modules[TestSelfHostVersion.__module__]
        result = unittest.TestResult()
        original = module.REPO_ROOT
        module.REPO_ROOT = repo_root
        try:
            module.TestSelfHostVersion(
                "test_every_self_host_carries_its_engine_version").run(result)
        finally:
            module.REPO_ROOT = original
        return result

    def test_a_checkout_without_the_plugin_layout_skips(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp))
        self.assertEqual(len(result.skipped), 1, "the walk did not skip")
        self.assertEqual(result.failures, [])
        # errors, not only failures: a walk that blew up — `git` missing, a subprocess
        # raising outside a repo — raises rather than fails, and a check that looks at
        # skips and failures alone would read the crash as a pass.
        self.assertEqual(result.errors, [])

    def test_this_repo_does_not_skip(self) -> None:
        result = self._run(REPO_ROOT)
        self.assertEqual(result.skipped, [], "the walk skipped in its own source repo")
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
