"""Behaviour tests for the marker-block guard. Pure text/file work, no LLM/network."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import markers

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


class SpanDetection(unittest.TestCase):
    def test_span_covers_the_marker_comments_themselves(self) -> None:
        spans = markers.find_spans(DOC)
        self.assertEqual(len(spans), 1)
        marker_id, start, end = spans[0]
        self.assertEqual(marker_id, "neurawork-cc-harness:rules")
        self.assertEqual(
            DOC[start:end],
            BLOCK,
            "a span that excludes the BEGIN/END comments leaves the markers rewritable",
        )

    def test_begin_without_end_is_not_a_span(self) -> None:
        text = "<!-- a:b BEGIN -->\nbody with no end\n"
        self.assertEqual(markers.find_spans(text), [])
        self.assertEqual(
            markers.unmatched_ids(text),
            ["a:b"],
            "an unclosed marker must be reported, never guessed at",
        )

    def test_two_ids_in_one_file_are_separate_spans(self) -> None:
        text = (
            "<!-- one:x BEGIN -->\nA\n<!-- one:x END -->\n\n"
            "<!-- two:y BEGIN -->\nB\n<!-- two:y END -->\n"
        )
        self.assertEqual([s[0] for s in markers.find_spans(text)], ["one:x", "two:y"])


class GuardBehaviour(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "CLAUDE.md"
        self.path.write_text(DOC, encoding="utf-8")
        self.addCleanup(self.tmp.cleanup)

    def _snapshot(self) -> dict:
        return markers.snapshot([self.path])

    def test_untouched_file_is_a_silent_no_op(self) -> None:
        snap = self._snapshot()
        self.assertEqual(markers.restore(snap), [])
        self.assertEqual(self.path.read_text(encoding="utf-8"), DOC)

    def test_edited_block_is_restored_and_reported(self) -> None:
        snap = self._snapshot()
        self.path.write_text(
            DOC.replace("- **Scope** — touch only what the request requires.",
                        "- Scope: edit freely, I improved the wording."),
            encoding="utf-8",
        )
        messages = markers.restore(snap)
        self.assertEqual(len(messages), 1)
        self.assertIn("was edited", messages[0])
        self.assertEqual(self.path.read_text(encoding="utf-8"), DOC)

    def test_rewritten_begin_comment_is_restored(self) -> None:
        snap = self._snapshot()
        self.path.write_text(
            DOC.replace("BEGIN (auto-managed)", "BEGIN"), encoding="utf-8"
        )
        messages = markers.restore(snap)
        self.assertEqual(len(messages), 1)
        self.assertEqual(self.path.read_text(encoding="utf-8"), DOC)

    def test_deleted_block_is_re_appended(self) -> None:
        snap = self._snapshot()
        self.path.write_text(DOC.replace(BLOCK + "\n\n", ""), encoding="utf-8")
        messages = markers.restore(snap)
        self.assertEqual(len(messages), 1)
        self.assertIn("was removed", messages[0])
        self.assertIn(BLOCK, self.path.read_text(encoding="utf-8"))

    def test_learning_outside_the_span_survives(self) -> None:
        snap = self._snapshot()
        learned = DOC.replace("Trailing prose.", "Trailing prose.\n\n## Build\n\n`make test`")
        self.path.write_text(learned, encoding="utf-8")
        self.assertEqual(
            markers.restore(snap),
            [],
            "an unchanged block must not trigger a write that could roll back real learning",
        )
        self.assertEqual(
            self.path.read_text(encoding="utf-8"),
            learned,
            "the guard must never restore anything outside the marker span",
        )

    def test_edited_block_restores_without_discarding_learning(self) -> None:
        snap = self._snapshot()
        both = DOC.replace("- **Scope** — touch only what the request requires.", "- reworded")
        both = both.replace("Trailing prose.", "Trailing prose.\n\n## Build\n\n`make test`")
        self.path.write_text(both, encoding="utf-8")
        markers.restore(snap)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn(BLOCK, text)
        self.assertIn("`make test`", text)

    def test_only_the_touched_id_is_restored(self) -> None:
        two = (
            "<!-- one:x BEGIN -->\nA\n<!-- one:x END -->\n\n"
            "<!-- two:y BEGIN -->\nB\n<!-- two:y END -->\n"
        )
        self.path.write_text(two, encoding="utf-8")
        snap = self._snapshot()
        self.path.write_text(two.replace("\nB\n", "\nB changed\n"), encoding="utf-8")
        messages = markers.restore(snap)
        self.assertEqual(len(messages), 1)
        self.assertIn("two:y", messages[0])
        self.assertEqual(self.path.read_text(encoding="utf-8"), two)

    def test_duplicated_block_is_reported_not_silently_accepted(self) -> None:
        snap = self._snapshot()
        self.path.write_text(DOC + "\n" + BLOCK + "\n", encoding="utf-8")
        messages = markers.restore(snap)
        self.assertTrue(any("appears 2 times" in m for m in messages))

    def test_missing_file_is_skipped_not_raised(self) -> None:
        snap = markers.snapshot([self.path, Path(self.tmp.name) / "nope.md"])
        self.assertEqual(list(snap), [self.path])

    def test_file_without_markers_is_not_snapshotted(self) -> None:
        plain = Path(self.tmp.name) / "docs.md"
        plain.write_text("# Just prose\n", encoding="utf-8")
        self.assertEqual(markers.snapshot([plain]), {})


if __name__ == "__main__":
    unittest.main()
