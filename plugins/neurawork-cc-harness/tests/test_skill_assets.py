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
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS = PLUGIN_ROOT / "skills"
COMMANDS = PLUGIN_ROOT / "commands"
WORKFLOWS = PLUGIN_ROOT / "workflows"

SHIP_PR = COMMANDS / "nw-ship-pr.md"
WORKTREE_SKILL = SKILLS / "nw-worktree" / "SKILL.md"
RULES_SKILL = SKILLS / "nw-rules-init" / "SKILL.md"
REVIEW_WORKFLOW = WORKFLOWS / "nw-ship-pr-review.js"

# The rules block is read on every session in every repo that installs it. Past this the
# block costs more than the repo-specific rules it sits next to.
RULES_BLOCK_BUDGET = 1200
# A command long enough to stand in for a real multi-suite repo when measuring the block.
SAMPLE_TEST_COMMAND = "python3 -m unittest discover -s engines/knowledge-compiler/tests"

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

    # Section-scoped like the cleanup-probe test above, and for the same reason: a
    # file-wide search for "open items" stays green on the Phase 5 mention alone, even
    # after Phase 6.5 stopped consuming them — the exact silent loss these pin.
    def ship_pr_section(self, heading: str, following: str) -> str:
        text = SHIP_PR.read_text(encoding="utf-8")
        _, _, rest = text.partition(heading)
        self.assertTrue(rest, f"{heading} is missing from the command file")
        section, _, _ = rest.partition(following)
        return section

    def test_explanation_names_open_items(self) -> None:
        section = self.ship_pr_section("## Phase 5", "## Phase 6 ")
        self.assertIn(
            "Open items",
            section,
            "phase 5 is the only collection point for the non-finding items (degraded "
            "validation, unverified claims, known-broken state); without it phase 6.5 "
            "receives review findings only",
        )

    def test_follow_up_capture_takes_open_items_not_only_findings(self) -> None:
        section = self.ship_pr_section("## Phase 6.5", "## Phase 7")
        for needle in ("nice-to-have", "Phase 5 open items"):
            with self.subTest(needle=needle):
                self.assertIn(
                    needle,
                    section,
                    "phase 6.5 persists deferred ITEMS — review findings are one source "
                    "among four; losing the phase 5 open items reverts the run to "
                    "capturing review findings only",
                )
        self.assertIn(
            "0 deferred items",
            section,
            "the zero-item skip is load-bearing against an empty commit",
        )

    def test_recurring_capture_items_have_fixed_titles(self) -> None:
        section = self.ship_pr_section("## Phase 6.5", "## Phase 7")
        for title in (
            "the /nw-ship-pr validation gate is not configured",
            "the /nw-ship-pr validation gate could not run",
            "PR #<nr> was merged with a failing <command>",
            "PR #<nr> was merged on a fallback mini-review",
        ):
            with self.subTest(title=title):
                self.assertIn(
                    title,
                    section,
                    "de-dup is exact-title, so a recurring condition needs a title the "
                    "command fixes; LLM-authored prose adds one near-duplicate per merge",
                )

    def test_report_does_not_invent_open_items(self) -> None:
        section = self.ship_pr_section("## Phase 9", "## Order mnemonic")
        self.assertIn(
            "names no open item that Phase 6.5 neither wrote nor explicitly excluded",
            section,
            "phase 9 is a readback of what phase 6.5 wrote plus the named exclusions; "
            "without the invariant it becomes a source again and its items are lost with "
            "the session",
        )


class RulesBlockTests(unittest.TestCase):
    """The block template is the whole product of nw-rules-init: one span, byte-stable,
    and small enough to earn its place in a root CLAUDE.md."""

    def template(self) -> str:
        text = RULES_SKILL.read_text(encoding="utf-8")
        blocks = re.findall(r"```markdown\n(.*?)```", text, re.DOTALL)
        templates = [b for b in blocks if "neurawork-cc-harness:rules BEGIN" in b]
        self.assertEqual(
            len(templates),
            1,
            "the block template must exist exactly once — a second copy is a second thing "
            "to keep byte-identical, and an inexact copy makes the re-run non-idempotent",
        )
        return templates[0]

    def test_template_is_one_well_formed_span(self) -> None:
        template = self.template()
        self.assertEqual(template.count("neurawork-cc-harness:rules BEGIN"), 1)
        self.assertEqual(template.count("neurawork-cc-harness:rules END"), 1)
        self.assertLess(
            template.index("BEGIN"),
            template.index("END"),
            "END before BEGIN is not a span the guard can protect",
        )

    def test_template_carries_all_three_clusters_and_the_command_slot(self) -> None:
        template = self.template()
        for cluster in ("**Scope**", "**Simplicity**", "**Evaluation first**"):
            with self.subTest(cluster=cluster):
                self.assertIn(cluster, template)
        self.assertIn(
            "<TEST_COMMAND>",
            template,
            "the runner detected in Stage 1 must have a slot; a hard-coded command would "
            "ship a rule this repo's own unittest suite violates",
        )

    def test_rendered_block_stays_inside_the_budget(self) -> None:
        rendered = self.template().replace("<TEST_COMMAND>", SAMPLE_TEST_COMMAND)
        self.assertLessEqual(
            len(rendered),
            RULES_BLOCK_BUDGET,
            f"the rendered block is {len(rendered)} chars; a root CLAUDE.md is read every "
            "session, so growth here is paid on every turn in every repo",
        )

    def test_the_learner_guard_recognises_this_marker(self) -> None:
        # Import the guard the learner actually ships, so a change to either the marker id
        # here or the regex there fails a test instead of silently unprotecting the block.
        scripts = PLUGIN_ROOT / "engines" / "claudemd-lerner" / "payload" / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import markers
        finally:
            sys.path.remove(str(scripts))
        spans = markers.find_spans(self.template().replace("<TEST_COMMAND>", "make test"))
        self.assertEqual(
            [s[0] for s in spans],
            ["neurawork-cc-harness:rules"],
            "the block the skill writes must be a span the learner's guard restores",
        )

    def test_skill_documents_the_refresh_and_no_second_block_rules(self) -> None:
        text = RULES_SKILL.read_text(encoding="utf-8")
        self.assertIn("--force", text, "an already-initialised repo needs a refresh path")
        self.assertIn(
            "Never write a second block",
            text,
            "two spans with the same marker id is the one state the guard cannot resolve",
        )

    def test_skill_forbids_defaulting_to_pytest(self) -> None:
        self.assertIn(
            "Never default to pytest",
            RULES_SKILL.read_text(encoding="utf-8"),
            "silently defaulting the runner is the failure mode Stage 1 exists to prevent",
        )

if __name__ == "__main__":
    unittest.main()
