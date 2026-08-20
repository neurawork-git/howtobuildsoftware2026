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

    def test_prose_mentioning_a_marker_does_not_swallow_the_real_block(self) -> None:
        # Documentation writes `<!-- owner:name BEGIN/END -->` inline; that text matches
        # the BEGIN pattern. Paired naively with the real block's END it would put every
        # line in between under protection, and the guard would then revert all of it.
        text = (
            "# CLAUDE.md\n\nThe rules live in one `<!-- neurawork-cc-harness:rules "
            "BEGIN/END -->` block.\n\nA long stretch of prose the learner owns.\n\n"
            + BLOCK
            + "\n"
        )
        spans = markers.find_spans(text)
        self.assertEqual(len(spans), 1, "the doc mention must not open a span")
        _, start, end = spans[0]
        self.assertEqual(text[start:end], BLOCK)
        self.assertNotIn(
            "prose the learner owns",
            text[start:end],
            "a span reaching back to the doc mention would freeze unrelated prose",
        )
        self.assertEqual(
            markers.unmatched_ids(text),
            ["neurawork-cc-harness:rules"],
            "the unpaired mention is still worth reporting, even though a real block "
            "with the same id exists further down",
        )

    def test_the_guarded_docs_of_this_repo_carry_no_unpaired_marker(self) -> None:
        # This repo documents its own marker id, and the learner guards exactly these
        # files. A BEGIN-shaped mention here would build the trap above in the very repo
        # that ships the guard.
        repo_root = Path(__file__).resolve().parents[5]
        if not (repo_root / "CLAUDE.md").is_file():
            self.skipTest("not running inside the harness repo")
        guarded = [repo_root / "CLAUDE.md", *sorted((repo_root / "docs").glob("*.md"))]
        for path in guarded:
            with self.subTest(file=path.name):
                self.assertEqual(
                    markers.unmatched_ids(path.read_text(encoding="utf-8")),
                    [],
                    f"{path} contains an unpaired marker BEGIN — spell marker ids out in "
                    "prose instead of using the comment syntax",
                )


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

    def test_half_deleted_block_is_reported_not_duplicated(self) -> None:
        # The END comment dropped: the reworded body is still in the file. Re-appending
        # the snapshot would leave the rule text twice over.
        snap = self._snapshot()
        broken = DOC.replace("<!-- neurawork-cc-harness:rules END -->\n", "")
        self.path.write_text(broken, encoding="utf-8")
        messages = markers.restore(snap)
        self.assertEqual(len(messages), 1)
        self.assertIn("unpaired BEGIN", messages[0])
        text = self.path.read_text(encoding="utf-8")
        self.assertEqual(text, broken, "a broken block is reported, never rewritten")
        self.assertEqual(text.count("### Coding Discipline"), 1, "must not duplicate")

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
