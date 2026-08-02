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
    def _touch(self, root: Path, *parts: str) -> Path:
        p = root.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        return p

    def test_matches_live_plan(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = self._touch(root, ".claude", "PRPs", "plans", "x.plan.md")
            self.assertTrue(precheck.is_plan_path(str(p), root))

    def test_rejects_completed_and_non_plan(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            done = self._touch(root, ".claude", "PRPs", "plans", "completed", "x.plan.md")
            self.assertFalse(precheck.is_plan_path(str(done), root))
            other = self._touch(root, "src", "x.plan.md")
            self.assertFalse(precheck.is_plan_path(str(other), root))
            self.assertFalse(precheck.is_plan_path(str(root / "a.md"), root))

    def test_defaults_apply_when_config_omits_the_keys(self) -> None:
        """An ADOPT install keeps a config.json written before these keys existed."""
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = self._touch(root, ".claude", "PRPs", "plans", "x.plan.md")
            legacy_cfg = {"catalog_dir": "compliance-base", "validate_mode": "warn"}
            self.assertTrue(precheck.is_plan_path(str(p), root, legacy_cfg))
            self.assertTrue(precheck.is_plan_path(str(p), root, {}))

    def test_configured_layout_gsd(self) -> None:
        """The case this config exists for: GSD's .planning/phases/<phase>/NN-PLAN.md."""
        cfg = {"plans_subpath": ".planning/phases", "plan_suffix": "-PLAN.md"}
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = self._touch(root, ".planning", "phases", "01-fundament", "01-01-PLAN.md")
            self.assertTrue(precheck.is_plan_path(str(p), root, cfg))
            # the old default no longer matches once overridden
            prp = self._touch(root, ".claude", "PRPs", "plans", "x.plan.md")
            self.assertFalse(precheck.is_plan_path(str(prp), root, cfg))

    def test_multiple_subpaths_and_suffixes(self) -> None:
        cfg = {"plans_subpath": [".claude/PRPs/plans", ".planning/phases"],
               "plan_suffix": [".plan.md", "-PLAN.md"]}
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for parts in ((".claude", "PRPs", "plans", "x.plan.md"),
                          (".planning", "phases", "01-a", "01-01-PLAN.md")):
                p = self._touch(root, *parts)
                self.assertTrue(precheck.is_plan_path(str(p), root, cfg))
            self.assertFalse(
                precheck.is_plan_path(str(self._touch(root, "docs", "x.plan.md")), root, cfg))

    def test_archive_segments_are_configurable(self) -> None:
        cfg = {"plans_subpath": ".planning/phases", "plan_suffix": "-PLAN.md",
               "plan_archive_segments": ["archive", "done"]}
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for seg in ("archive", "done"):
                p = self._touch(root, ".planning", "phases", seg, "01-PLAN.md")
                self.assertFalse(precheck.is_plan_path(str(p), root, cfg))
            # "completed" is no longer special once the key is overridden
            live = self._touch(root, ".planning", "phases", "completed", "01-PLAN.md")
            self.assertTrue(precheck.is_plan_path(str(live), root, cfg))

    def test_empty_archive_segments_keeps_every_plan_live(self) -> None:
        cfg = {"plan_archive_segments": []}
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            done = self._touch(root, ".claude", "PRPs", "plans", "completed", "x.plan.md")
            self.assertTrue(precheck.is_plan_path(str(done), root, cfg))

    def test_subpath_tolerates_separator_noise(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = self._touch(root, ".planning", "phases", "01-a", "x.plan.md")
            for subpath in ("./.planning/phases/", ".planning\\phases", "/.planning/phases"):
                self.assertTrue(
                    precheck.is_plan_path(str(p), root, {"plans_subpath": subpath}), subpath)

    def test_unusable_values_fall_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = self._touch(root, ".claude", "PRPs", "plans", "x.plan.md")
            for bad in (None, 42, {"nested": "dict"}):
                self.assertTrue(
                    precheck.is_plan_path(str(p), root, {"plans_subpath": bad}), repr(bad))

    def test_empty_subpath_list_disables_matching(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = self._touch(root, ".claude", "PRPs", "plans", "x.plan.md")
            self.assertFalse(precheck.is_plan_path(str(p), root, {"plans_subpath": []}))


if __name__ == "__main__":
    unittest.main()
