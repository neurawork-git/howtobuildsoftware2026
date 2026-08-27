"""Pure-logic tests for shards, the validation-framework selector, and the plan
precheck. No LLM."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import precheck  # noqa: E402
import shards  # noqa: E402
import utils  # noqa: E402

ALL_CFG = {"frameworks": ["gdpr", "soc2", "iso27001"]}


class TestShards(unittest.TestCase):
    def test_all_frameworks_count_and_uniqueness(self) -> None:
        s = shards.build_shards(ALL_CFG)
        self.assertGreaterEqual(len(s), 28)
        self.assertLessEqual(len(s), 40)
        keys = [(x["framework"], x["key"]) for x in s]
        self.assertEqual(len(keys), len(set(keys)))  # unique per framework

    def test_framework_filter(self) -> None:
        s = shards.build_shards({"frameworks": ["gdpr"]})
        self.assertEqual(len(s), 10)
        self.assertTrue(all(x["framework"] == "gdpr" for x in s))

    def test_unknown_framework_yields_nothing(self) -> None:
        self.assertEqual(shards.build_shards({"frameworks": ["nope"]}), [])


class TestValidationFrameworks(unittest.TestCase):
    def test_selector_prefers_validate_frameworks(self) -> None:
        self.assertEqual(
            utils.validation_frameworks(
                {"frameworks": ["gdpr", "soc2", "iso27001"], "validate_frameworks": ["soc2"]}),
            ["soc2"])

    def test_selector_falls_back_when_unset_or_empty(self) -> None:
        self.assertEqual(
            utils.validation_frameworks({"frameworks": ["gdpr", "soc2"]}), ["gdpr", "soc2"])
        self.assertEqual(
            utils.validation_frameworks({"frameworks": ["gdpr"], "validate_frameworks": []}),
            ["gdpr"])

    def _catalog(self, tmp: Path) -> Path:
        catalog = tmp / "catalog"
        catalog.mkdir()
        (catalog / "gdpr.json").write_text(json.dumps({
            "framework": "gdpr",
            "constraints": [{"id": "GDPR-ART5-01", "mandatory": True}],
        }), encoding="utf-8")
        (catalog / "soc2.json").write_text(json.dumps({
            "framework": "soc2",
            "constraints": [{"id": "SOC2-CC6-01", "mandatory": True},
                            {"id": "SOC2-CC6-02", "mandatory": True}],
        }), encoding="utf-8")
        return catalog

    def test_precheck_honors_validate_frameworks_subset(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = self._catalog(Path(t))
            cfg = {"frameworks": ["gdpr", "soc2"], "validate_frameworks": ["soc2"]}
            pc = precheck.precheck("# Feature\n\nno mention", cfg, catalog)
            # only soc2 constraints are considered — gdpr is excluded from validation
            self.assertEqual(pc["mandatory_total"], 2)
            self.assertEqual(pc["missing_mandatory_ids"], ["SOC2-CC6-01", "SOC2-CC6-02"])


class TestPrecheck(unittest.TestCase):
    def _catalog(self, tmp: Path) -> Path:
        catalog = tmp / "catalog"
        catalog.mkdir()
        (catalog / "gdpr.json").write_text(json.dumps({
            "framework": "gdpr",
            "constraints": [
                {"id": "GDPR-ART5-01", "mandatory": True},
                {"id": "GDPR-ART5-02", "mandatory": True},
                {"id": "GDPR-ART7-01", "mandatory": False},
            ],
        }), encoding="utf-8")
        return catalog

    def test_missing_ids_detected(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = self._catalog(Path(t))
            plan = "## Compliance\n\nCovered: GDPR-ART5-01 handled by encryption."
            pc = precheck.precheck(plan, {"frameworks": ["gdpr"]}, catalog)
            self.assertTrue(pc["catalog_built"])
            self.assertTrue(pc["has_compliance_section"])
            self.assertEqual(pc["mandatory_total"], 2)
            self.assertEqual(pc["missing_mandatory_ids"], ["GDPR-ART5-02"])
            self.assertEqual(pc["referenced_ids"], ["GDPR-ART5-01"])

    def test_no_section_and_no_refs(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = self._catalog(Path(t))
            pc = precheck.precheck("# Feature\n\nno mention here", {"frameworks": ["gdpr"]}, catalog)
            self.assertFalse(pc["has_compliance_section"])
            self.assertEqual(pc["missing_mandatory_ids"], ["GDPR-ART5-01", "GDPR-ART5-02"])

    def test_catalog_absent(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            pc = precheck.precheck("anything", {"frameworks": ["gdpr"]}, Path(t) / "catalog")
            self.assertFalse(pc["catalog_built"])
            self.assertEqual(pc["missing_mandatory_ids"], [])


class TestIsPlanPath(unittest.TestCase):
    def test_matches_live_plan(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = root / ".claude" / "PRPs" / "plans" / "x.plan.md"
            p.parent.mkdir(parents=True)
            p.write_text("x", encoding="utf-8")
            self.assertTrue(precheck.is_plan_path(str(p), root))

    def test_rejects_completed_and_non_plan(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            done = root / ".claude" / "PRPs" / "plans" / "completed" / "x.plan.md"
            done.parent.mkdir(parents=True)
            done.write_text("x", encoding="utf-8")
            self.assertFalse(precheck.is_plan_path(str(done), root))
            other = root / "src" / "x.plan.md"
            other.parent.mkdir(parents=True)
            other.write_text("x", encoding="utf-8")
            self.assertFalse(precheck.is_plan_path(str(other), root))

    def test_matches_prp_home_store_layout(self) -> None:
        # PRP_HOME=".claude/PRPs" makes prp-core write to <store>/plans/, one level deeper
        # than the canonical path — see config.PRP_SUBPATH.
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            store = root / ".claude" / "PRPs" / "myrepo-1a2b3c4d"
            live = store / "plans" / "x.plan.md"
            live.parent.mkdir(parents=True)
            live.write_text("x", encoding="utf-8")
            self.assertTrue(precheck.is_plan_path(str(live), root))

            done = store / "plans" / "completed" / "x.plan.md"
            done.parent.mkdir(parents=True)
            done.write_text("x", encoding="utf-8")
            self.assertFalse(precheck.is_plan_path(str(done), root))

    def test_rejects_other_store_dirs_and_deeper_nesting(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            prd = root / ".claude" / "PRPs" / "myrepo-1a2b3c4d" / "prds" / "x.plan.md"
            prd.parent.mkdir(parents=True)
            prd.write_text("x", encoding="utf-8")
            self.assertFalse(precheck.is_plan_path(str(prd), root))

            deep = root / ".claude" / "PRPs" / "a" / "b" / "plans" / "x.plan.md"
            deep.parent.mkdir(parents=True)
            deep.write_text("x", encoding="utf-8")
            self.assertFalse(precheck.is_plan_path(str(deep), root))
            self.assertFalse(precheck.is_plan_path(str(root / "a.md"), root))


CAP_CFG = {"frameworks": ["gdpr", "soc2"]}


def _capability_catalog(tmp: Path, *, chosen: str | None = None,
                        applicable: bool = True) -> Path:
    """A catalog dir with two gdpr capabilities — one mandatory-linked ('Encryption at
    rest'), one covering only an optional constraint ('Consent capture') — plus a soc2
    capability, the matching constraints, and a stack.json recording one decision."""
    catalog = tmp / "catalog"
    catalog.mkdir()
    (catalog / "gdpr.json").write_text(json.dumps({"framework": "gdpr", "constraints": [
        {"id": "GDPR-ART5-01", "mandatory": True},
        {"id": "GDPR-ART7-01", "mandatory": False},
    ]}), encoding="utf-8")
    (catalog / "soc2.json").write_text(json.dumps({"framework": "soc2", "constraints": [
        {"id": "SOC2-CC7-01", "mandatory": True},
    ]}), encoding="utf-8")
    (catalog / "capabilities.json").write_text(json.dumps({
        "generated": "2026-01-01",
        "frameworks": {
            "gdpr": {"capability_count": 2, "capabilities": [
                {"name": "Encryption at rest", "category": "Data Protection",
                 "description": "Encrypt stored personal data.",
                 "satisfies": ["GDPR-ART5-01"], "stack": []},
                {"name": "Consent capture", "category": "Governance & Privacy Ops",
                 "description": "Record consent.",
                 "satisfies": ["GDPR-ART7-01"], "stack": []},
            ]},
            "soc2": {"capability_count": 1, "capabilities": [
                {"name": "Audit logging", "category": "Logging & Monitoring",
                 "description": "Append-only log.",
                 "satisfies": ["SOC2-CC7-01"], "stack": []},
            ]},
        },
    }), encoding="utf-8")
    (catalog / "stack.json").write_text(json.dumps({"choices": {
        "gdpr/encryption-at-rest": {"chosen": chosen, "applicable": applicable},
        "gdpr/consent-capture": {"chosen": None, "applicable": True},
        "soc2/audit-logging": {"chosen": "OpenSearch", "applicable": True},
    }}), encoding="utf-8")
    return catalog


class TestCapabilityDeclaration(unittest.TestCase):
    def test_parses_keys_with_and_without_backticks(self) -> None:
        d = precheck.declared_capabilities(
            "## Compliance\n\n**Capabilities**: gdpr/encryption-at-rest, `soc2/audit-logging`\n")
        self.assertTrue(d["present"])
        self.assertFalse(d["none"])
        self.assertEqual(d["keys"], ["gdpr/encryption-at-rest", "soc2/audit-logging"])

    def test_reads_a_wrapped_declaration_whole(self) -> None:
        d = precheck.declared_capabilities(
            "**Capabilities**: gdpr/encryption-at-rest,\nsoc2/audit-logging\n\nprose\n")
        self.assertEqual(d["keys"], ["gdpr/encryption-at-rest", "soc2/audit-logging"])

    def test_none_declaration_carries_its_reason(self) -> None:
        d = precheck.declared_capabilities("**Capabilities**: none — internal tool, no PII\n")
        self.assertTrue(d["none"])
        self.assertEqual(d["keys"], [])
        self.assertEqual(d["reason"], "internal tool, no PII")

    def test_none_without_reason_is_still_a_declaration(self) -> None:
        d = precheck.declared_capabilities("**Capabilities**: none\n")
        self.assertTrue(d["present"])
        self.assertTrue(d["none"])
        self.assertEqual(d["reason"], "")

    def test_absent_line_is_not_present(self) -> None:
        d = precheck.declared_capabilities("## Compliance\n\nJust prose.\n")
        self.assertFalse(d["present"])
        self.assertEqual(d["keys"], [])

    def test_prose_with_a_slash_never_becomes_a_key(self) -> None:
        # A path in the same paragraph must not be read as a capability key.
        d = precheck.declared_capabilities(
            "**Capabilities**: gdpr/encryption-at-rest, see .claude/PRPs for context\n")
        self.assertEqual(d["keys"], ["gdpr/encryption-at-rest"])


class TestCapabilityPrecheck(unittest.TestCase):
    def _run(self, plan: str, catalog: Path, cfg: dict | None = None) -> dict:
        return precheck.capability_precheck(plan, cfg or CAP_CFG, catalog)

    def test_reports_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t))
            r = self._run("**Capabilities**: gdpr/encryption-at-rest, gdpr/typo-here\n", catalog)
            self.assertTrue(r["catalog_built"])
            self.assertEqual(r["unknown_keys"], ["gdpr/typo-here"])
            self.assertEqual(r["mandatory_linked_total"], 2)

    def test_framework_outside_validate_frameworks_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t))
            r = self._run("**Capabilities**: soc2/audit-logging\n", catalog,
                          {"frameworks": ["gdpr", "soc2"], "validate_frameworks": ["gdpr"]})
            self.assertEqual(r["unknown_keys"], ["soc2/audit-logging"])
            self.assertEqual(r["mandatory_linked_total"], 1)

    def test_chosen_component_clears_the_unchosen_flag(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t), chosen="OpenBao")
            r = self._run("**Capabilities**: gdpr/encryption-at-rest\n", catalog)
            self.assertEqual(r["declared_unchosen"], [])
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t))
            r = self._run("**Capabilities**: gdpr/encryption-at-rest\n", catalog)
            self.assertEqual(r["declared_unchosen"], ["gdpr/encryption-at-rest"])

    def test_reports_a_capability_scoped_out_as_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t), chosen="OpenBao", applicable=False)
            r = self._run("**Capabilities**: gdpr/encryption-at-rest\n", catalog)
            self.assertEqual(r["declared_not_applicable"], ["gdpr/encryption-at-rest"])

    def test_missing_capability_catalog_degrades_quietly(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = Path(t) / "catalog"
            catalog.mkdir()
            r = self._run("**Capabilities**: gdpr/encryption-at-rest\n", catalog)
            self.assertFalse(r["catalog_built"])
            self.assertEqual(r["mandatory_linked_total"], 0)
            self.assertEqual(r["unknown_keys"], ["gdpr/encryption-at-rest"])

    def test_corrupt_capability_catalog_degrades_quietly(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t))
            (catalog / "capabilities.json").write_text("{not json", encoding="utf-8")
            r = self._run("**Capabilities**: gdpr/encryption-at-rest\n", catalog)
            self.assertFalse(r["catalog_built"])

    def test_precheck_embeds_the_capability_signals(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t))
            pc = precheck.precheck("**Capabilities**: none — no surface\n", CAP_CFG, catalog)
            self.assertTrue(pc["capabilities"]["declared_none"])
            self.assertEqual(pc["mandatory_total"], 2)  # constraint tier untouched


class TestCapabilityVerdict(unittest.TestCase):
    MAND = ["gdpr/encryption-at-rest", "soc2/audit-logging"]

    def test_applicable_mandatory_but_undeclared_fails(self) -> None:
        v = precheck.capability_verdict(
            ["gdpr/encryption-at-rest", "soc2/audit-logging"],
            ["soc2/audit-logging"], self.MAND)
        self.assertEqual(v["undeclared_mandatory"], ["gdpr/encryption-at-rest"])

    def test_applicable_optional_only_is_not_a_gap(self) -> None:
        v = precheck.capability_verdict(["gdpr/consent-capture"], [], self.MAND)
        self.assertEqual(v["undeclared_mandatory"], [])
        self.assertEqual(v["applicable_total"], 1)

    def test_over_declaration_is_reported_never_failed(self) -> None:
        v = precheck.capability_verdict([], ["gdpr/encryption-at-rest"], self.MAND)
        self.assertEqual(v["undeclared_mandatory"], [])
        self.assertEqual(v["declared_not_applicable"], ["gdpr/encryption-at-rest"])

    def test_invented_key_is_filtered_out_before_the_math(self) -> None:
        v = precheck.capability_verdict(
            ["gdpr/encryption-at-rest", "gdpr/made-up"], [], self.MAND,
            known_keys=self.MAND + ["gdpr/consent-capture"])
        self.assertEqual(v["applicable_total"], 1)
        self.assertEqual(v["undeclared_mandatory"], ["gdpr/encryption-at-rest"])

    def test_nothing_applicable_passes(self) -> None:
        v = precheck.capability_verdict([], [], self.MAND)
        self.assertEqual(v["undeclared_mandatory"], [])


VALIDATION_SECTION = """## Validation

| Gate | Command | Proves |
|---|---|---|
| Unit | `python3 -m unittest discover -s tests` | AC1 |
| Lint | `uvx ruff check` | house style |

## Risks
"""


class TestValidationPrecheck(unittest.TestCase):
    def test_table_commands_and_a_task_level_test_file_are_found(self) -> None:
        plan = ("# Plan\n\n**Tests**\n- `tests/test_rules_block.py` (new)\n\n"
                + VALIDATION_SECTION)
        v = precheck.validation_precheck(plan)
        self.assertTrue(v["section_present"])
        self.assertEqual(
            v["commands"], ["python3 -m unittest discover -s tests", "uvx ruff check"])
        self.assertEqual(v["named_test_files"], ["test_rules_block.py"])

    def test_validation_commands_heading_is_recognised_identically(self) -> None:
        # 10 of this repo's 22 plans spell it this way; an exact-match heading regex
        # would report a missing section on every one of them.
        plan = "# Plan\n\n" + VALIDATION_SECTION.replace(
            "## Validation\n", "## Validation Commands\n")
        v = precheck.validation_precheck(plan)
        self.assertTrue(v["section_present"])
        self.assertEqual(len(v["commands"]), 2)

    def test_absent_section_reports_itself(self) -> None:
        v = precheck.validation_precheck("# Plan\n\n## Scope\n\nprose\n")
        self.assertFalse(v["section_present"])
        self.assertEqual(v["commands"], [])

    def test_section_with_prose_but_no_delimited_span_yields_no_command(self) -> None:
        v = precheck.validation_precheck("# Plan\n\n## Validation\n\nRun the suite.\n")
        self.assertTrue(v["section_present"])
        self.assertEqual(v["commands"], [])

    def test_pytest_in_bare_prose_is_never_a_command(self) -> None:
        # The documented false positive: nw-rules-init-baseline-rules.plan.md:286,341
        # discusses pytest-vs-unittest DETECTION in a target repo, not its own gate.
        v = precheck.validation_precheck(
            "# Plan\n\n## Validation\n\nNever default to pytest in a unittest repo.\n")
        self.assertEqual(v["commands"], [])

    def test_a_file_reference_sharing_the_section_is_not_a_command(self) -> None:
        v = precheck.validation_precheck(
            "# Plan\n\n## Validation\n\nRead `.claude/ship-pr.local.md` and "
            "`precheck.py:184-198`, then run `make test`.\n")
        self.assertEqual(v["commands"], ["make test"])

    def test_fenced_commands_are_taken_one_per_line(self) -> None:
        plan = "# Plan\n\n## Validation\n\n```bash\nmake test\nmake lint\n```\n"
        self.assertEqual(
            precheck.validation_precheck(plan)["commands"], ["make test", "make lint"])

    def test_a_narrower_command_than_the_repo_declares_is_a_count_not_a_failure(self) -> None:
        plan = "# Plan\n\n## Validation\n\n- `pytest tests/unit/test_one.py`\n"
        v = precheck.validation_precheck(plan, ["make test", "make lint"])
        self.assertEqual(v["repo_commands_total"], 2)
        self.assertEqual(v["repo_commands_named"], 0)
        self.assertEqual(v["commands"], ["pytest tests/unit/test_one.py"])
        self.assertNotIn("failed", str(v))

    def test_repo_commands_are_matched_on_the_normalised_string(self) -> None:
        plan = "# Plan\n\n## Validation\n\n```sh\nmake   test\n```\n"
        v = precheck.validation_precheck(plan, ["make test", "make lint"])
        self.assertEqual(v["repo_commands_named"], 1)

    def test_precheck_embeds_the_validation_signals(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _capability_catalog(Path(t))
            pc = precheck.precheck("# Plan\n\n" + VALIDATION_SECTION, CAP_CFG, catalog)
            self.assertTrue(pc["validation"]["section_present"])
            self.assertEqual(pc["validation"]["repo_commands_total"], 0)

    def test_precheck_reads_the_repo_rules_block_when_given_a_root(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            catalog = _capability_catalog(root)
            (root / "CLAUDE.md").write_text(
                "# CLAUDE.md\n\n<!-- neurawork-cc-harness:rules BEGIN (auto) -->\n"
                "- **Evaluation first** — Run:\n\n```sh\nuvx ruff check\n```\n"
                "<!-- neurawork-cc-harness:rules END -->\n",
                encoding="utf-8")
            pc = precheck.precheck(
                "# Plan\n\n" + VALIDATION_SECTION, CAP_CFG, catalog, repo_root=root)
            self.assertEqual(pc["validation"]["repo_commands"], ["uvx ruff check"])
            self.assertEqual(pc["validation"]["repo_commands_named"], 1)


class TestValidationPrecheckCorpus(unittest.TestCase):
    """The survey this check was designed against, pinned so a later regex tightening
    cannot silently stop matching the plans it was measured on."""

    def _plans(self) -> list[Path]:
        for parent in Path(__file__).resolve().parents:
            plans = parent / ".claude" / "PRPs" / "plans"
            if plans.is_dir():
                return sorted(plans.rglob("*.plan.md"))
        return []

    def test_every_plan_in_this_repo_has_a_validation_section(self) -> None:
        plans = self._plans()
        if not plans:
            self.skipTest("no .claude/PRPs/plans next to this engine (pure plugin checkout)")
        missing = [
            p.name for p in plans
            if not precheck.validation_precheck(
                p.read_text(encoding="utf-8"))["section_present"]
        ]
        self.assertEqual(
            missing, [],
            "the heading regex is a PREFIX match precisely so both `## Validation` and "
            "`## Validation Commands` count; a plan reported missing here means the "
            "regex was tightened, not that the corpus changed")


def _installed_hook_path() -> Path | None:
    """The self-hosted ``compliance-base/hooks/co-post-tooluse.py``, or None.

    The hook is imported from the INSTALL, never from ``payload/``: it resolves
    ``_shared`` next to its own hooks/ dir, which only exists in an installed repo.
    A pure plugin checkout has no install — the test skips there, same as
    ``test_catalog_seed.py``.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "compliance-base" / "hooks" / "co-post-tooluse.py"
        if candidate.exists():
            return candidate
    return None


def _load_installed_hook(test: unittest.TestCase):
    """The installed hook module, or ``skipTest`` in a pure plugin checkout."""
    import importlib.util
    import os

    hook_path = _installed_hook_path()
    if hook_path is None:
        test.skipTest("no compliance-base install next to this engine")
    # recursion_guard() sys.exit(0)s on this var — it is set when the hook runs
    # under a compiler-spawned session, not when a test imports it.
    test.assertIsNone(os.environ.get("CLAUDE_INVOKED_BY"),
                      "CLAUDE_INVOKED_BY set — the hook would exit on import")
    spec = importlib.util.spec_from_file_location("co_post_tooluse_under_test", hook_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCapabilityAdvisory(unittest.TestCase):
    """The hook's one-sentence advisory about the capability layer."""

    def _summary(self, cp: dict) -> str:
        return _load_installed_hook(self)._capability_summary(cp)

    def test_unbuilt_capability_layer_names_the_command(self) -> None:
        text = self._summary({"catalog_built": False})
        self.assertIn("co-capabilities", text)

    def test_built_layer_advises_on_the_declaration_instead(self) -> None:
        text = self._summary({
            "catalog_built": True,
            "declaration_present": False,
            "unknown_keys": [],
            "declared_none": False,
            "none_reason": "",
            "declared": [],
            "declared_unchosen": [],
            "declared_not_applicable": [],
        })
        self.assertNotIn("co-capabilities", text)
        self.assertIn("**Capabilities**:", text)


class TestValidationAdvisory(unittest.TestCase):
    """The hook's one-clause advisory about the plan's own validation gate."""

    def _summary(self, plan: str, repo_commands: list[str] | None = None) -> str:
        module = _load_installed_hook(self)
        return module._validation_summary(
            precheck.validation_precheck(plan, repo_commands))

    def test_missing_section_says_what_belongs_there(self) -> None:
        text = self._summary("# Plan\n\n## Scope\n\nprose\n")
        self.assertIn("## Validation", text)
        self.assertIn("test file", text)

    def test_empty_section_names_the_repo_declared_commands(self) -> None:
        text = self._summary("# Plan\n\n## Validation\n\nRun the suite.\n",
                             ["make test", "make lint"])
        self.assertIn("`make test`", text)
        self.assertIn("`make lint`", text)

    def test_empty_section_without_a_block_still_reports_the_gap(self) -> None:
        text = self._summary("# Plan\n\n## Validation\n\nRun the suite.\n")
        self.assertIn("no runnable command", text)

    def test_command_but_no_test_file_reads_as_a_question(self) -> None:
        text = self._summary("# Plan\n\n## Validation\n\n- `make test`\n", ["make test"])
        self.assertTrue(text.rstrip().endswith("?"), text)

    def test_no_rules_block_names_the_init_command(self) -> None:
        plan = "# Plan\n\n**Tests**: `tests/test_x.py`\n\n## Validation\n\n- `make test`\n"
        self.assertIn("nw-rules-init", self._summary(plan))

    def test_a_complete_plan_gets_a_confirming_clause_only(self) -> None:
        plan = "# Plan\n\n**Tests**: `tests/test_x.py`\n\n## Validation\n\n- `make test`\n"
        text = self._summary(plan, ["make test"])
        self.assertIn("1 command(s)", text)
        self.assertNotIn("nw-rules-init", text)

    def test_the_advisory_never_reaches_the_blocking_path(self) -> None:
        # The whole point: `validate_mode: block` is reserved for unaddressed MANDATORY
        # constraints. A plan with no test is a legitimate state twice over in this corpus.
        hook_path = _installed_hook_path()
        if hook_path is None:
            self.skipTest("no compliance-base install next to this engine")
        source = hook_path.read_text(encoding="utf-8")
        _, _, blocking = source.partition("    blocking = (")
        self.assertTrue(blocking)
        condition, _, _ = blocking.partition(")")
        self.assertNotIn("validation", condition)


if __name__ == "__main__":
    unittest.main()
