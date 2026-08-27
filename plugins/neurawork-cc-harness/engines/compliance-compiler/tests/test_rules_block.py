"""Pure-logic tests for the `neurawork-cc-harness:rules` block reader. No LLM, no SDK."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import rules_block  # noqa: E402

BEGIN = "<!-- neurawork-cc-harness:rules BEGIN (auto-managed — re-run to refresh) -->"
END = "<!-- neurawork-cc-harness:rules END -->"


def claudemd(body: str, *, before: str = "# CLAUDE.md\n\nprose\n\n") -> str:
    return f"{before}{BEGIN}\n{body}{END}\n"


BULLET = (
    "### Coding Discipline\n\n"
    "- **Evaluation first** — a behaviour change starts with a failing test. Run:\n\n"
)


class TestTestCommands(unittest.TestCase):
    def test_three_line_fence_yields_three_commands_in_order(self) -> None:
        text = claudemd(
            BULLET + "```sh\nmake test\npytest tests/unit\nnpm test\n```\n"
        )
        self.assertEqual(
            rules_block.test_commands(text), ["make test", "pytest tests/unit", "npm test"]
        )

    def test_bullet_without_a_fence_yields_nothing(self) -> None:
        # The documented state when Stage 1 detected no runner and the user declined
        # to name one: the bullet ships, the command slot does not.
        text = claudemd(
            "### Coding Discipline\n\n- **Evaluation first** — start with a failing test.\n"
        )
        self.assertEqual(rules_block.test_commands(text), [])

    def test_no_marker_block_at_all_yields_nothing(self) -> None:
        self.assertEqual(
            rules_block.test_commands("# CLAUDE.md\n\n```sh\nmake test\n```\n"), []
        )

    def test_fence_outside_the_span_is_ignored(self) -> None:
        # A repo's own prose fences sit above the block far more often than not.
        text = claudemd(BULLET + "```sh\nmake test\n```\n",
                        before="# CLAUDE.md\n\n```sh\nnot-the-gate\n```\n\n")
        self.assertEqual(rules_block.test_commands(text), ["make test"])

    def test_two_fences_inside_the_span_take_the_first(self) -> None:
        text = claudemd(BULLET + "```sh\nmake test\n```\n\nnote:\n\n```sh\nmake docs\n```\n")
        self.assertEqual(rules_block.test_commands(text), ["make test"])

    def test_language_tag_and_trailing_whitespace_are_handled(self) -> None:
        text = claudemd(BULLET + "```bash   \n  make test  \n\n```\n")
        self.assertEqual(rules_block.test_commands(text), ["make test"])

    def test_empty_fence_yields_nothing(self) -> None:
        self.assertEqual(rules_block.test_commands(claudemd(BULLET + "```sh\n```\n")), [])

    def test_unpaired_begin_is_not_a_span(self) -> None:
        # Mirrors the learner guard: guessing the extent could swallow the whole file.
        text = f"# CLAUDE.md\n\n{BEGIN}\n{BULLET}```sh\nmake test\n```\n"
        self.assertIsNone(rules_block.find_block(text))
        self.assertEqual(rules_block.test_commands(text), [])


class TestRead(unittest.TestCase):
    def test_reads_the_repo_root_claudemd(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "CLAUDE.md").write_text(
                claudemd(BULLET + "```sh\nmake test\n```\n"), encoding="utf-8"
            )
            self.assertEqual(rules_block.read(root), ["make test"])

    def test_absent_claudemd_returns_empty_rather_than_raising(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(rules_block.read(Path(t)), [])


class TestShippedTemplate(unittest.TestCase):
    """The reader must parse the block the skill actually writes — not a fixture of it."""

    def test_the_nw_rules_init_template_round_trips(self) -> None:
        skill = None
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "skills" / "nw-rules-init" / "SKILL.md"
            if candidate.exists():
                skill = candidate
                break
        if skill is None:
            self.skipTest("nw-rules-init skill not found next to this engine")
        import re

        blocks = re.findall(
            r"````markdown\n(.*?)\n````", skill.read_text(encoding="utf-8"), re.DOTALL
        )
        templates = [b for b in blocks if "neurawork-cc-harness:rules BEGIN" in b]
        self.assertEqual(len(templates), 1)
        rendered = templates[0].replace("<TEST_COMMAND>", "make test\nmake lint")
        self.assertEqual(rules_block.test_commands(rendered), ["make test", "make lint"])


if __name__ == "__main__":
    unittest.main()
