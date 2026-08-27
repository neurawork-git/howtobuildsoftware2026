"""Stdlib tests for settings.merge_hooks idempotency + non-clobber."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import settings  # noqa: E402

HOOK = ("SessionEnd", "python3 .claude/nw/end.py", 10, "nw/end.py")


class TestMergeHooks(unittest.TestCase):
    def test_creates_file_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            changed = settings.merge_hooks(tmp, [HOOK])
            self.assertTrue(changed)
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            entries = data["hooks"]["SessionEnd"][0]["hooks"]
            self.assertEqual(entries[0]["command"], HOOK[1])
            self.assertEqual(entries[0]["timeout"], 10)

    def test_idempotent_second_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(settings.merge_hooks(tmp, [HOOK]))
            self.assertFalse(settings.merge_hooks(tmp, [HOOK]))
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            # No duplicate hook entry.
            entries = [h for g in data["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)

    def test_preserves_unrelated_hooks_and_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text(json.dumps({
                "model": "opus",
                "hooks": {"SessionEnd": [
                    {"matcher": "", "hooks": [
                        {"type": "command", "command": "other.py", "timeout": 5}
                    ]}
                ]},
            }))
            settings.merge_hooks(tmp, [HOOK])
            data = json.loads(sp.read_text())
            self.assertEqual(data["model"], "opus")
            cmds = [h["command"] for g in data["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertIn("other.py", cmds)
            self.assertIn(HOOK[1], cmds)

    def test_migrates_drifted_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text(json.dumps({"hooks": {"SessionEnd": [
                {"matcher": "", "hooks": [
                    {"type": "command", "command": "old/nw/end.py", "timeout": 99}
                ]}
            ]}}))
            self.assertTrue(settings.merge_hooks(tmp, [HOOK]))
            data = json.loads(sp.read_text())
            hook = data["hooks"]["SessionEnd"][0]["hooks"][0]
            self.assertEqual(hook["command"], HOOK[1])  # command updated
            self.assertEqual(hook["timeout"], 99)  # hand-edited timeout kept

    def test_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text("{ not json")
            with self.assertRaises(settings.SettingsError):
                settings.merge_hooks(tmp, [HOOK])


class TestMatcherGroups(unittest.TestCase):
    """The 5-tuple form. A PreToolUse hook registered in the catch-all group would
    spawn a process on EVERY tool call, which is why the matcher is part of the
    registration rather than something a user has to hand-edit afterwards."""

    def test_matcher_hook_creates_its_own_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings.merge_hooks(tmp, [("PreToolUse", "a.py", 10, "a.py")])
            self.assertTrue(settings.merge_hooks(
                tmp, [("PreToolUse", "skill.py", 10, "skill.py", "Skill")]))
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            groups = {g["matcher"]: [h["command"] for h in g["hooks"]]
                      for g in data["hooks"]["PreToolUse"]}
            self.assertEqual(groups, {"": ["a.py"], "Skill": ["skill.py"]})

    def test_matcher_hook_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hook = ("PreToolUse", "skill.py", 10, "skill.py", "Skill")
            self.assertTrue(settings.merge_hooks(tmp, [hook]))
            self.assertFalse(settings.merge_hooks(tmp, [hook]))
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            entries = [h for g in data["hooks"]["PreToolUse"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)

    def test_existing_entry_is_moved_into_the_requested_matcher(self) -> None:
        # The upgrade path: an install made before the hook carried a matcher has the
        # entry in the catch-all group. Re-running the installer must MOVE it — leaving
        # it there means the narrowing never reaches an existing install, and appending
        # a second entry means the hook runs twice.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(settings.merge_hooks(tmp, [("PostToolUse", "co.py", 15, "co.py")]))
            narrowed = ("PostToolUse", "co.py", 15, "co.py", "Write|Edit")
            self.assertTrue(settings.merge_hooks(tmp, [narrowed]))
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            groups = data["hooks"]["PostToolUse"]
            self.assertEqual([g["matcher"] for g in groups], ["Write|Edit"])
            entries = [h for g in groups for h in g["hooks"]]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["command"], "co.py")
            self.assertFalse(settings.merge_hooks(tmp, [narrowed]))

    def test_the_move_leaves_an_unrelated_hook_in_the_catch_all_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text(json.dumps({"hooks": {"PostToolUse": [
                {"matcher": "", "hooks": [
                    {"type": "command", "command": "third-party.py", "timeout": 5},
                    {"type": "command", "command": "co.py", "timeout": 15},
                ]}
            ]}}))
            settings.merge_hooks(tmp, [("PostToolUse", "co.py", 15, "co.py", "Write")])
            data = json.loads(sp.read_text())
            groups = {g["matcher"]: [h["command"] for h in g["hooks"]]
                      for g in data["hooks"]["PostToolUse"]}
            self.assertEqual(groups, {"": ["third-party.py"], "Write": ["co.py"]})

    def test_a_drifted_command_is_moved_and_rewritten_in_one_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text(json.dumps({"hooks": {"PostToolUse": [
                {"matcher": "", "hooks": [
                    {"type": "command", "command": "old/co.py", "timeout": 99}
                ]}
            ]}}))
            settings.merge_hooks(tmp, [("PostToolUse", "new/co.py", 15, "co.py", "Write")])
            data = json.loads(sp.read_text())
            groups = data["hooks"]["PostToolUse"]
            self.assertEqual([g["matcher"] for g in groups], ["Write"])
            hook = groups[0]["hooks"][0]
            self.assertEqual(hook["command"], "new/co.py")
            self.assertEqual(hook["timeout"], 99)  # hand-edited timeout still kept

    def test_four_tuple_still_lands_in_the_catch_all_group(self) -> None:
        # Regression guard for the claudemd-lerner and compliance-compiler installers,
        # which pass 4-tuples and are not modified by this change.
        with tempfile.TemporaryDirectory() as tmp:
            settings.merge_hooks(tmp, [HOOK])
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            self.assertEqual(data["hooks"]["SessionEnd"][0]["matcher"], "")


GITIGNORE = """\
# engine runtime
reports/
scripts/state.json

