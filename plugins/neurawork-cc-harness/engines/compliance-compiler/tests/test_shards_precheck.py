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


if __name__ == "__main__":
    unittest.main()
