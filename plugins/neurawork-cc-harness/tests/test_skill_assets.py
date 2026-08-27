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
DOCTOR_COMMAND = COMMANDS / "nw-doctor.md"
WORKTREE_SKILL = SKILLS / "nw-worktree" / "SKILL.md"
RULES_SKILL = SKILLS / "nw-rules-init" / "SKILL.md"
REVIEW_WORKFLOW = WORKFLOWS / "nw-ship-pr-review.js"

# The rules block is read on every session in every repo that installs it. Past this the
# block costs more than the repo-specific rules it sits next to. Raised from 1200 when the
# command slot became a fence: this repo's own six suites render to 1281 characters, and a
# budget the shipping repo violates is not a budget.
RULES_BLOCK_BUDGET = 1500
# THIS repo's six suites — the worst realistic case, and the one the budget is sized against.
SAMPLE_TEST_COMMAND = "\n".join(
    (
        "cd plugins/neurawork-cc-harness/engines && "
        f"python3 -m unittest discover -s {suite}"
        for suite in (
            "_shared/tests",
            "knowledge-compiler/tests",
            "claudemd-lerner/tests",
            "compliance-compiler/tests",
            "stack-compiler/tests",
        )
    )
) + "\ncd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests"

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

    def test_every_install_skill_is_registered_as_an_engine(self) -> None:
        # An installable skill whose staleness nudge cannot name it is the defect: the
        # nudge's whole payload is "re-run /neurawork-cc-harness:<engine>", and find_stale
        # skips any engine with no install_skill. This was carried in README prose while
        # one engine had no installer; now that all four do, pin it mechanically.
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        try:
            import harness_probe
        finally:
            sys.path.remove(str(PLUGIN_ROOT / "scripts"))
        engines = {p.name for p in (PLUGIN_ROOT / "engines").iterdir()
                   if p.is_dir() and (p / "install.py").is_file()}
        self.assertTrue(engines, "no engine with an install.py — the engines/ tree moved")
        for skill in sorted(SKILLS.glob("*/SKILL.md")):
            name = skill.parent.name
            if name not in engines:
                continue  # a workflow skill installs nothing — no engine to register
            with self.subTest(skill=name):
                self.assertIn(name, harness_probe.ENGINES)
                self.assertEqual(harness_probe.ENGINES[name].install_skill, name)

    def test_every_command_has_a_description(self) -> None:
        commands = sorted(COMMANDS.glob("*.md"))
        self.assertTrue(commands, "no commands found — the commands/ tree moved")
        for command in commands:
            with self.subTest(command=command.name):
                self.assertTrue(
                    frontmatter(command).get("description"),
                    "a command without a description is invisible in the slash-command list",
                )