# caches
__pycache__/
"""


class TestMergeGitignore(unittest.TestCase):
    """Append-only merge. The defect it replaces was create-if-absent: a rule added in
    a later release reached fresh installs only, so an existing repo kept tracking the
    files the new rule was written to hide."""

    def read(self, tmp: str) -> str:
        return (Path(tmp) / ".gitignore").read_text(encoding="utf-8")

    def test_absent_file_is_written_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(settings.merge_gitignore(tmp, GITIGNORE))
            self.assertEqual(self.read(tmp), GITIGNORE)

    def test_fully_covered_file_is_not_touched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings.merge_gitignore(tmp, GITIGNORE)
            before = (Path(tmp) / ".gitignore").read_bytes()
            self.assertFalse(settings.merge_gitignore(tmp, GITIGNORE))
            self.assertEqual((Path(tmp) / ".gitignore").read_bytes(), before)

    def test_only_the_missing_rules_are_appended(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitignore").write_text(
                "my-own-rule/\nreports/\n", encoding="utf-8")
            self.assertTrue(settings.merge_gitignore(tmp, GITIGNORE))
            lines = self.read(tmp).splitlines()
            # The user's rule keeps its position, and the covered rule is not duplicated.
            self.assertEqual(lines[0], "my-own-rule/")
            self.assertEqual(lines[1], "reports/")
            self.assertEqual(lines.count("reports/"), 1)
            self.assertIn("scripts/state.json", lines)
            self.assertIn("__pycache__/", lines)
            # The comment above a missing rule comes with it, so the group stays readable.
            self.assertIn("# caches", lines)

    def test_trailing_whitespace_is_not_a_second_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitignore").write_text(
                "reports/  \nscripts/state.json\n__pycache__/\n", encoding="utf-8")
            self.assertFalse(settings.merge_gitignore(tmp, GITIGNORE))

    def test_a_file_without_a_final_newline_does_not_glue_rules_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitignore").write_text("my-own-rule/", encoding="utf-8")
            settings.merge_gitignore(tmp, GITIGNORE)
            self.assertIn("my-own-rule/", self.read(tmp).splitlines())

    def test_second_call_after_a_partial_merge_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitignore").write_text("reports/\n", encoding="utf-8")
            self.assertTrue(settings.merge_gitignore(tmp, GITIGNORE))
            self.assertFalse(settings.merge_gitignore(tmp, GITIGNORE))


class TestSetEnvDefault(unittest.TestCase):
    def test_writes_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status, value = settings.set_env_default(tmp, "PRP_HOME", ".claude/PRPs")
            self.assertEqual((status, value), ("wrote", ".claude/PRPs"))
            data = json.loads((Path(tmp) / ".claude" / "settings.json").read_text())
            self.assertEqual(data["env"]["PRP_HOME"], ".claude/PRPs")

    def test_second_call_is_already(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings.set_env_default(tmp, "PRP_HOME", ".claude/PRPs")
            sp = Path(tmp) / ".claude" / "settings.json"
            before = sp.read_bytes()
            status, value = settings.set_env_default(tmp, "PRP_HOME", ".claude/PRPs")
            self.assertEqual((status, value), ("already", ".claude/PRPs"))
            self.assertEqual(sp.read_bytes(), before)

    def test_conflicting_value_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text(json.dumps({"env": {"PRP_HOME": "/elsewhere"}}), encoding="utf-8")
            before = sp.read_bytes()
            status, value = settings.set_env_default(tmp, "PRP_HOME", ".claude/PRPs")
            self.assertEqual((status, value), ("conflict", "/elsewhere"))
            self.assertEqual(sp.read_bytes(), before)

    def test_preserves_hooks_and_other_env_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings.merge_hooks(tmp, [HOOK])
            sp = Path(tmp) / ".claude" / "settings.json"
            data = json.loads(sp.read_text())
            data["env"] = {"OTHER": "keep"}
            sp.write_text(json.dumps(data), encoding="utf-8")

            self.assertEqual(
                settings.set_env_default(tmp, "PRP_HOME", ".claude/PRPs")[0], "wrote")
            data = json.loads(sp.read_text())
            self.assertEqual(data["env"], {"OTHER": "keep", "PRP_HOME": ".claude/PRPs"})
            entries = [h for g in data["hooks"]["SessionEnd"] for h in g["hooks"]]
            self.assertEqual(len(entries), 1)

    def test_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / ".claude" / "settings.json"
            sp.parent.mkdir(parents=True)
            sp.write_text("{ not json")
            with self.assertRaises(settings.SettingsError):
                settings.set_env_default(tmp, "PRP_HOME", ".claude/PRPs")
            self.assertEqual(sp.read_text(encoding="utf-8"), "{ not json")


if __name__ == "__main__":
    unittest.main()
