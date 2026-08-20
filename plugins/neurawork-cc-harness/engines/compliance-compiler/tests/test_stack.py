"""Pure-logic tests for stack.py (capability→component mapping). No LLM, no network."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import stack


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
            self.assertIsNone(enc["ranked"])            # None, not []: never ranked ≠ ranked empty
            self.assertIsNone(enc["ranked_from"])
            self.assertIsNone(enc["chosen_from"])
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

    def test_preserves_component_ranking(self) -> None:
        """A re-scaffold must not erase the stack-compiler's ranking pass either."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            existing = {"choices": {"gdpr/encryption-at-rest": {
                "options": ["Vault"],           # stale — must be recomputed
                "ranked": [{"component": "age", "rationale": "single binary, no server"},
                           {"component": "OpenBao", "rationale": "needs an operator"}],
                "ranked_from": "prod-4c11",
            }}}
            out = stack.scaffold(_capabilities(), existing, catalog_dir=catalog)
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual([r["component"] for r in enc["ranked"]], ["age", "OpenBao"])
            self.assertEqual(enc["ranked_from"], "prod-4c11")
            self.assertEqual(enc["options"], ["OpenBao", "age"])   # machine field still refreshed

    def test_preserves_the_catalog_reference_of_a_choice(self) -> None:
        """Losing chosen_from here would silently disable staleness detection."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            existing = {"choices": {"gdpr/encryption-at-rest": {
                "chosen": "OpenBao",
                "chosen_from": "1e23e943fe51caae",
            }}}
            out = stack.scaffold(_capabilities(), existing, catalog_dir=catalog)
            self.assertEqual(out["choices"]["gdpr/encryption-at-rest"]["chosen_from"],
                             "1e23e943fe51caae")

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

    def test_non_applicable_is_not_a_gap_and_leaves_the_total(self) -> None:
        """A capability scoped out of the product is a decision, not a pending one."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            s["choices"]["gdpr/encryption-at-rest"].update(
                applicable=False, applicability_reason="product stores no data at rest")
            res = stack.gaps(_capabilities(), s, catalog_dir=catalog)
            self.assertEqual(res["mandatory_unchosen"], [])
            self.assertEqual(res["mandatory_total"], 0)     # excluded from the denominator too
            self.assertEqual(res["non_applicable"], ["gdpr/encryption-at-rest"])
            self.assertEqual(res["unexplained_non_applicable"], [])
            self.assertEqual(res["mandatory_linked"], ["gdpr/encryption-at-rest"])  # still known

    def test_non_applicable_without_reason_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            for reason in ("", "   "):
                s = self._scaffolded(catalog)
                s["choices"]["gdpr/encryption-at-rest"].update(
                    applicable=False, applicability_reason=reason)
                res = stack.gaps(_capabilities(), s, catalog_dir=catalog)
                self.assertEqual(res["unexplained_non_applicable"],
                                 ["gdpr/encryption-at-rest"], repr(reason))

    def test_unscoped_stack_is_unaffected(self) -> None:
        """Every entry applicable (the scaffold default) ⇒ pre-scoping behaviour."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            res = stack.gaps(_capabilities(), self._scaffolded(catalog), catalog_dir=catalog)
            self.assertEqual(res["mandatory_total"], 1)
            self.assertEqual(res["mandatory_unchosen"], ["gdpr/encryption-at-rest"])
            self.assertEqual(res["non_applicable"], [])
            self.assertEqual(res["unexplained_non_applicable"], [])


class TestApplyScope(unittest.TestCase):
    """The single write path the stack-compiler skill uses for applicability."""

    def _scaffolded(self, catalog: Path) -> dict:
        return stack.scaffold(_capabilities(), None, catalog_dir=catalog)

    def _all_applicable(self, s: dict) -> dict:
        return {k: {"applicable": True, "applicability_reason": ""} for k in s["choices"]}

    def test_writes_all_three_fields(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            decisions = self._all_applicable(s)
            decisions["gdpr/consent-capture"] = {
                "applicable": False, "applicability_reason": "no consent is ever collected"}
            out = stack.apply_scope(s, decisions, "prod-9f21")
            enc = out["choices"]["gdpr/encryption-at-rest"]
            con = out["choices"]["gdpr/consent-capture"]
            self.assertTrue(enc["applicable"])
            self.assertEqual(enc["scoped_from"], "prod-9f21")
            self.assertFalse(con["applicable"])
            self.assertEqual(con["applicability_reason"], "no consent is ever collected")
            self.assertEqual(con["scoped_from"], "prod-9f21")

    def test_never_touches_the_component_decision(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            s["choices"]["gdpr/encryption-at-rest"].update(
                chosen="OpenBao", rationale="already self-hosted")
            out = stack.apply_scope(s, self._all_applicable(s), "prod-1")
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual(enc["chosen"], "OpenBao")
            self.assertEqual(enc["rationale"], "already self-hosted")

    def test_missing_decision_refuses_the_whole_write(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            decisions = self._all_applicable(s)
            del decisions["gdpr/consent-capture"]
            with self.assertRaises(ValueError) as cm:
                stack.apply_scope(s, decisions, "prod-1")
            self.assertIn("gdpr/consent-capture", str(cm.exception))

    def test_unknown_decision_key_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            decisions = self._all_applicable(s)
            decisions["gdpr/invented-capability"] = {"applicable": True}
            with self.assertRaises(ValueError) as cm:
                stack.apply_scope(s, decisions, "prod-1")
            self.assertIn("gdpr/invented-capability", str(cm.exception))

    def test_non_applicable_without_reason_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            decisions = self._all_applicable(s)
            decisions["gdpr/consent-capture"] = {"applicable": False, "applicability_reason": "  "}
            with self.assertRaises(ValueError) as cm:
                stack.apply_scope(s, decisions, "prod-1")
            self.assertIn("gdpr/consent-capture", str(cm.exception))

    def test_a_refused_write_leaves_the_input_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scaffolded(catalog)
            decisions = {"gdpr/encryption-at-rest": {"applicable": True}}  # incomplete
            with self.assertRaises(ValueError):
                stack.apply_scope(s, decisions, "prod-1")
            self.assertIsNone(s["choices"]["gdpr/encryption-at-rest"]["scoped_from"])


class TestApplyRanking(unittest.TestCase):
    """The single write path the stack-compiler skill uses for component orderings."""

    def _scoped(self, catalog: Path, consent_applicable: bool = True) -> dict:
        """A scaffolded stack, scoped so `consent-capture` can be ruled out."""
        s = stack.scaffold(_capabilities(), None, catalog_dir=catalog)
        decisions = {k: {"applicable": True, "applicability_reason": ""} for k in s["choices"]}
        if not consent_applicable:
            decisions["gdpr/consent-capture"] = {
                "applicable": False, "applicability_reason": "no consent is ever collected"}
        return stack.apply_scope(s, decisions, "prod-1")

    def _full(self) -> dict:
        return {
            "gdpr/encryption-at-rest": [
                {"component": "age", "rationale": "single binary, matches the deployment"},
                {"component": "OpenBao", "rationale": "needs an operator we do not have"},
            ],
            "gdpr/consent-capture": [
                {"component": "Klaro!", "rationale": "the only option, and self-hostable"},
            ],
        }

    def test_writes_the_ordering_and_the_hash(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            out = stack.apply_ranking(self._scoped(catalog), self._full(), "prod-4c11")
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual([r["component"] for r in enc["ranked"]], ["age", "OpenBao"])
            self.assertEqual(enc["ranked"][0]["rationale"],
                             "single binary, matches the deployment")
            self.assertEqual(enc["ranked_from"], "prod-4c11")

    def test_never_touches_the_selection_or_the_pool(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scoped(catalog)
            s["choices"]["gdpr/encryption-at-rest"].update(
                chosen="OpenBao", rationale="already self-hosted")
            out = stack.apply_ranking(s, self._full(), "prod-1")
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual(enc["chosen"], "OpenBao")
            self.assertEqual(enc["rationale"], "already self-hosted")
            self.assertEqual(enc["options"], ["OpenBao", "age"])
            self.assertTrue(enc["applicable"])
            self.assertEqual(enc["scoped_from"], "prod-1")

    def test_non_applicable_capability_is_left_unranked(self) -> None:
        """Explicitly null, never a missing key — every entry carries every field."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scoped(catalog, consent_applicable=False)
            rankings = {k: v for k, v in self._full().items() if k != "gdpr/consent-capture"}
            out = stack.apply_ranking(s, rankings, "prod-1")
            con = out["choices"]["gdpr/consent-capture"]
            self.assertIn("ranked", con)
            self.assertIn("ranked_from", con)
            self.assertIsNone(con["ranked"])
            self.assertIsNone(con["ranked_from"])

    def test_a_ranking_recorded_before_a_capability_was_scoped_out_survives(self) -> None:
        """Scoping something out records a decision; it must not destroy earlier work."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scoped(catalog, consent_applicable=False)
            s["choices"]["gdpr/consent-capture"].update(
                ranked=[{"component": "Klaro!", "rationale": "ranked while still applicable"}],
                ranked_from="prod-0")
            rankings = {k: v for k, v in self._full().items() if k != "gdpr/consent-capture"}
            out = stack.apply_ranking(s, rankings, "prod-1")
            con = out["choices"]["gdpr/consent-capture"]
            self.assertEqual(con["ranked"][0]["component"], "Klaro!")
            self.assertEqual(con["ranked_from"], "prod-0")

    def test_ranking_a_scoped_out_capability_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scoped(catalog, consent_applicable=False)
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(s, self._full(), "prod-1")
            self.assertIn("non-applicable", str(cm.exception))
            self.assertIn("gdpr/consent-capture", str(cm.exception))

    def test_missing_applicable_capability_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            rankings = {k: v for k, v in self._full().items() if k != "gdpr/consent-capture"}
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(self._scoped(catalog), rankings, "prod-1")
            self.assertIn("no ranking", str(cm.exception))
            self.assertIn("gdpr/consent-capture", str(cm.exception))

    def test_unknown_key_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            rankings = self._full()
            rankings["gdpr/invented-capability"] = [{"component": "X", "rationale": "y"}]
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(self._scoped(catalog), rankings, "prod-1")
            self.assertIn("gdpr/invented-capability", str(cm.exception))

    def test_an_unranked_option_refuses(self) -> None:
        """Dropping a component silently is the omission this gate exists to prevent."""
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            rankings = self._full()
            rankings["gdpr/encryption-at-rest"] = [
                {"component": "age", "rationale": "single binary"}]
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(self._scoped(catalog), rankings, "prod-1")
            self.assertIn("options left unranked", str(cm.exception))
            self.assertIn("OpenBao", str(cm.exception))

    def test_an_invented_component_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            rankings = self._full()
            rankings["gdpr/encryption-at-rest"].append(
                {"component": "SOPS", "rationale": "not in the catalog"})
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(self._scoped(catalog), rankings, "prod-1")
            self.assertIn("not in options", str(cm.exception))
            self.assertIn("SOPS", str(cm.exception))

    def test_a_duplicated_component_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            rankings = self._full()
            rankings["gdpr/encryption-at-rest"] = [
                {"component": "age", "rationale": "first"},
                {"component": "age", "rationale": "again"},
            ]
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(self._scoped(catalog), rankings, "prod-1")
            self.assertIn("ranked twice", str(cm.exception))

    def test_a_blank_rationale_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            rankings = self._full()
            rankings["gdpr/encryption-at-rest"][1]["rationale"] = "   "
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(self._scoped(catalog), rankings, "prod-1")
            self.assertIn("no rationale", str(cm.exception))
            self.assertIn("OpenBao", str(cm.exception))

    def test_an_empty_ranking_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            rankings = self._full()
            rankings["gdpr/encryption-at-rest"] = []
            with self.assertRaises(ValueError) as cm:
                stack.apply_ranking(self._scoped(catalog), rankings, "prod-1")
            self.assertIn("non-empty list", str(cm.exception))

    def test_a_refused_write_leaves_the_input_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scoped(catalog)
            rankings = {"gdpr/encryption-at-rest": self._full()["gdpr/encryption-at-rest"]}
            with self.assertRaises(ValueError):
                stack.apply_ranking(s, rankings, "prod-1")
            self.assertIsNone(s["choices"]["gdpr/encryption-at-rest"]["ranked"])


class TestCapabilityHash(unittest.TestCase):
    """What must reopen a settled choice, and what must not."""

    def _cap(self, **over) -> dict:
        cap = {
            "name": "Encryption at rest",
            "description": "Encrypt stored personal data.",
            "satisfies": ["GDPR-ART5-01"],
            "stack": [{"name": "OpenBao", "license": "MPL-2.0", "role": "in-product",
                       "verdict": "keep", "why": "self-hostable secret store"}],
        }
        cap.update(over)
        return cap

    def test_stable_across_calls(self) -> None:
        self.assertEqual(stack.capability_hash(self._cap()), stack.capability_hash(self._cap()))

    def test_changes_when_a_component_license_changes(self) -> None:
        other = self._cap(stack=[{"name": "OpenBao", "license": "BUSL-1.1",
                                  "role": "in-product", "verdict": "keep", "why": "same prose"}])
        self.assertNotEqual(stack.capability_hash(self._cap()), stack.capability_hash(other))

    def test_ignores_free_prose(self) -> None:
        # A wording fix must not reopen every settled choice.
        reworded = self._cap(stack=[{"name": "OpenBao", "license": "MPL-2.0",
                                     "role": "in-product", "verdict": "keep",
                                     "why": "COMPLETELY REWRITTEN justification"}])
        self.assertEqual(stack.capability_hash(self._cap()), stack.capability_hash(reworded))

    def test_changes_when_the_pool_changes(self) -> None:
        widened = self._cap(stack=[*self._cap()["stack"], {"name": "age", "license": "BSD-3-Clause"}])
        self.assertNotEqual(stack.capability_hash(self._cap()), stack.capability_hash(widened))

    def test_changes_when_the_obligation_changes(self) -> None:
        other = self._cap(satisfies=["GDPR-ART5-01", "GDPR-ART5-02"])
        self.assertNotEqual(stack.capability_hash(self._cap()), stack.capability_hash(other))


class TestApplySelection(unittest.TestCase):
    """The single write path for the component decision itself."""

    def _scoped(self, catalog: Path, consent_applicable: bool = True) -> dict:
        s = stack.scaffold(_capabilities(), None, catalog_dir=catalog)
        decisions = {k: {"applicable": True, "applicability_reason": ""} for k in s["choices"]}
        if not consent_applicable:
            decisions["gdpr/consent-capture"] = {
                "applicable": False, "applicability_reason": "no consent is ever collected"}
        return stack.apply_scope(s, decisions, "prod-1")

    def test_writes_the_choice_the_reason_and_the_catalog_reference(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            cat = _capabilities()
            catalog = _constraints(Path(t))
            out = stack.apply_selection(
                self._scoped(catalog),
                {"gdpr/encryption-at-rest": {"chosen": "age", "rationale": "single binary"}},
                cat,
            )
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual(enc["chosen"], "age")
            self.assertEqual(enc["rationale"], "single binary")
            self.assertEqual(
                enc["chosen_from"],
                stack.capability_hash(cat["frameworks"]["gdpr"]["capabilities"][0]),
            )

    def test_is_partial_and_leaves_undecided_capabilities_alone(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            out = stack.apply_selection(
                self._scoped(catalog),
                {"gdpr/encryption-at-rest": {"chosen": "OpenBao", "rationale": ""}},
                _capabilities(),
            )
            consent = out["choices"]["gdpr/consent-capture"]
            self.assertIsNone(consent["chosen"])       # untouched, still a visible gap
            self.assertIsNone(consent["chosen_from"])  # every entry carries every field

    def test_never_touches_the_pool_the_ranking_or_the_scoping(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            scoped = stack.apply_ranking(
                self._scoped(catalog),
                {"gdpr/encryption-at-rest": [{"component": "age", "rationale": "fits"},
                                             {"component": "OpenBao", "rationale": "heavy"}],
                 "gdpr/consent-capture": [{"component": "Klaro!", "rationale": "only option"}]},
                "prod-9",
            )
            out = stack.apply_selection(
                scoped, {"gdpr/encryption-at-rest": {"chosen": "age"}}, _capabilities())
            enc = out["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual(enc["options"], ["OpenBao", "age"])
            self.assertEqual([r["component"] for r in enc["ranked"]], ["age", "OpenBao"])
            self.assertEqual(enc["ranked_from"], "prod-9")
            self.assertEqual(enc["scoped_from"], "prod-1")
            self.assertTrue(enc["applicable"])

    def test_a_component_outside_the_pool_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            with self.assertRaises(ValueError) as e:
                stack.apply_selection(self._scoped(catalog),
                                      {"gdpr/encryption-at-rest": {"chosen": "HashiCorp Vault"}},
                                      _capabilities())
            self.assertIn("not in options", str(e.exception))

    def test_choosing_for_a_scoped_out_capability_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            with self.assertRaises(ValueError) as e:
                stack.apply_selection(self._scoped(catalog, consent_applicable=False),
                                      {"gdpr/consent-capture": {"chosen": "Klaro!"}},
                                      _capabilities())
            self.assertIn("scoped out", str(e.exception))

    def test_unknown_key_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            with self.assertRaises(ValueError) as e:
                stack.apply_selection(self._scoped(catalog),
                                      {"gdpr/nope": {"chosen": "age"}}, _capabilities())
            self.assertIn("unknown key", str(e.exception))

    def test_blank_choice_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            with self.assertRaises(ValueError) as e:
                stack.apply_selection(self._scoped(catalog),
                                      {"gdpr/encryption-at-rest": {"chosen": "  "}},
                                      _capabilities())
            self.assertIn("names no component", str(e.exception))

    def test_every_problem_is_reported_at_once(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            with self.assertRaises(ValueError) as e:
                stack.apply_selection(
                    self._scoped(catalog),
                    {"gdpr/nope": {"chosen": "age"},
                     "gdpr/encryption-at-rest": {"chosen": "HashiCorp Vault"},
                     "gdpr/consent-capture": {"chosen": ""}},
                    _capabilities(),
                )
            msg = str(e.exception)
            self.assertIn("unknown key", msg)
            self.assertIn("not in options", msg)
            self.assertIn("names no component", msg)

    def test_a_refused_write_leaves_the_input_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            s = self._scoped(catalog)
            with self.assertRaises(ValueError):
                stack.apply_selection(s, {"gdpr/encryption-at-rest": {"chosen": "Vault"}},
                                      _capabilities())
            self.assertIsNone(s["choices"]["gdpr/encryption-at-rest"]["chosen"])


class TestStaleChoices(unittest.TestCase):
    """A catalog change must reopen the choices it invalidated — and only those."""

    def _chosen_both(self, catalog: Path, cat: dict) -> dict:
        s = stack.scaffold(cat, None, catalog_dir=catalog)
        return stack.apply_selection(
            s,
            {"gdpr/encryption-at-rest": {"chosen": "OpenBao"},
             "gdpr/consent-capture": {"chosen": "Klaro!"}},
            cat,
        )

    def test_only_the_changed_capability_goes_stale(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = self._chosen_both(catalog, cat)
            self.assertEqual(stack.gaps(cat, s, catalog_dir=catalog)["stale_choices"], [])

            cat["frameworks"]["gdpr"]["capabilities"][0]["stack"][0]["license"] = "BUSL-1.1"
            res = stack.gaps(cat, s, catalog_dir=catalog)
            self.assertEqual([i["key"] for i in res["stale_choices"]],
                             ["gdpr/encryption-at-rest"])
            self.assertEqual(res["stale_choices"][0]["chosen"], "OpenBao")

    def test_prose_only_catalog_edit_leaves_every_choice_current(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = self._chosen_both(catalog, cat)
            cat["frameworks"]["gdpr"]["capabilities"][0]["stack_notes"] = "reworded"
            self.assertEqual(stack.gaps(cat, s, catalog_dir=catalog)["stale_choices"], [])

    def test_a_choice_with_no_catalog_reference_is_never_stale(self) -> None:
        # Hand-recorded straight into stack.json: nothing to compare against, so silence.
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.scaffold(cat, None, catalog_dir=catalog)
            s["choices"]["gdpr/encryption-at-rest"]["chosen"] = "OpenBao"
            cat["frameworks"]["gdpr"]["capabilities"][0]["description"] = "changed"
            self.assertEqual(stack.gaps(cat, s, catalog_dir=catalog)["stale_choices"], [])


class TestRenderGapReport(unittest.TestCase):
    def test_lists_unchosen_mandatory_capability(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.scaffold(cat, None, catalog_dir=catalog)
            res = stack.gaps(cat, s, catalog_dir=catalog)
            md = stack.render_gap_report(cat, s, res, "2026-02-02")
            self.assertIn("# Stack Gap Report", md)
            self.assertIn("| Framework | Capabilities | Mandatory-linked | Not applicable "
                          "| Chosen | Unchosen |", md)
            self.assertIn("**1 of 1 applicable mandatory-linked capabilities have no chosen "
                          "component.**", md)
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
            self.assertIn("**0 of 1 applicable mandatory-linked capabilities have no chosen "
                          "component.**", md)
            self.assertIn("Nothing to report.", md)

    def test_lists_non_applicable_capability_with_its_reason(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.scaffold(cat, None, catalog_dir=catalog)
            s["choices"]["gdpr/encryption-at-rest"].update(
                applicable=False, applicability_reason="product stores no data at rest")
            res = stack.gaps(cat, s, catalog_dir=catalog)
            md = stack.render_gap_report(cat, s, res, "2026-02-02")
            self.assertIn("**0 of 0 applicable mandatory-linked capabilities have no chosen "
                          "component.**", md)
            self.assertIn("**Not applicable (1)**", md)
            self.assertIn("`gdpr/encryption-at-rest` — product stores no data at rest", md)
            self.assertNotIn("Unexplained omission", md)

    def test_unexplained_omission_is_called_out(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.scaffold(cat, None, catalog_dir=catalog)
            s["choices"]["gdpr/encryption-at-rest"]["applicable"] = False
            res = stack.gaps(cat, s, catalog_dir=catalog)
            md = stack.render_gap_report(cat, s, res, "2026-02-02")
            self.assertIn("Unexplained omission", md)
            self.assertIn("**no reason recorded**", md)

    def test_stale_choice_block_names_the_component_and_both_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            catalog = _constraints(Path(t))
            cat = _capabilities()
            s = stack.apply_selection(
                stack.scaffold(cat, None, catalog_dir=catalog),
                {"gdpr/encryption-at-rest": {"chosen": "OpenBao"}},
                cat,
            )
            cat["frameworks"]["gdpr"]["capabilities"][0]["stack"][0]["role"] = "internal-infra"
            res = stack.gaps(cat, s, catalog_dir=catalog)
            md = stack.render_gap_report(cat, s, res, "2026-02-02")
            self.assertIn("**Stale choices (1)**", md)
            self.assertIn("`gdpr/encryption-at-rest` \u2192 **OpenBao**", md)
            self.assertIn(res["stale_choices"][0]["current"], md)



if __name__ == "__main__":
    unittest.main()
