"""The Node nudge's engine map must not drift from the Python registry.

`scripts/harness_probe.py` is the single source of truth for which engines exist and
which installed hook command locates each one. `hooks/version-check.js` cannot import
it — a Node hook has no way to read a Python module — so it carries a second copy.

That copy is the exact defect the probe was extracted to end: the map lived only in
the nudge and had already fallen a whole engine behind reality. These tests are the
price of reintroducing a copy. They fail when an engine or a marker is registered on
one side only, which is the only way the two can diverge.

Text-parsed, not executed: the guard has to hold in a checkout with no Node installed.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import harness_probe as probe  # noqa: E402

HOOK_JS = PLUGIN_ROOT / "hooks" / "version-check.js"

_BLOCK_RE = re.compile(r"^const ENGINES = \{$(.*?)^\};$", re.DOTALL | re.MULTILINE)
_ENTRY_RE = re.compile(r'"([^"]+)":\s*\[(.*?)\]', re.DOTALL)
_STRING_RE = re.compile(r'"([^"]+)"')


def parse_js_engines() -> dict[str, list[str]]:
    """Return the `ENGINES` object literal of version-check.js as a dict."""
    block = _BLOCK_RE.search(HOOK_JS.read_text(encoding="utf-8"))
    assert block, "version-check.js has no top-level `const ENGINES = {…};` block"
    return {
        name: _STRING_RE.findall(markers)
        for name, markers in _ENTRY_RE.findall(block.group(1))
    }


def installable_engines() -> dict[str, list[str]]:
    """The probe's registry, reduced to what the nudge can act on.

    `find_stale` skips an engine with no `install_skill` — the note's whole payload is
    "re-run /neurawork-cc-harness:<engine>", and naming a command that does not exist
    is worse than silence. The JS map must mirror that same subset.
    """
    return {
        name: sorted(engine.hooks.values())
        for name, engine in probe.ENGINES.items()
        if engine.install_skill
    }


class TestVersionCheckRegistry(unittest.TestCase):
    def test_js_map_parses(self):
        self.assertTrue(parse_js_engines(), "no engines parsed out of version-check.js")

    def test_same_engines_on_both_sides(self):
        self.assertEqual(
            sorted(parse_js_engines()),
            sorted(installable_engines()),
            "version-check.js and harness_probe.ENGINES disagree on which engines exist",
        )

    def test_same_markers_per_engine(self):
        js = parse_js_engines()
        for engine, markers in installable_engines().items():
            with self.subTest(engine=engine):
                self.assertEqual(
                    sorted(js.get(engine, [])),
                    markers,
                    f"hook markers for {engine} differ between the JS map and the probe",
                )

    def test_markers_are_unique_across_engines(self):
        """A marker that matches two engines would attribute an install to the wrong one."""
        seen: dict[str, str] = {}
        for engine, markers in parse_js_engines().items():
            for marker in markers:
                self.assertNotIn(marker, seen, f"{marker} claimed by {seen.get(marker)} and {engine}")
                seen[marker] = engine

    def test_no_marker_is_a_substring_of_another(self):
        """`hooks/session-start.py` must not match the lerner's `hooks/cl-session-start.py`."""
        all_markers = [m for markers in parse_js_engines().values() for m in markers]
        for a in all_markers:
            for b in all_markers:
                if a != b:
                    self.assertNotIn(a, b, f"{a} is a substring of {b}")


if __name__ == "__main__":
    unittest.main()
