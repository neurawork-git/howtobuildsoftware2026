"""Structural tests for the plugin's prompt-only assets (skills, commands, workflows).

These pin the *guard invariants* of the workflow surfaces — the properties whose loss is
silent: a removed worktree guard, a re-introduced implicit checkout, a workflow name that
no longer resolves. They prove NOTHING about runtime behaviour; prose cannot be unit
tested. The runtime proof is the manual validation runs named in the plan
(`/nw-worktree <slug>` and `/nw-ship-pr` on a real PR). Green asset tests are not a
working lifecycle.

Stdlib only, no network. `node --check` runs only when node is installed, else skipped.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS = PLUGIN_ROOT / "skills"
COMMANDS = PLUGIN_ROOT / "commands"
WORKFLOWS = PLUGIN_ROOT / "workflows"

SHIP_PR = COMMANDS / "nw-ship-pr.md"
WORKTREE_SKILL = SKILLS / "nw-worktree" / "SKILL.md"
REVIEW_WORKFLOW = WORKFLOWS / "nw-ship-pr-review.js"

# The is_main_checkout probe: both sides normalised to absolute, or the test compares
# output formats instead of locations.
PROBE = "git rev-parse --path-format=absolute --git-dir"


def frontmatter(path: Path) -> dict[str, str]:
    """Parse the leading `---` YAML block into a flat key -> value dict (scalars only)."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


class SkillFrontmatterTests(unittest.TestCase):
    def test_every_skill_name_matches_its_directory(self) -> None:
        skills = sorted(SKILLS.glob("*/SKILL.md"))
        self.assertTrue(skills, "no SKILL.md found — the skills/ tree moved")
        for skill in skills:
            with self.subTest(skill=skill.parent.name):
                fields = frontmatter(skill)
                self.assertEqual(
                    fields.get("name"),
                    skill.parent.name,
                    "a skill whose frontmatter name differs from its directory is not "
                    "invocable under the name users type",
                )
                self.assertTrue(
                    fields.get("description"),
                    "an empty description means the skill never auto-triggers",
                )

    def test_every_command_has_a_description(self) -> None:
        commands = sorted(COMMANDS.glob("*.md"))
        self.assertTrue(commands, "no commands found — the commands/ tree moved")
        for command in commands:
            with self.subTest(command=command.name):
                self.assertTrue(
                    frontmatter(command).get("description"),
                    "a command without a description is invisible in the slash-command list",
                )


class WorkflowResolutionTests(unittest.TestCase):
    def test_workflow_meta_name_matches_its_basename(self) -> None:
        source = REVIEW_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "name: 'nw-ship-pr-review'",
            source,
            "the runtime registers a workflow as <plugin>:<meta.name>; a meta.name that "
            "differs from the file the command falls back to makes one of the two paths dead",
        )
        self.assertEqual(REVIEW_WORKFLOW.stem, "nw-ship-pr-review")

    def test_ship_pr_resolves_the_workflow_both_ways(self) -> None:
        text = SHIP_PR.read_text(encoding="utf-8")
        self.assertIn(
            "neurawork-cc-harness:nw-ship-pr-review",
            text,
            "the namespaced name is the primary resolution path; the bare name does not resolve",
        )
        self.assertIn(
            "workflows/nw-ship-pr-review.js",
            text,
            "the ${CLAUDE_PLUGIN_ROOT} scriptPath fallback must name the shipped file",
        )
        self.assertTrue(
            REVIEW_WORKFLOW.is_file(),
            "both resolution paths point at a workflow file that does not exist",
        )

    def test_workflow_parses(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node not installed")
        result = subprocess.run(
            [node, "--check", str(REVIEW_WORKFLOW)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class GuardInvariantTests(unittest.TestCase):
    def test_ship_pr_never_names_the_implicit_checkout_merge_flag(self) -> None:
        text = SHIP_PR.read_text(encoding="utf-8")
        self.assertNotIn(
            "--delete-branch",
            text,
            "gh's post-merge branch-delete flag triggers a local checkout of the base "
            "branch; from a worktree that aborts with exit 128 AFTER the GitHub-side merge, "
            "leaving the remote branch behind. The command deletes the remote separately "
            "and checkout-free, and never names this flag — not even in prose, so this "
            "test stays mechanical",
        )

    def test_both_worktree_cleanup_phases_carry_their_own_probe(self) -> None:
        # Section-scoped, NOT a count over the whole file: the probe also appears in the
        # ground rules and in phase 8.0, so a global `>= 2` stays green even when BOTH
        # cleanup guards are deleted — the exact silent loss this test exists to catch.
        text = SHIP_PR.read_text(encoding="utf-8")
        sections = {}
        for heading, following in (("### 8.3", "### 8.4"), ("### 8.4", "## Phase 9")):
            _, _, rest = text.partition(heading)
            self.assertTrue(rest, f"{heading} is missing from the command file")
            sections[heading], _, _ = rest.partition(following)
        for heading, body in sections.items():
            with self.subTest(phase=heading):
                self.assertIn(
                    PROBE,
                    body,
                    f"phase {heading[4:]} must inline the is_main_checkout probe itself: "
                    "ground-rule prose is not sourced into a Bash subshell, and an "
                    "unguarded checkout in a worktree detaches HEAD so the following "
                    "`git branch -d` eats the branch",
                )

    def test_worktree_skill_only_mentions_branch_switching_to_forbid_it(self) -> None:
        offenders = [
            line
            for line in WORKTREE_SKILL.read_text(encoding="utf-8").splitlines()
            if ("git checkout " in line or "git switch " in line)
            and "never" not in line.lower()
        ]
        self.assertEqual(
            offenders,
            [],
            "the skill moves between worktrees with EnterWorktree/ExitWorktree only; a "
            "branch-switching command may appear solely on a line that forbids it",
        )

    def test_ship_pr_documents_the_config_driven_validation_gate(self) -> None:
        text = SHIP_PR.read_text(encoding="utf-8")
        self.assertIn(
            "validate_commands",
            text,
            "phase 0.2 must read the validation commands from the per-repo config",
        )
        self.assertIn(
            "SKIP",
            text,
            "an absent or empty validate_commands list must SKIP the gate, never block",
        )


if __name__ == "__main__":
    unittest.main()
