"""Pure-logic tests for selection_lib.py (the sheet, its parser, the gate).

No LLM, no network, no SDK.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import selection_lib

POLICY = {
    "embeddable": ["MIT", "Apache-2.0", "BSD-3-Clause", "MPL-2.0"],
    "not_in_product": ["GPL-3.0", "AGPL-3.0", "SSPL"],
    "internal_infra_exception": "operator-side components may carry any license",
}


def _capabilities() -> dict:
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
                     "verdict": "keep", "why": "single-binary file encryption"},
                ],
            },
            {
                "name": "Consent capture",
                "category": "Governance & Privacy Ops",
                "description": "Record consent.",
                "satisfies": ["GDPR-ART7-01"],
                "stack": [{"name": "Klaro!", "license": "Apache-2.0", "role": "in-product",
                           "verdict": "keep", "why": "consent banner"}],
            },
        ]}},
    }


def _stack(enc: dict | None = None) -> dict:
    """A scoped + ranked stack: encryption applicable and ranked, consent scoped out.

    ``enc`` patches the encryption entry — the one every test varies.
    """
    choices = {
        "gdpr/encryption-at-rest": {
            "capability": "Encryption at rest",
            "framework": "gdpr",
            "mandatory_linked": True,
            "options": ["OpenBao", "age"],
            "chosen": None,
            "rationale": "",
            "chosen_from": None,
            "applicable": True,
            "applicability_reason": "",
            "scoped_from": "prod-1",
            "ranked": [{"component": "age", "rationale": "single binary, no operator"},
                       {"component": "OpenBao", "rationale": "needs an operator"}],
            "ranked_from": "prod-1",
        },
        "gdpr/consent-capture": {
            "capability": "Consent capture",
            "framework": "gdpr",
            "mandatory_linked": False,
            "options": ["Klaro!"],
            "chosen": None,
            "rationale": "",
            "chosen_from": None,
            "applicable": False,
            "applicability_reason": "no consent is ever collected",
            "scoped_from": "prod-1",
            "ranked": None,
            "ranked_from": None,
        },
    }
    choices["gdpr/encryption-at-rest"].update(enc or {})
    return {"choices": choices}


def _universe(enc: dict | None = None) -> list[dict]:
    return selection_lib.selectable_universe(_stack(enc), _capabilities())


class TestSelectableUniverse(unittest.TestCase):
    def test_only_applicable_capabilities(self) -> None:
        self.assertEqual([u["key"] for u in _universe()], ["gdpr/encryption-at-rest"])

    def test_order_follows_the_recorded_ranking(self) -> None:
        u = _universe()[0]
        self.assertEqual(u["order"], ["age", "OpenBao"])   # ranked order, not catalog order
        self.assertEqual(u["options"], ["OpenBao", "age"])  # the pool itself is untouched
        self.assertTrue(u["ranked"])
        self.assertEqual(u["rationales"]["age"], "single binary, no operator")

    def test_an_unranked_capability_falls_back_to_catalog_order(self) -> None:
        u = _universe({"ranked": None})[0]
        self.assertEqual(u["order"], ["OpenBao", "age"])
        self.assertFalse(u["ranked"])

    def test_a_partial_ranking_still_covers_the_whole_pool(self) -> None:
        # An option the ranking never named must not drop off the sheet.
        u = _universe({"ranked": [{"component": "age", "rationale": "fits"}]})[0]
        self.assertEqual(sorted(u["order"]), sorted(u["options"]))
        self.assertEqual(u["order"][0], "age")

    def test_carries_an_existing_choice(self) -> None:
        u = _universe({"chosen": "age"})[0]
        self.assertEqual(u["chosen"], "age")


class TestRenderSheet(unittest.TestCase):
    def test_lists_only_applicable_keys_with_blank_choices(self) -> None:
        md = selection_lib.render_sheet(_universe(), "2026-02-02", stack_path="c/stack.json")
        self.assertIn("## gdpr/encryption-at-rest", md)
        self.assertNotIn("gdpr/consent-capture", md)   # scoped out: nothing to choose
        self.assertIn("1. **age** — single binary, no operator", md)
        self.assertIn("2. **OpenBao** — needs an operator", md)
        self.assertIn("\nchoice:\n", md)               # blank: no auto-pick
        self.assertIn("*mandatory-linked*", md)

    def test_a_recorded_choice_is_prefilled_so_a_rerender_resumes(self) -> None:
        md = selection_lib.render_sheet(_universe({"chosen": "age"}), "2026-02-02")
        self.assertIn("choice: age", md)
        self.assertIn("1 chosen, 0 undecided", md)

    def test_an_unranked_capability_is_flagged(self) -> None:
        md = selection_lib.render_sheet(_universe({"ranked": None}), "2026-02-02")
        self.assertIn("Not ranked", md)


class TestParseSheet(unittest.TestCase):
    def _filled(self, choice: str, reason: str = "") -> str:
        universe = _universe()
        md = selection_lib.render_sheet(universe, "2026-02-02")
        md = md.replace("choice:\n", f"choice: {choice}\n", 1)
        if reason:
            md = md.replace("reason:\n", f"reason: {reason}\n", 1)
        return md

    def test_round_trip_with_a_rank_number(self) -> None:
        out = selection_lib.parse_sheet(self._filled("1"), _universe())
        self.assertEqual(out, {"gdpr/encryption-at-rest": {"chosen": "age", "rationale": ""}})

    def test_round_trip_with_an_exact_name_and_a_reason(self) -> None:
        out = selection_lib.parse_sheet(self._filled("OpenBao", "already operated"), _universe())
        self.assertEqual(out["gdpr/encryption-at-rest"],
                         {"chosen": "OpenBao", "rationale": "already operated"})

    def test_a_blank_choice_is_still_deciding_not_an_error(self) -> None:
        md = selection_lib.render_sheet(_universe(), "2026-02-02")
        self.assertEqual(selection_lib.parse_sheet(md, _universe()), {})

    def test_a_rank_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError) as e:
            selection_lib.parse_sheet(self._filled("7"), _universe())
        self.assertIn("has no rank 7", str(e.exception))

    def test_a_component_not_in_the_block_raises(self) -> None:
        with self.assertRaises(ValueError) as e:
            selection_lib.parse_sheet(self._filled("HashiCorp Vault"), _universe())
        self.assertIn("no component 'HashiCorp Vault'", str(e.exception))

    def test_a_heading_for_a_scoped_out_capability_raises(self) -> None:
        md = self._filled("1") + "\n## gdpr/consent-capture\n\nchoice: Klaro!\n"
        with self.assertRaises(ValueError) as e:
            selection_lib.parse_sheet(md, _universe())
        self.assertIn("not an applicable capability", str(e.exception))

    def test_a_duplicate_heading_raises(self) -> None:
        md = self._filled("1") * 2
        with self.assertRaises(ValueError) as e:
            selection_lib.parse_sheet(md, _universe())
        self.assertIn("appears twice", str(e.exception))

    def test_a_second_choice_line_in_one_block_raises(self) -> None:
        md = self._filled("1").replace("choice: 1\n", "choice: 1\nchoice: OpenBao\n", 1)
        with self.assertRaises(ValueError) as e:
            selection_lib.parse_sheet(md, _universe())
        self.assertIn("second 'choice:' line", str(e.exception))

    def test_a_choice_outside_any_block_raises(self) -> None:
        with self.assertRaises(ValueError) as e:
            selection_lib.parse_sheet("choice: age\n", _universe())
        self.assertIn("does not belong to a capability block", str(e.exception))

    def test_every_problem_is_reported_at_once(self) -> None:
        md = self._filled("9") + "\n## gdpr/nope\n\nchoice: age\n"
        with self.assertRaises(ValueError) as e:
            selection_lib.parse_sheet(md, _universe())
        self.assertIn("has no rank 9", str(e.exception))
        self.assertIn("gdpr/nope", str(e.exception))

    def test_the_numbered_list_is_prose_and_is_never_parsed(self) -> None:
        # Corrupt the rendered list; the recorded order still resolves the number.
        md = self._filled("2").replace("1. **age**", "1. **NOT A COMPONENT**")
        self.assertEqual(selection_lib.parse_sheet(md, _universe())
                         ["gdpr/encryption-at-rest"]["chosen"], "OpenBao")


class TestSelectionGate(unittest.TestCase):
    def test_a_pool_member_passes(self) -> None:
        gate = selection_lib.selection_gate(
            _universe(), {"gdpr/encryption-at-rest": {"chosen": "age"}}, POLICY)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["pending"], [])

    def test_a_component_outside_the_pool_fails(self) -> None:
        gate = selection_lib.selection_gate(
            _universe(), {"gdpr/encryption-at-rest": {"chosen": "Vault"}}, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["off_pool"][0]["chosen"], "Vault")

    def test_a_scoped_out_capability_is_unknown_here(self) -> None:
        gate = selection_lib.selection_gate(
            _universe(), {"gdpr/consent-capture": {"chosen": "Klaro!"}}, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["unknown"], ["gdpr/consent-capture"])

    def test_a_blank_choice_fails(self) -> None:
        gate = selection_lib.selection_gate(
            _universe(), {"gdpr/encryption-at-rest": {"chosen": "  "}}, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["blank"], ["gdpr/encryption-at-rest"])

    def test_a_partial_pass_is_legitimate(self) -> None:
        gate = selection_lib.selection_gate(_universe(), {}, POLICY)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["pending"], ["gdpr/encryption-at-rest"])

    def test_a_keep_exception_license_is_recorded_not_rejected(self) -> None:
        caps = _capabilities()
        caps["frameworks"]["gdpr"]["capabilities"][0]["stack"][1].update(
            {"license": "AGPL-3.0", "verdict": "keep-exception", "why": "audited deviation"})
        universe = selection_lib.selectable_universe(_stack(), caps)
        gate = selection_lib.selection_gate(
            universe, {"gdpr/encryption-at-rest": {"chosen": "age"}}, POLICY)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["exceptions"][0]["component"], "age")

    def test_a_license_violation_fails(self) -> None:
        caps = _capabilities()
        caps["frameworks"]["gdpr"]["capabilities"][0]["stack"][1]["license"] = "AGPL-3.0"
        universe = selection_lib.selectable_universe(_stack(), caps)
        gate = selection_lib.selection_gate(
            universe, {"gdpr/encryption-at-rest": {"chosen": "age"}}, POLICY)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["violations"][0]["license"], "AGPL-3.0")


class TestSelectionsPayload(unittest.TestCase):
    def test_strips_and_sorts(self) -> None:
        out = selection_lib.selections_payload(
            {"b/x": {"chosen": " age ", "rationale": " r "}, "a/y": {"chosen": "OpenBao"}})
        self.assertEqual(list(out["selections"]), ["a/y", "b/x"])
        self.assertEqual(out["selections"]["b/x"], {"chosen": "age", "rationale": "r"})
        self.assertEqual(out["selections"]["a/y"]["rationale"], "")


class TestRenderSelectReport(unittest.TestCase):
    def test_records_the_choice_and_its_rank_position(self) -> None:
        universe = _universe()
        selections = {"gdpr/encryption-at-rest": {"chosen": "OpenBao", "rationale": "operated"}}
        gate = selection_lib.selection_gate(universe, selections, POLICY)
        md = selection_lib.render_select_report(universe, selections, gate, "2026-02-02")
        self.assertIn("**Encryption at rest** (`gdpr/encryption-at-rest`) → **OpenBao**", md)
        self.assertIn("rank 2 of 2", md)
        self.assertIn("operated", md)

    def test_a_failed_gate_says_nothing_was_written(self) -> None:
        universe = _universe()
        selections = {"gdpr/encryption-at-rest": {"chosen": "Vault"}}
        gate = selection_lib.selection_gate(universe, selections, POLICY)
        md = selection_lib.render_select_report(universe, selections, gate, "2026-02-02")
        self.assertIn("This run wrote nothing", md)
        self.assertIn("outside the capability's pool", md)

    def test_pending_capabilities_are_listed(self) -> None:
        universe = _universe()
        gate = selection_lib.selection_gate(universe, {}, POLICY)
        md = selection_lib.render_select_report(universe, {}, gate, "2026-02-02")
        self.assertIn("Still undecided (1)", md)


if __name__ == "__main__":
    unittest.main()
