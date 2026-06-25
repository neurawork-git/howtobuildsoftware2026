"""Stdlib tests for transcript.extract_turns: parsing, blocks, truncation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import transcript  # noqa: E402


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


class TestTranscript(unittest.TestCase):
    def test_string_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.jsonl"
            _write_jsonl(p, [
                {"message": {"role": "user", "content": "hello"}},
                {"message": {"role": "assistant", "content": "hi there"}},
            ])
            out = transcript.extract_turns(p)
            self.assertIn("**User:** hello", out)
            self.assertIn("**Assistant:** hi there", out)

    def test_block_content_and_role_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.jsonl"
            _write_jsonl(p, [
                {"message": {"role": "system", "content": "ignored"}},
                {"message": {"role": "assistant", "content": [
                    {"type": "text", "text": "block-a"},
                    {"type": "tool_use", "name": "x"},
                    {"type": "text", "text": "block-b"},
                ]}},
            ])
            out = transcript.extract_turns(p)
            self.assertNotIn("ignored", out)
            self.assertIn("block-a", out)
            self.assertIn("block-b", out)

    def test_truncation_keeps_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.jsonl"
            _write_jsonl(p, [
                {"message": {"role": "user", "content": "A" * 100}},
                {"message": {"role": "assistant", "content": "TAILMARKER"}},
            ])
            out = transcript.extract_turns(p, max_turns=30, max_chars=50)
            self.assertLessEqual(len(out), 50)
            self.assertIn("TAILMARKER", out)

    def test_max_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.jsonl"
            _write_jsonl(p, [{"message": {"role": "user", "content": f"m{i}"}} for i in range(10)])
            out = transcript.extract_turns(p, max_turns=3)
            self.assertNotIn("m6", out)
            self.assertIn("m9", out)

    def test_missing_file_returns_empty(self) -> None:
        self.assertEqual(transcript.extract_turns("/no/such/file.jsonl"), "")

    def test_skips_malformed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.jsonl"
            p.write_text('{"message": {"role": "user", "content": "ok"}}\nNOT JSON\n', encoding="utf-8")
            out = transcript.extract_turns(p)
            self.assertIn("ok", out)


if __name__ == "__main__":
    unittest.main()
