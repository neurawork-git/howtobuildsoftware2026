"""Pure-logic tests for cap_lib (capability derivation). No LLM, no network."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cap_lib  # noqa: E402


def _catalog(tmp: Path) -> Path:
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


class TestSlug(unittest.TestCase):
    def test_strips_trailing_parenthetical(self) -> None:
        self.assertEqual(cap_lib.capability_slug("Audit logging (SOC2 CC7)"), "audit-logging")

    def test_strips_em_dash_clause(self) -> None:
        self.assertEqual(cap_lib.capability_slug("Data portability — export service"),
                         "data-portability")

    def test_keeps_ampersand_and_inner_hyphen(self) -> None:
        self.assertEqual(cap_lib.capability_slug("RBAC & least privilege"),
                         "rbac-least-privilege")
        self.assertEqual(cap_lib.capability_slug("Data-subject request handling"),
                         "data-subject-request-handling")

    def test_clean_and_suffixed_names_share_slug(self) -> None:
        self.assertEqual(
            cap_lib.capability_slug("Encryption at rest"),
            cap_lib.capability_slug("Encryption at rest (per GDPR Art. 32)"),
        )


class TestCoverageGap(unittest.TestCase):
    CONSTRAINTS = [
        {"id": "GDPR-ART5-01", "mandatory": True},
        {"id": "GDPR-ART5-02", "mandatory": True},
        {"id": "GDPR-ART7-01", "mandatory": False},
    ]

    def test_complete_coverage_no_gap(self) -> None:
        caps = [{"name": "a", "satisfies": ["GDPR-ART5-01", "GDPR-ART7-01"]},
                {"name": "b", "satisfies": ["GDPR-ART5-02"]}]
        self.assertEqual(cap_lib.coverage_gap(caps, self.CONSTRAINTS), [])

    def test_missing_mandatory_surfaced(self) -> None:
        caps = [{"name": "a", "satisfies": ["GDPR-ART5-01"]}]  # ART5-02 dropped
        self.assertEqual(cap_lib.coverage_gap(caps, self.CONSTRAINTS), ["GDPR-ART5-02"])

    def test_non_mandatory_never_a_gap(self) -> None:
        caps = [{"name": "a", "satisfies": ["GDPR-ART5-01", "GDPR-ART5-02"]}]  # ART7-01 (opt) absent
        self.assertEqual(cap_lib.coverage_gap(caps, self.CONSTRAINTS), [])


class TestAssemble(unittest.TestCase):
    def test_schema_and_slug_join(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _catalog(Path(t))
            clusters = {"gdpr": [{
                "name": "Encryption at rest",
                "category": "Data Protection",
                "description": "Encrypt stored personal data.",
                "satisfies": ["GDPR-ART5-01", "GDPR-ART5-02"],
            }]}
            # stack agent appended a parenthetical to the capability name → slug must still join
            stacks = [{"capability": "Encryption at rest (storage layer)",
                       "components": [{"name": "AWS KMS", "kind": "managed", "why": "envelope keys"}],
                       "notes": "rotate annually"}]
            cat = cap_lib.assemble_catalog(clusters, stacks, catalog_dir=catalog,
                                           generated="2026-01-01")
            self.assertEqual(cat["generated"], "2026-01-01")
            self.assertIn("gdpr", cat["frameworks"])
            f = cat["frameworks"]["gdpr"]
            self.assertEqual(f["capability_count"], 1)
            self.assertEqual(f["mandatory_covered"], 2)
            self.assertEqual(f["mandatory_total"], 2)
            self.assertEqual(f["uncovered_mandatory_ids"], [])
            c = f["capabilities"][0]
            self.assertEqual(set(c),
                             {"name", "category", "description", "satisfies", "stack", "stack_notes"})
            self.assertEqual(c["stack"][0]["name"], "AWS KMS")  # joined despite suffix
            self.assertEqual(c["stack_notes"], "rotate annually")

    def test_uncovered_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _catalog(Path(t))
            clusters = {"gdpr": [{"name": "Partial", "category": "IAM",
                                  "description": "", "satisfies": ["GDPR-ART5-01"]}]}
            cat = cap_lib.assemble_catalog(clusters, [], catalog_dir=catalog,
                                           generated="2026-01-01")
            self.assertEqual(cat["frameworks"]["gdpr"]["uncovered_mandatory_ids"],
                             ["GDPR-ART5-02"])


class TestMergePreserving(unittest.TestCase):
    def test_subset_run_keeps_other_frameworks(self) -> None:
        existing = {"generated": "2026-01-01", "frameworks": {
            "gdpr": {"capability_count": 25, "capabilities": []},
            "soc2": {"capability_count": 25, "capabilities": []},
            "iso27001": {"capability_count": 18, "capabilities": []},
        }}
        # a --frameworks gdpr run only re-derives gdpr
        fresh = {"generated": "2026-02-02", "frameworks": {
            "gdpr": {"capability_count": 30, "capabilities": []},
        }}
        merged = cap_lib.merge_preserving(existing, fresh)
        self.assertEqual(set(merged["frameworks"]), {"gdpr", "soc2", "iso27001"})
        self.assertEqual(merged["frameworks"]["gdpr"]["capability_count"], 30)  # fresh wins
        self.assertEqual(merged["frameworks"]["soc2"]["capability_count"], 25)  # preserved
        self.assertEqual(merged["generated"], "2026-02-02")  # top-level from fresh run

    def test_empty_existing_is_just_fresh(self) -> None:
        fresh = {"generated": "x", "frameworks": {"gdpr": {"capability_count": 1}}}
        self.assertEqual(cap_lib.merge_preserving({}, fresh), fresh)


class TestRender(unittest.TestCase):
    def _catalog_obj(self) -> dict:
        return {
            "generated": "2026-01-01",
            "frameworks": {"gdpr": {
                "capability_count": 1,
                "mandatory_covered": 2,
                "mandatory_total": 2,
                "uncovered_mandatory_ids": [],
                "capabilities": [{
                    "name": "Encryption at rest",
                    "category": "Data Protection",
                    "description": "Encrypt stored data.",
                    "satisfies": ["GDPR-ART5-01", "GDPR-ART5-02"],
                    "stack": [{"name": "AWS KMS", "kind": "managed", "why": "keys"}],
                    "stack_notes": "",
                }],
            }},
        }

    def test_capabilities_md(self) -> None:
        md = cap_lib.render_capabilities_md(self._catalog_obj())
        self.assertIn("# Capability Catalog", md)
        self.assertIn("| Framework | Capabilities | Mandatory covered | Uncovered |", md)
        self.assertIn("### Encryption at rest", md)
        self.assertIn("**Stack (greenfield 2026):** AWS KMS", md)
        self.assertIn("<sub>GDPR-ART5-01, GDPR-ART5-02</sub>", md)

    def test_index(self) -> None:
        meta = [{"framework": "gdpr", "count": 3, "mandatory": 2, "generated": "2026-01-01"}]
        idx = cap_lib.render_index(meta, self._catalog_obj())
        self.assertIn("# Compliance Catalog", idx)
        self.assertIn("| gdpr | 3 | 2 | 2026-01-01 |", idx)
        self.assertIn("## Derived capabilities", idx)
        self.assertIn("| gdpr | 1 | 2/2 | 2026-01-01 |", idx)


if __name__ == "__main__":
    unittest.main()