class DoctorCommandTests(unittest.TestCase):
    """The doctor's entry point is the property whose loss is silent: a `uv run`
    invocation still works on a healthy repo and fails on exactly the broken ones the
    command exists to diagnose."""

    def fences(self) -> list[str]:
        text = DOCTOR_COMMAND.read_text(encoding="utf-8")
        # The fence is indented inside a numbered step, so it never starts at column 0.
        return re.findall(r"```[a-z]*\n(.*?)\n *```", text, re.DOTALL)

    def test_it_runs_the_plugin_side_script(self) -> None:
        self.assertTrue(DOCTOR_COMMAND.is_file(), "commands/nw-doctor.md is missing")
        self.assertIn(
            '"${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"',
            DOCTOR_COMMAND.read_text(encoding="utf-8"),
            "only the plugin holds the shipped VERSIONs the doctor compares against",
        )
        self.assertTrue((PLUGIN_ROOT / "scripts" / "doctor.py").is_file())

    def test_no_command_it_runs_needs_uv(self) -> None:
        fences = self.fences()
        self.assertTrue(fences, "the command file must show the invocation in a fence")
        for fence in fences:
            with self.subTest(fence=fence[:40]):
                self.assertNotIn(
                    "uv run",
                    fence,
                    "a missing uv and an absent .venv are states the doctor exists to "
                    "report; a `uv run` entry point cannot start in either of them",
                )
                self.assertIn("python3", fence)

    def test_it_states_that_it_only_reads(self) -> None:
        text = DOCTOR_COMMAND.read_text(encoding="utf-8")
        self.assertIn(
            "never removes a lock",
            text,
            "the read-only contract has to be in the prose the model follows, or the "
            "command starts 'helpfully' clearing locks it was asked to report",
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

    def test_main_root_is_resolved_in_phase_0_before_any_use(self) -> None:
        # Section-scoped, NOT a global count: ten `$MAIN_ROOT` uses survived a file-wide
        # read precisely because nothing tied a use to its resolution. The two assertions
        # are (a) no shell variable at all — shell state does not survive between Bash
        # calls, so an unbound one degrades to an absolute path off `/` — and (b) the
        # first placeholder occurrence in the phases is the resolution itself.
        text = SHIP_PR.read_text(encoding="utf-8")
        self.assertNotIn(
            "MAIN_ROOT",
            text,
            "a shell variable cannot carry the main checkout root between phases: each "
            "Bash call is a fresh subshell, so `git -C \"$MAIN_ROOT\"` runs against `/`. "
            "The resolved path is inserted literally as <main-root> instead",
        )
        _, _, phases = text.partition("## Phase 0 ")
        self.assertTrue(phases, "Phase 0 is missing from the command file")
        first_use = phases.index("<main-root>")
        before = phases[:first_use]
        self.assertIn(
            "### 0.1",
            before,
            "the first mention of the main root in the phases must be its resolution in "
            "Phase 0.1 — a use that precedes it has nothing to insert",
        )
        self.assertNotIn(
            "## Phase 1",
            before,
            "the main root is resolved in Phase 0.1 and nowhere else; a resolution that "
            "has drifted into a later phase leaves 0.2's config read unbound",
        )
        resolution = self.ship_pr_section("### 0.1", "### 0.2")
        self.assertIn(
            "git rev-parse --git-common-dir",
            resolution,
            "the main root is derived from --git-common-dir's parent; without the command "
            "the placeholder has no value",
        )
        self.assertIn(
            "inserted literally",
            resolution,
            "every later phase writes the resolved path into its command literally; "
            "dropping that statement is what invites a shell variable back",
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

    def test_validation_gate_merges_the_rules_block_with_the_config_extras(self) -> None:
        # Section-scoped, NOT file-wide: both sources and the anchoring rule are also
        # discussed in Phase 0.2, so a whole-file search stays green even after Phase 4.5
        # has quietly gone back to reading one of them.
        section = self.ship_pr_section("## Phase 4.5", "## Phase 5")
        for needle in ("$RULES", "$VALIDATE", "duplicates dropped"):
            with self.subTest(needle=needle):
                self.assertIn(
                    needle,
                    section,
                    "the gate's input is the CLAUDE.md rules block plus the configured "
                    "extras, deduped; naming only one source reintroduces the "
                    "hand-transcribed second copy of the repo's test command",
                )
        self.assertIn(
            "SKIP",
            section,
            "an empty merged list must SKIP the gate, never block",
        )
        self.assertIn(
            "<wt-root>",
            section,
            "the gate runs in the shipped checkout",
        )
        self.assertNotIn(
            "<main-root>/",
            section.split("If one command")[0],
            "a gate anchored to the main checkout tests <base>, not the PR: GREEN for a "
            "PR that breaks the suite, and blind to a test directory the PR itself adds. "
            "Only the documented single-command exception may name the main root",
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
        # Four backticks: the template now nests a ```sh fence, so a three-backtick outer
        # fence would end at the inner one and hand back half a block.
        text = RULES_SKILL.read_text(encoding="utf-8")
        blocks = re.findall(r"````markdown\n(.*?)\n````", text, re.DOTALL)
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

    def test_template_routes_pull_requests_through_nw_ship_pr(self) -> None:
        # The rule exists because agents reach for whatever PR skill is enabled
        # (prp-pr, a bare `gh pr create`) and skip the review/validation/approval gates
        # /nw-ship-pr owns. Without it in the always-read block, the routing is folklore.
        template = self.template()
        self.assertIn("**Pull requests**", template)
        self.assertIn("nw-ship-pr", template)

    def test_command_slot_is_one_fence_inside_the_span(self) -> None:
        # The fence is the machine-readable half: rules_block.test_commands() takes the
        # FIRST fence inside the span, and /nw-ship-pr's Phase 4.5 runs those lines. A
        # second fence, or one outside the markers, silently changes what both read.
        template = self.template()
        fences = [i for i, line in enumerate(template.splitlines())
                  if line.startswith("```")]
        self.assertEqual(
            len(fences),
            2,
            "the template must carry exactly one fenced block — the command list",
        )
        begin = template.index("neurawork-cc-harness:rules BEGIN")
        end = template.index("neurawork-cc-harness:rules END")
        opening = template.index("```")
        self.assertLess(begin, opening)
        self.assertLess(opening, end, "a fence outside the span is invisible to both readers")

    def test_run_label_immediately_precedes_the_fence(self) -> None:
        # Both readers key on the fence, but a human editing the block keys on `Run:`.
        # Separating them is how a future edit ends up moving the commands out of the span.
        lines = self.template().splitlines()
        opening = next(i for i, line in enumerate(lines) if line.startswith("```"))
        self.assertEqual(lines[opening - 1], "")
        self.assertTrue(
            lines[opening - 2].rstrip().endswith("Run:"),
            "the Evaluation-first bullet must end with `Run:` directly above the fence",
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
