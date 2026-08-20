"""Pure-logic tests for rank_lib.py (component ranking). No LLM, no network, no SDK."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import rank_lib

POLICY = {
    "embeddable": ["MIT", "Apache-2.0", "BSD-3-Clause", "MPL-2.0", "CC0", "LGPL (dynamic)"],
    "not_in_product": ["GPL-3.0", "AGPL-3.0", "SSPL"],
    "internal_infra_exception": "operator-side components may carry any license",
}


def _capabilities() -> dict:
    """Two capabilities: one with two in-product options, one with a single option."""
    return {
        "generated": "2026-01-01",
        "frameworks": {"gdpr": {"capabilities": [
            {
                "name": "Encryption at rest",
                "category": "Data Protection",
                "description": "Encrypt stored personal data.",
                "satisfies": ["GDPR-ART5-01"],
                "stack": [
                    {"name": "OpenBao", "license": "MPL-2.0", "role": "in-product",
                     "verdict": "keep", "why": "self-hostable secret store"},
                    {"name": "age", "license": "BSD-3-Clause", "role": "in-product",
                     "verdict": "replaced", "replaced_from": "AWS KMS",
                     "why": "single-binary file encryption"},
                ],
            },
            {
                "name": "Consent capture",
                "category": "Governance & Privacy Ops",
                "description": "Record consent.",
                "satisfies": ["GDPR-ART7-01"],
                "stack": [
                    {"name": "Klaro!", "license": "BSD-3-Clause", "role": "in-product",
                     "verdict": "keep", "why": "self-hosted consent widget"},
                ],
            },
        ]}},
    }


def _stack(consent_applicable: bool = True) -> dict:
    return {"choices": {
        "gdpr/encryption-at-rest": {
            "capability": "Encryption at rest", "framework": "gdpr", "mandatory_linked": True,
            "options": ["OpenBao", "age"], "applicable": True,
        },
        "gdpr/consent-capture": {
            "capability": "Consent capture", "framework": "gdpr", "mandatory_linked": False,
            "options": ["Klaro!"], "applicable": consent_applicable,
            "applicability_reason": "" if consent_applicable else "no consent is collected",
        },
    }}


def _universe(consent_applicable: bool = True) -> list[dict]:
    return rank_lib.rankable_universe(_stack(consent_applicable), _capabilities())


def _full() -> dict:
    return {
        "gdpr/encryption-at-rest": [
            {"component": "age", "rationale": "single binary, matches the deployment"},
            {"component": "OpenBao", "rationale": "needs an operator we do not have"},
        ],
        "gdpr/consent-capture": [
            {"component": "Klaro!", "rationale": "the only option, and self-hostable"},
        ],
    }


class TestNormalizeLicense(unittest.TestCase):
    def test_maps_the_spellings_the_catalog_actually_uses(self) -> None:
        self.assertEqual(rank_lib.normalize_license("CC0-1.0"), "CC0")
        self.assertEqual(rank_lib.normalize_license("LGPL-2.1"), "LGPL (dynamic)")
        self.assertEqual(rank_lib.normalize_license("LGPL-3.0"), "LGPL (dynamic)")

    def test_passes_an_unmapped_license_through_untouched(self) -> None:
        self.assertEqual(rank_lib.normalize_license("MIT"), "MIT")
        self.assertEqual(rank_lib.normalize_license("CC-BY-SA-4.0"), "CC-BY-SA-4.0")
        self.assertEqual(rank_lib.normalize_license(None), "")


class TestLicenseCheck(unittest.TestCase):
    def test_internal_infra_may_carry_any_license(self) -> None:
        comp = {"name": "Grafana", "license": "AGPL-3.0", "role": "internal-infra",
                "verdict": "keep"}
        self.assertEqual(rank_lib.license_check(comp, POLICY), "ok")

    def test_embeddable_in_product_is_ok(self) -> None:
        comp = {"name": "age", "license": "BSD-3-Clause", "role": "in-product",
                "verdict": "keep"}
        self.assertEqual(rank_lib.license_check(comp, POLICY), "ok")

    def test_a_normalised_license_is_ok(self) -> None:
        """Semgrep is LGPL-2.1 in the catalog and 'LGPL (dynamic)' in the policy."""
        comp = {"name": "Semgrep", "license": "LGPL-2.1", "role": "in-product",
                "verdict": "keep"}
        self.assertEqual(rank_lib.license_check(comp, POLICY), "ok")

    def test_keep_exception_is_recorded_not_rejected(self) -> None:
        comp = {"name": "OWASP ASVS 5.0", "license": "CC-BY-SA-4.0", "role": "in-product",
                "verdict": "keep-exception"}
        self.assertEqual(rank_lib.license_check(comp, POLICY), "exception")

    def test_unjustified_copyleft_in_product_is_a_violation(self) -> None:
        comp = {"name": "Something", "license": "AGPL-3.0", "role": "in-product",
                "verdict": "keep"}
        self.assertEqual(rank_lib.license_check(comp, POLICY), "violation")

    def test_an_unknown_license_in_product_is_a_violation(self) -> None:
        """Not on either list and not excepted — fail loudly rather than assume."""
        comp = {"name": "Something", "license": "Weird-1.0", "role": "in-product",
                "verdict": "keep"}
        self.assertEqual(rank_lib.license_check(comp, POLICY), "violation")


class TestRankableUniverse(unittest.TestCase):
    def test_skips_capabilities_the_scoping_pass_ruled_out(self) -> None:
        keys = [u["key"] for u in _universe(consent_applicable=False)]
        self.assertEqual(keys, ["gdpr/encryption-at-rest"])

    def test_options_come_from_stack_json_and_carry_catalog_metadata(self) -> None:
        enc = next(u for u in _universe() if u["key"] == "gdpr/encryption-at-rest")
        self.assertEqual(enc["options"], ["OpenBao", "age"])
        self.assertEqual([c["name"] for c in enc["components"]], ["OpenBao", "age"])
        self.assertEqual(enc["components"][0]["license"], "MPL-2.0")
        self.assertEqual(enc["components"][1]["verdict"], "replaced")
        self.assertIn("single-binary", enc["components"][1]["why"])

    def test_an_option_the_catalog_no_longer_describes_still_appears(self) -> None:
        stack = _stack()
        stack["choices"]["gdpr/encryption-at-rest"]["options"] = ["OpenBao", "Vault"]
        enc = rank_lib.rankable_universe(stack, _capabilities())[0]
        self.assertEqual([c["name"] for c in enc["components"]], ["OpenBao", "Vault"])
        self.assertEqual(enc["components"][1]["license"], "")


class TestRankingGate(unittest.TestCase):
    def test_a_complete_ordering_passes(self) -> None:
        gate = rank_lib.ranking_gate(_universe(), _full(), POLICY)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["exceptions"], [])

    def test_an_applicable_capability_with_no_ranking_fails(self) -> None:
        rankings = {k: v for k, v in _full().items() if k != "gdpr/consent-capture"}
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["missing_rankings"], ["gdpr/consent-capture"])

    def test_a_ranking_for_an_unknown_capability_fails(self) -> None:
        rankings = _full()
        rankings["gdpr/invented"] = [{"component": "X", "rationale": "y"}]
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["unknown_rankings"], ["gdpr/invented"])

    def test_a_ranking_for_a_scoped_out_capability_fails(self) -> None:
        """A ruled-out capability is not in the universe, so ranking it is unknown."""
        gate = rank_lib.ranking_gate(_universe(consent_applicable=False), _full(), POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["unknown_rankings"], ["gdpr/consent-capture"])

    def test_an_omitted_option_fails(self) -> None:
        rankings = _full()
        rankings["gdpr/encryption-at-rest"] = [{"component": "age", "rationale": "r"}]
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["set_mismatches"][0]["missing"], ["OpenBao"])

    def test_an_invented_component_fails(self) -> None:
        rankings = _full()
        rankings["gdpr/encryption-at-rest"].append({"component": "SOPS", "rationale": "r"})
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["set_mismatches"][0]["unexpected"], ["SOPS"])

    def test_a_duplicated_component_fails(self) -> None:
        rankings = _full()
        rankings["gdpr/encryption-at-rest"] = [
            {"component": "age", "rationale": "first"},
            {"component": "age", "rationale": "again"},
            {"component": "OpenBao", "rationale": "third"},
        ]
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["set_mismatches"][0]["duplicated"], ["age"])

    def test_a_blank_rationale_fails(self) -> None:
        rankings = _full()
        rankings["gdpr/encryption-at-rest"][1]["rationale"] = "   "
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["blank_rationales"][0],
                         {"key": "gdpr/encryption-at-rest", "components": ["OpenBao"]})

    def test_an_empty_ranking_fails(self) -> None:
        rankings = _full()
        rankings["gdpr/encryption-at-rest"] = []
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["set_mismatches"][0]["missing"], ["OpenBao", "age"])

    def test_a_license_violation_fails_and_names_the_component(self) -> None:
        caps = _capabilities()
        caps["frameworks"]["gdpr"]["capabilities"][0]["stack"][0]["license"] = "AGPL-3.0"
        universe = rank_lib.rankable_universe(_stack(), caps)
        gate = rank_lib.ranking_gate(universe, _full(), POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["violations"][0]["component"], "OpenBao")
        self.assertEqual(gate["violations"][0]["license"], "AGPL-3.0")

    def test_a_keep_exception_is_recorded_and_the_gate_still_passes(self) -> None:
        caps = _capabilities()
        comp = caps["frameworks"]["gdpr"]["capabilities"][0]["stack"][0]
        comp["license"], comp["verdict"] = "CC-BY-SA-4.0", "keep-exception"
        universe = rank_lib.rankable_universe(_stack(), caps)
        gate = rank_lib.ranking_gate(universe, _full(), POLICY)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["exceptions"][0]["component"], "OpenBao")
        self.assertEqual(gate["exceptions"][0]["license"], "CC-BY-SA-4.0")


class TestRankingsPayload(unittest.TestCase):
    def test_strips_and_carries_the_hash(self) -> None:
        rankings = {"gdpr/consent-capture": [{"component": " Klaro! ", "rationale": " only  "}]}
        payload = rank_lib.rankings_payload(rankings, "prod-4c11")
        self.assertEqual(payload["ranked_from"], "prod-4c11")
        self.assertEqual(payload["rankings"]["gdpr/consent-capture"],
                         [{"component": "Klaro!", "rationale": "only"}])


class TestRenderRankReport(unittest.TestCase):
    def test_lists_the_ordering_with_every_rationale(self) -> None:
        gate = rank_lib.ranking_gate(_universe(), _full(), POLICY)
        out = rank_lib.render_rank_report(_universe(), _full(), gate, "prod-1", "2026-08-20")
        self.assertIn("1. **age** — single binary, matches the deployment", out)
        self.assertIn("2. **OpenBao** — needs an operator we do not have", out)
        self.assertIn("*(mandatory-linked)*", out)

    def test_a_failed_gate_says_nothing_was_written(self) -> None:
        rankings = {k: v for k, v in _full().items() if k != "gdpr/consent-capture"}
        gate = rank_lib.ranking_gate(_universe(), rankings, POLICY)
        out = rank_lib.render_rank_report(_universe(), rankings, gate, "prod-1", "2026-08-20")
        self.assertIn("This run wrote nothing", out)
        self.assertIn("gdpr/consent-capture", out)

    def test_a_violation_names_the_catalog_as_the_place_to_fix_it(self) -> None:
        caps = _capabilities()
        caps["frameworks"]["gdpr"]["capabilities"][0]["stack"][0]["license"] = "AGPL-3.0"
        universe = rank_lib.rankable_universe(_stack(), caps)
        gate = rank_lib.ranking_gate(universe, _full(), POLICY)
        out = rank_lib.render_rank_report(universe, _full(), gate, "prod-1", "2026-08-20")
        self.assertIn("License policy violations", out)
        self.assertIn("capabilities.json", out)

    def test_a_recorded_exception_is_quoted_with_its_reasoning(self) -> None:
        caps = _capabilities()
        comp = caps["frameworks"]["gdpr"]["capabilities"][0]["stack"][0]
        comp["license"], comp["verdict"] = "CC-BY-SA-4.0", "keep-exception"
        universe = rank_lib.rankable_universe(_stack(), caps)
        gate = rank_lib.ranking_gate(universe, _full(), POLICY)
        out = rank_lib.render_rank_report(universe, _full(), gate, "prod-1", "2026-08-20")
        self.assertIn("Recorded license exceptions", out)
        self.assertIn("self-hostable secret store", out)


if __name__ == "__main__":
    unittest.main()
