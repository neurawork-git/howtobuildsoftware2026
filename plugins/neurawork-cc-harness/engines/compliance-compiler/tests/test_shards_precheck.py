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


if __name__ == "__main__":
    unittest.main()
