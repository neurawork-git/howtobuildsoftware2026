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


if __name__ == "__main__":
    unittest.main()
