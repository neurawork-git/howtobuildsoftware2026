"""Pure-logic tests for scope_lib.py (product scoping). No LLM, no network, no SDK."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import scope_lib  # noqa: E402

MAND = {"gdpr": {"GDPR-ART5-01", "GDPR-ART32-01"}}


def _capabilities() -> dict:
    """Two capabilities both covering GDPR-ART5-01; one also covers GDPR-ART32-01."""
    return {
        "generated": "2026-01-01",
        "frameworks": {"gdpr": {"capabilities": [
            {
                "name": "Encryption at rest",
                "category": "Data Protection",
                "description": "Encrypt stored personal data.",
                "satisfies": ["GDPR-ART5-01", "GDPR-ART32-01"],
            },
            {
                "name": "Access control",
                "category": "IAM",
                "description": "Restrict who can read stored data.",
                "satisfies": ["GDPR-ART5-01"],
            },
            {
                "name": "Consent capture",
                "category": "Governance & Privacy Ops",
                "description": "Record consent.",
                "satisfies": ["GDPR-ART7-01"],       # optional only
            },
        ]}},
    }


def _stack() -> dict:
    return {"choices": {
        "gdpr/encryption-at-rest": {"capability": "Encryption at rest", "framework": "gdpr",
                                    "mandatory_linked": True},
        "gdpr/access-control": {"capability": "Access control", "framework": "gdpr",
                                "mandatory_linked": True},
        "gdpr/consent-capture": {"capability": "Consent capture", "framework": "gdpr",
                                 "mandatory_linked": False},
    }}


def _universe() -> list[dict]:
    return scope_lib.capability_universe(_stack(), _capabilities())


def _all_applicable() -> dict:
    return {u["key"]: {"applicable": True, "reason": ""} for u in _universe()}


class TestProductHash(unittest.TestCase):
    def test_stable_and_content_sensitive(self) -> None:
        a = scope_lib.product_hash("we store user emails")
        self.assertEqual(a, scope_lib.product_hash("we store user emails"))
        self.assertNotEqual(a, scope_lib.product_hash("we store user emails."))
        self.assertEqual(len(a), 16)


class TestMandatoryIdsFor(unittest.TestCase):
    def _catalog(self, tmp: Path) -> Path:
        (tmp / "gdpr.json").write_text(json.dumps({"constraints": [
            {"id": "GDPR-ART5-01", "mandatory": True},
            {"id": "GDPR-ART7-01", "mandatory": False},
            {"id": "GDPR-ART32-01"},                 # unspecified ⇒ mandatory
        ]}), encoding="utf-8")
        return tmp

    def test_defaults_to_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            got = scope_lib.mandatory_ids_for("gdpr", self._catalog(Path(t)))
            self.assertEqual(got, {"GDPR-ART5-01", "GDPR-ART32-01"})

    def test_missing_framework_file_is_empty_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(scope_lib.mandatory_ids_for("soc2", Path(t)), set())


class TestCapabilityUniverse(unittest.TestCase):
    def test_keys_come_from_stack_json(self) -> None:
        keys = [u["key"] for u in _universe()]
        self.assertEqual(keys, list(_stack()["choices"]))

    def test_joins_description_by_name(self) -> None:
        enc = next(u for u in _universe() if u["key"] == "gdpr/encryption-at-rest")
        self.assertEqual(enc["description"], "Encrypt stored personal data.")
        self.assertEqual(enc["category"], "Data Protection")
        self.assertEqual(enc["satisfies"], ["GDPR-ART5-01", "GDPR-ART32-01"])
        self.assertTrue(enc["mandatory_linked"])

    def test_capability_the_catalog_no_longer_describes_still_appears(self) -> None:
        stack = _stack()
        stack["choices"]["gdpr/ghost"] = {"capability": "Ghost", "framework": "gdpr",
                                          "mandatory_linked": False}
        universe = scope_lib.capability_universe(stack, _capabilities())
        ghost = next(u for u in universe if u["key"] == "gdpr/ghost")
        self.assertEqual(ghost["description"], "")
        self.assertEqual(ghost["satisfies"], [])


class TestSafetyGate(unittest.TestCase):
    def test_all_applicable_passes(self) -> None:
        gate = scope_lib.safety_gate(_universe(), _all_applicable(), MAND)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["justified_drops"], [])
        self.assertEqual(gate["uncovered_upstream"], [])

    def test_blank_reason_on_a_drop_fails(self) -> None:
        for reason in ("", "   "):
            decisions = _all_applicable()
            decisions["gdpr/consent-capture"] = {"applicable": False, "reason": reason}
            gate = scope_lib.safety_gate(_universe(), decisions, MAND)
            self.assertFalse(gate["ok"], repr(reason))
            self.assertEqual(gate["blank_reasons"], ["gdpr/consent-capture"])

    def test_unreasoned_drop_of_the_only_cover_fails(self) -> None:
        """GDPR-ART32-01 is covered by encryption-at-rest alone."""
        decisions = _all_applicable()
        decisions["gdpr/encryption-at-rest"] = {"applicable": False, "reason": ""}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["unjustified_mandatory"],
                         [{"constraint": "GDPR-ART32-01",
                           "capabilities": ["gdpr/encryption-at-rest"]}])

    def test_reasoned_drop_of_the_only_cover_passes_and_is_recorded(self) -> None:
        decisions = _all_applicable()
        decisions["gdpr/encryption-at-rest"] = {
            "applicable": False, "reason": "the service persists nothing to disk"}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["justified_drops"],
                         [{"constraint": "GDPR-ART32-01",
                           "capabilities": ["gdpr/encryption-at-rest"]}])

    def test_a_second_applicable_cover_keeps_the_constraint_satisfied(self) -> None:
        """GDPR-ART5-01 has two covers; dropping one leaves it covered, so no drop
        is recorded for it — only GDPR-ART32-01 becomes a justified drop."""
        decisions = _all_applicable()
        decisions["gdpr/encryption-at-rest"] = {
            "applicable": False, "reason": "the service persists nothing to disk"}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        dropped = {d["constraint"] for d in gate["justified_drops"]}
        self.assertNotIn("GDPR-ART5-01", dropped)

    def test_dropping_every_cover_unreasoned_fails(self) -> None:
        decisions = _all_applicable()
        decisions["gdpr/encryption-at-rest"] = {"applicable": False, "reason": "no disk"}
        decisions["gdpr/access-control"] = {"applicable": False, "reason": ""}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        self.assertFalse(gate["ok"])
        offending = next(d for d in gate["unjustified_mandatory"]
                         if d["constraint"] == "GDPR-ART5-01")
        self.assertEqual(offending["capabilities"], ["gdpr/access-control"])

    def test_missing_decision_fails(self) -> None:
        decisions = _all_applicable()
        del decisions["gdpr/access-control"]
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["missing_decisions"], ["gdpr/access-control"])

    def test_unknown_decision_fails(self) -> None:
        decisions = _all_applicable()
        decisions["gdpr/invented"] = {"applicable": True, "reason": ""}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["unknown_decisions"], ["gdpr/invented"])

    def test_constraint_no_capability_covers_is_upstream_not_a_scoping_failure(self) -> None:
        gate = scope_lib.safety_gate(_universe(), _all_applicable(),
                                     {"gdpr": {"GDPR-ART5-01", "GDPR-ART99-99"}})
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["uncovered_upstream"], ["GDPR-ART99-99"])


class TestDecisionsPayload(unittest.TestCase):
    def test_maps_reason_onto_the_schema_owners_field(self) -> None:
        decisions = _all_applicable()
        decisions["gdpr/consent-capture"] = {"applicable": False, "reason": " no consent  "}
        payload = scope_lib.decisions_payload(decisions, "prod-abc")
        self.assertEqual(payload["scoped_from"], "prod-abc")
        self.assertEqual(set(payload["decisions"]), set(_all_applicable()))
        con = payload["decisions"]["gdpr/consent-capture"]
        self.assertFalse(con["applicable"])
        self.assertEqual(con["applicability_reason"], "no consent")
        self.assertNotIn("reason", con)


class TestRenderScopeReport(unittest.TestCase):
    def test_lists_ruled_out_capabilities_and_justified_drops(self) -> None:
        decisions = _all_applicable()
        decisions["gdpr/encryption-at-rest"] = {
            "applicable": False, "reason": "the service persists nothing to disk"}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        md = scope_lib.render_scope_report(_universe(), decisions, gate, "prod-abc",
                                           "2026-02-02", product_path="product.md")
        self.assertIn("# Product Scope Report", md)
        self.assertIn("scope hash `prod-abc`", md)
        self.assertIn("**Encryption at rest** (`gdpr/encryption-at-rest`) *(mandatory-linked)* "
                      "— the service persists nothing to disk", md)
        self.assertIn("`GDPR-ART32-01` — via `gdpr/encryption-at-rest`", md)
        self.assertNotIn("This run wrote nothing", md)

    def test_failed_gate_says_nothing_was_written(self) -> None:
        decisions = _all_applicable()
        decisions["gdpr/encryption-at-rest"] = {"applicable": False, "reason": ""}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        md = scope_lib.render_scope_report(_universe(), decisions, gate, "prod-abc", "2026-02-02")
        self.assertIn("**This run wrote nothing.**", md)
        self.assertIn("Mandatory constraints dropped without a reason", md)
        self.assertIn("`GDPR-ART32-01`", md)

    def test_refutation_is_quoted_back(self) -> None:
        decisions = _all_applicable()
        decisions["gdpr/consent-capture"] = {
            "applicable": False, "reason": "no personal data is processed"}
        gate = scope_lib.safety_gate(_universe(), decisions, MAND)
        md = scope_lib.render_scope_report(
            _universe(), decisions, gate, "prod-abc", "2026-02-02",
            refuted=[{"key": "gdpr/consent-capture",
                      "evidence": "we store the user's email address"}])
        self.assertIn("## Refuted decisions (1)", md)
        self.assertIn("claimed: no personal data is processed", md)
        self.assertIn("contradicted by: we store the user's email address", md)
        self.assertIn("**This run wrote nothing.**", md)


if __name__ == "__main__":
    unittest.main()
