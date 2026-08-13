"""Pure-logic tests for stack.py (capability→component mapping). No LLM, no network."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import stack  # noqa: E402


def _constraints(tmp: Path) -> Path:
    """A catalog dir whose gdpr.json has two mandatory and one optional constraint."""
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


def _capabilities() -> dict:
    """Two capabilities: one mandatory-linked, one covering only an optional constraint."""
    return {
        "generated": "2026-01-01",
        "frameworks": {"gdpr": {
            "capability_count": 2,
            "capabilities": [
                {
                    "name": "Encryption at rest",
                    "category": "Data Protection",
                    "description": "Encrypt stored personal data.",
                    "satisfies": ["GDPR-ART5-01", "GDPR-ART5-02"],
                    "stack": [
                        {"name": "OpenBao", "kind": "open-source", "verdict": "keep"},
                        {"name": "age", "kind": "open-source", "verdict": "replaced",
                         "replaced_from": "AWS KMS"},
                    ],
                    "stack_notes": "",
                },
                {
                    "name": "Consent capture",
                    "category": "Governance & Privacy Ops",
                    "description": "Record consent.",
                    "satisfies": ["GDPR-ART7-01"],
                    "stack": [{"name": "Klaro!", "kind": "open-source", "verdict": "keep"}],
                    "stack_notes": "",
                },
            ],
        }},
    }


class TestCapabilityKey(unittest.TestCase):
    def test_framework_prefixed_slug(self) -> None:
        self.assertEqual(stack.capability_key("gdpr", "Audit logging (SOC2 CC7)"),
                         "gdpr/audit-logging")

    def test_same_name_distinct_across_frameworks(self) -> None:
        self.assertNotEqual(stack.capability_key("gdpr", "Audit logging"),
                            stack.capability_key("soc2", "Audit logging"))


class TestMandatoryLinked(unittest.TestCase):
    def test_only_mandatory_linked_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            keys = stack.mandatory_linked_keys(_capabilities(), catalog)
            self.assertEqual(keys, {"gdpr/encryption-at-rest"})  # consent-capture is optional-only


class TestComponentOptions(unittest.TestCase):
    def test_preserves_order_and_keeps_replaced_verdict(self) -> None:
        cap = _capabilities()["frameworks"]["gdpr"]["capabilities"][0]
        # `replaced` means this component SUPERSEDED replaced_from — never "rejected"
        self.assertEqual(stack.component_options(cap), ["OpenBao", "age"])

    def test_dedupes_and_skips_nameless(self) -> None:
        cap = {"stack": [{"name": "A"}, {"name": "A"}, {"kind": "x"}, {"name": "B"}]}
        self.assertEqual(stack.component_options(cap), ["A", "B"])

    def test_empty_stack(self) -> None:
        self.assertEqual(stack.component_options({"stack": []}), [])


class TestScaffold(unittest.TestCase):
    def test_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            out = stack.scaffold(_capabilities(), None, catalog_dir=catalog,
                                 generated="2026-02-02", capabilities_hash="abc123")
            self.assertEqual(out["generated"], "2026-02-02")
            self.assertEqual(out["capabilities_generated"], "2026-01-01")
            self.assertEqual(out["capabilities_hash"], "abc123")
            self.assertEqual(list(out["choices"]), sorted(out["choices"]))  # stable diffs
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual(enc["capability"], "Encryption at rest")
            self.assertEqual(enc["framework"], "gdpr")
            self.assertTrue(enc["mandatory_linked"])
            self.assertEqual(enc["options"], ["OpenBao", "age"])
            self.assertIsNone(enc["chosen"])
            self.assertEqual(enc["rationale"], "")
            self.assertTrue(enc["applicable"])          # unscoped default: everything applies
            self.assertEqual(enc["applicability_reason"], "")
            self.assertIsNone(enc["scoped_from"])
            self.assertFalse(out["choices"]["gdpr/consent-capture"]["mandatory_linked"])

    def test_preserves_human_fields_and_refreshes_machine_fields(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            existing = {"choices": {"gdpr/encryption-at-rest": {
                "capability": "STALE NAME",
                "framework": "gdpr",
                "mandatory_linked": False,      # stale — must be recomputed
                "options": ["Vault"],           # stale — must be recomputed
                "chosen": "OpenBao",
                "rationale": "already self-hosted",
            }}}
            out = stack.scaffold(_capabilities(), existing, catalog_dir=catalog,
                                 generated="2026-02-02")
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual(enc["chosen"], "OpenBao")                   # human, carried
            self.assertEqual(enc["rationale"], "already self-hosted")    # human, carried
            self.assertEqual(enc["capability"], "Encryption at rest")    # machine, refreshed
            self.assertTrue(enc["mandatory_linked"])                     # machine, refreshed
            self.assertEqual(enc["options"], ["OpenBao", "age"])         # machine, refreshed

    def test_preserves_applicability_scoping(self) -> None:
        """A re-scaffold must not erase the stack-compiler's product scoping."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            existing = {"choices": {"gdpr/encryption-at-rest": {
                "chosen": None,
                "rationale": "",
                "applicable": False,
                "applicability_reason": "product stores no data at rest",
                "scoped_from": "scope-7f3a",
            }}}
            out = stack.scaffold(_capabilities(), existing, catalog_dir=catalog)
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertFalse(enc["applicable"])
            self.assertEqual(enc["applicability_reason"], "product stores no data at rest")
            self.assertEqual(enc["scoped_from"], "scope-7f3a")

    def test_adds_new_capability_unchosen(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            existing = {"choices": {"gdpr/encryption-at-rest": {"chosen": "OpenBao",
                                                                "rationale": "r"}}}
            out = stack.scaffold(_capabilities(), existing, catalog_dir=catalog)
            self.assertIsNone(out["choices"]["gdpr/consent-capture"]["chosen"])
            self.assertEqual(out["choices"]["gdpr/encryption-at-rest"]["chosen"], "OpenBao")

    def test_orphaned_key_not_carried(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            existing = {"choices": {"gdpr/gone-away": {"chosen": "X", "rationale": ""}}}
            out = stack.scaffold(_capabilities(), existing, catalog_dir=catalog)
            self.assertNotIn("gdpr/gone-away", out["choices"])

    def test_duplicate_key_raises(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            # a parenthetical suffix collapses to the same slug → collision, not overwrite
            cat["frameworks"]["gdpr"]["capabilities"].append({
                "name": "Encryption at rest (storage layer)",
                "category": "Data Protection", "description": "",
                "satisfies": ["GDPR-ART5-01"], "stack": [], "stack_notes": "",
            })
            with self.assertRaises(ValueError):
                stack.scaffold(cat, None, catalog_dir=catalog)


class TestGaps(unittest.TestCase):
    def _scaffolded(self, catalog: Path, **kw) -> dict:
        return stack.scaffold(_capabilities(), None, catalog_dir=catalog, **kw)

    def test_counts_only_mandatory_linked(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            res = stack.gaps(_capabilities(), self._scaffolded(catalog), catalog_dir=catalog)
            self.assertEqual(res["mandatory_total"], 1)
            self.assertEqual(res["mandatory_unchosen"], ["gdpr/encryption-at-rest"])
            self.assertEqual(res["optional_unchosen"], ["gdpr/consent-capture"])

    def test_chosen_clears_the_gap(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            s["choices"]["gdpr/encryption-at-rest"]["chosen"] = "OpenBao"
            res = stack.gaps(_capabilities(), s, catalog_dir=catalog)
            self.assertEqual(res["mandatory_unchosen"], [])
            self.assertEqual(res["off_catalog"], [])

    def test_blank_chosen_counts_as_unchosen(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            for blank in ("", "   "):
                s = self._scaffolded(catalog)
                s["choices"]["gdpr/encryption-at-rest"]["chosen"] = blank
                res = stack.gaps(_capabilities(), s, catalog_dir=catalog)
                self.assertEqual(res["mandatory_unchosen"], ["gdpr/encryption-at-rest"], blank)

    def test_off_catalog_choice_is_informational_not_a_gap(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            s["choices"]["gdpr/encryption-at-rest"]["chosen"] = "Something else"
            res = stack.gaps(_capabilities(), s, catalog_dir=catalog)
            self.assertEqual(res["mandatory_unchosen"], [])          # still a decision
            self.assertEqual(len(res["off_catalog"]), 1)
            self.assertEqual(res["off_catalog"][0]["key"], "gdpr/encryption-at-rest")
            self.assertEqual(res["off_catalog"][0]["chosen"], "Something else")

    def test_orphaned_key_reported(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            s["choices"]["gdpr/removed-capability"] = {"chosen": "X", "options": []}
            res = stack.gaps(_capabilities(), s, catalog_dir=catalog)
            self.assertEqual(res["orphaned"], ["gdpr/removed-capability"])

    def test_missing_stack_file_is_all_unchosen(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            res = stack.gaps(_capabilities(), {}, catalog_dir=catalog)
            self.assertEqual(res["mandatory_unchosen"], ["gdpr/encryption-at-rest"])
            self.assertEqual(res["orphaned"], [])

    def test_stale_hash_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog, capabilities_hash="old")
            self.assertTrue(stack.gaps(_capabilities(), s, catalog_dir=catalog,
                                       capabilities_hash="new")["stale"])
            self.assertFalse(stack.gaps(_capabilities(), s, catalog_dir=catalog,
                                        capabilities_hash="old")["stale"])

    def test_hashless_stack_file_is_not_stale(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog, capabilities_hash="")
            self.assertFalse(stack.gaps(_capabilities(), s, catalog_dir=catalog,
                                        capabilities_hash="new")["stale"])


class TestRenderGapReport(unittest.TestCase):
    def test_lists_unchosen_mandatory_capability(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.scaffold(cat, None, catalog_dir=catalog)
            res = stack.gaps(cat, s, catalog_dir=catalog)
            md = stack.render_gap_report(cat, s, res, "2026-02-02")
            self.assertIn("# Stack Gap Report", md)
            self.assertIn("| Framework | Capabilities | Mandatory-linked | Chosen | Unchosen |", md)
            self.assertIn("**1 of 1 mandatory-linked capabilities have no chosen component.**", md)
            self.assertIn("`gdpr/encryption-at-rest`", md)
            self.assertIn("options: OpenBao; age", md)
            self.assertIn("`gdpr/consent-capture`", md)          # optional, informational

    def test_stale_warning_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.scaffold(cat, None, catalog_dir=catalog, capabilities_hash="old")
            res = stack.gaps(cat, s, catalog_dir=catalog, capabilities_hash="new")
            self.assertIn("**Stale**", stack.render_gap_report(cat, s, res, "2026-02-02"))

    def test_fully_chosen_reports_nothing_informational(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.scaffold(cat, None, catalog_dir=catalog)
            s["choices"]["gdpr/encryption-at-rest"]["chosen"] = "OpenBao"
            s["choices"]["gdpr/consent-capture"]["chosen"] = "Klaro!"
            res = stack.gaps(cat, s, catalog_dir=catalog)
            md = stack.render_gap_report(cat, s, res, "2026-02-02")
            self.assertIn("**0 of 1 mandatory-linked capabilities have no chosen component.**", md)
            self.assertIn("Nothing to report.", md)


if __name__ == "__main__":
    unittest.main()
