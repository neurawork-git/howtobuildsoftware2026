"""Unit tests for gate_lib: which documents the gate reads, which components they
name, what the recorded stack says about each, and when an LLM run is earned.

Pure logic — imported straight from ``payload/scripts``, no install, no LLM, no
network. The spawning path itself is deliberately not driven end-to-end here: that
would launch a real agent, which is exactly why the decision lives in
``should_spawn`` and is tested as a function.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gate_lib  # type: ignore[reportMissingImports]  # on sys.path only at runtime

REPO = Path(__file__).resolve().parents[5]  # the self-host repo, when there is one
CFG = {"prds_subpath": ".claude/PRPs/prds", "plans_subpath": ".claude/PRPs/plans",
       "stack_dir": "stack-base", "compliance_dir": "compliance-base"}


def _capabilities() -> dict:
    """A catalog small enough to reason about and wide enough to hit every status."""
    return {
        "license_policy": {"embeddable": ["MIT", "MPL-2.0"],
                           "not_in_product": ["AGPL-3.0"]},
        "frameworks": {
            "gdpr": {"capabilities": [
                {"name": "Encryption at rest", "category": "Data Protection", "stack": [
                    {"name": "OpenBao", "license": "MPL-2.0", "role": "in-product",
                     "verdict": "keep", "why": "self-hostable secret store"},
                    {"name": "age", "license": "MIT", "role": "in-product",
                     "verdict": "keep", "why": "single-binary file encryption"},
                ]},
                {"name": "Consent capture", "category": "Governance", "stack": [
                    {"name": "Klaro!", "license": "MIT", "role": "in-product",
                     "verdict": "keep", "why": "consent banner"},
                ]},
                {"name": "Disclosure ledger", "category": "Governance", "stack": [
                    {"name": "PostgreSQL (append-only disclosure ledger via temporal_tables)",
                     "license": "PostgreSQL", "role": "in-product", "verdict": "keep",
                     "why": "system-versioned tables"},
                ]},
            ]},
            "soc2": {"capabilities": [
                {"name": "Log aggregation", "category": "Monitoring", "stack": [
                    {"name": "Grafana Loki", "license": "AGPL-3.0", "role": "internal-infra",
                     "verdict": "keep", "why": "operator-side only"},
                    {"name": "Klaro!", "license": "MIT", "role": "in-product",
                     "verdict": "keep", "why": "listed twice on purpose"},
                ]},
                {"name": "Case management", "category": "Incident", "stack": [
                    {"name": "TheHive (Community)", "license": "AGPL-3.0",
                     "role": "in-product", "verdict": "keep", "why": "shipped"},
                    {"name": "Zammad", "license": "AGPL-3.0", "role": "in-product",
                     "verdict": "keep-exception", "why": "recorded deviation"},
                    {"name": "Orphan Tool", "license": "MIT", "role": "in-product",
                     "verdict": "keep", "why": "in the catalog, in no options list"},
                ]},
            ]},
        },
    }


def _stack() -> dict:
    """A stack that has been scoped and partly chosen — every status reachable."""
    return {"choices": {
        "gdpr/encryption-at-rest": {
            "capability": "Encryption at rest", "framework": "gdpr",
            "options": ["OpenBao", "age"], "chosen": "age", "applicable": True,
            "applicability_reason": "", "scoped_from": "prod-1",
        },
        "gdpr/consent-capture": {
            "capability": "Consent capture", "framework": "gdpr",
            "options": ["Klaro!"], "chosen": None, "applicable": False,
            "applicability_reason": "no consent is ever collected", "scoped_from": "prod-1",
        },
        "gdpr/disclosure-ledger": {
            "capability": "Disclosure ledger", "framework": "gdpr",
            "options": ["PostgreSQL (append-only disclosure ledger via temporal_tables)"],
            "chosen": None, "applicable": True, "applicability_reason": "",
            "scoped_from": "prod-1",
        },
        "soc2/log-aggregation": {
            "capability": "Log aggregation", "framework": "soc2",
            "options": ["Grafana Loki", "Klaro!"], "chosen": "Grafana Loki",
            "applicable": True, "applicability_reason": "", "scoped_from": "prod-1",
        },
        "soc2/case-management": {
            "capability": "Case management", "framework": "soc2",
            "options": ["TheHive (Community)", "Zammad"], "chosen": "Zammad",
            "applicable": True, "applicability_reason": "", "scoped_from": "prod-1",
        },
    }}


def _classify(names: list[str]) -> dict:
    return gate_lib.classify(names, _stack(), _capabilities())


def _status(names: list[str], component: str) -> str:
    for item in _classify(names)["mentions"]:
        if item["component"] == component:
            return item["status"]
    raise AssertionError(f"{component} not classified")


class TestDocumentKind(unittest.TestCase):
    """Only live PRDs and plans inside the configured subpaths are read."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def _kind(self, rel: str) -> str:
        return gate_lib.document_kind(str(self.root / rel), self.root, CFG)

    def test_live_prd_and_plan(self) -> None:
        self.assertEqual(self._kind(".claude/PRPs/prds/product.prd.md"), "prd")
        self.assertEqual(self._kind(".claude/PRPs/plans/feature.plan.md"), "plan")
        self.assertEqual(self._kind(".claude/PRPs/plans/nested/feature.plan.md"), "plan")

    def test_archived_documents_are_records_not_pending_work(self) -> None:
        self.assertEqual(self._kind(".claude/PRPs/prds/completed/old.prd.md"), "")
        self.assertEqual(self._kind(".claude/PRPs/plans/completed/old.plan.md"), "")

    def test_other_markdown_and_other_locations(self) -> None:
        self.assertEqual(self._kind(".claude/PRPs/prds/notes.md"), "")
        self.assertEqual(self._kind("docs/product.prd.md"), "")
        self.assertEqual(self._kind(".claude/PRPs/reports/x.plan.md"), "")

    def test_a_path_outside_the_repo_never_matches(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / ".claude" / "PRPs" / "prds" / "x.prd.md"
            self.assertEqual(gate_lib.document_kind(str(outside), self.root, CFG), "")

    def test_a_relative_path_resolves_against_the_working_directory(self) -> None:
        (self.root / ".claude/PRPs/prds").mkdir(parents=True)
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            self.assertEqual(
                gate_lib.document_kind(".claude/PRPs/prds/product.prd.md", self.root, CFG),
                "prd")
        finally:
            os.chdir(cwd)

    def test_empty_path_and_configured_subpaths(self) -> None:
        self.assertEqual(gate_lib.document_kind("", self.root, CFG), "")
        cfg = {**CFG, "prds_subpath": "docs/prds"}
        self.assertEqual(
            gate_lib.document_kind(str(self.root / "docs/prds/x.prd.md"), self.root, cfg), "prd")


class TestGateMode(unittest.TestCase):
    """A hand-edited config must not be able to crash a tool call."""

    def setUp(self) -> None:
        import config  # type: ignore[reportMissingImports]  # on sys.path only at runtime
        self.gate_mode = config.gate_mode

    def test_absent_string_and_garbage_all_degrade_to_warn(self) -> None:
        self.assertEqual(self.gate_mode({}, "prd"), "warn")
        self.assertEqual(self.gate_mode({"validate_mode": "warn"}, "plan"), "warn")
        self.assertEqual(self.gate_mode({"validate_mode": 17}, "plan"), "warn")
        self.assertEqual(self.gate_mode({"validate_mode": {"plan": "shout"}}, "plan"), "warn")
        self.assertEqual(self.gate_mode({"validate_mode": {"prd": "block"}}, "plan"), "warn")

    def test_block_is_read_per_kind(self) -> None:
        cfg = {"validate_mode": {"prd": "warn", "plan": "block"}}
        self.assertEqual(self.gate_mode(cfg, "plan"), "block")
        self.assertEqual(self.gate_mode(cfg, "prd"), "warn")
        self.assertEqual(self.gate_mode({"validate_mode": "block"}, "prd"), "block")


class TestMentions(unittest.TestCase):
    """The closed pool, found case-sensitively and whole-word."""

    def setUp(self) -> None:
        self.index = gate_lib.component_index(_capabilities())

    def _mentions(self, text: str) -> list[str]:
        return gate_lib.mentions(text, self.index)

    def test_exact_head_and_alias_resolve_to_the_same_component(self) -> None:
        canonical = "PostgreSQL (append-only disclosure ledger via temporal_tables)"
        self.assertEqual(self._mentions("We store it in PostgreSQL."), [canonical])
        self.assertEqual(self._mentions("We store it in Postgres."), [canonical])
        self.assertEqual(self._mentions(f"the catalog says {canonical}"), [canonical])

    def test_lowercase_prose_is_not_a_mention(self) -> None:
        self.assertEqual(self._mentions("some postgresql database"), [])
        self.assertEqual(self._mentions("the whole fleet of hosts"), [])

    def test_a_name_inside_a_longer_word_is_not_a_mention(self) -> None:
        self.assertEqual(self._mentions("OpenBaoX"), [])
        self.assertEqual(self._mentions("run the age-encrypt step"), [])
        self.assertEqual(self._mentions("the storage-OpenBao-bridge"), [])

    def test_a_real_mention_survives_punctuation(self) -> None:
        self.assertEqual(self._mentions("Use OpenBao, then age."), ["OpenBao", "age"])

    def test_short_variants_never_enter_the_index(self) -> None:
        for variant in self.index:
            self.assertGreaterEqual(len(variant), gate_lib.MIN_VARIANT_LEN)

    @unittest.skipUnless((REPO / "CLAUDE.md").exists(), "no self-host repo in this checkout")
    def test_the_repos_own_prose_yields_zero_mentions(self) -> None:
        """The measured false-positive floor, against the live catalog — not a fixture."""
        import json
        catalog = REPO / "compliance-base" / "catalog" / "capabilities.json"
        if not catalog.exists():
            self.skipTest("no built capability catalog in this checkout")
        index = gate_lib.component_index(json.loads(catalog.read_text(encoding="utf-8")))
        for rel in ("CLAUDE.md", "docs/ARCHITECTURE.md"):
            path = REPO / rel
            if not path.exists():
                continue
            self.assertEqual(gate_lib.mentions(path.read_text(encoding="utf-8"), index), [],
                             f"{rel} produced a false-positive component mention")


class TestClassify(unittest.TestCase):
    """Every mention gets exactly one status, plus a license verdict."""

    def test_the_five_statuses(self) -> None:
        self.assertEqual(_status(["age"], "age"), "on_stack")
        self.assertEqual(_status(["OpenBao"], "OpenBao"), "off_stack")
        self.assertEqual(
            _status(["PostgreSQL (append-only disclosure ledger via temporal_tables)"],
                    "PostgreSQL (append-only disclosure ledger via temporal_tables)"),
            "undecided")
        self.assertEqual(_status(["Orphan Tool"], "Orphan Tool"), "orphaned")

    def test_an_option_of_two_capabilities_follows_the_applicable_one(self) -> None:
        """Klaro! is an option of a scoped-out capability AND of an applicable one."""
        self.assertEqual(_status(["Klaro!"], "Klaro!"), "off_stack")

    def test_scoped_out_carries_the_recorded_reason(self) -> None:
        stack = _stack()
        del stack["choices"]["soc2/log-aggregation"]  # leave Klaro! only where it is ruled out
        item = gate_lib.classify(["Klaro!"], stack, _capabilities())["mentions"][0]
        self.assertEqual(item["status"], "scoped_out")
        self.assertEqual(item["reasons"], ["no consent is ever collected"])

    def test_off_stack_names_the_capability_and_the_recorded_choice(self) -> None:
        item = _classify(["OpenBao"])["mentions"][0]
        self.assertEqual(item["conflicts"],
                         [{"key": "gdpr/encryption-at-rest", "chosen": "age"}])

    def test_license_verdicts_follow_the_catalogs_own_policy(self) -> None:
        result = _classify(["TheHive (Community)", "Grafana Loki", "Zammad", "age"])
        by_name = {i["component"]: i for i in result["mentions"]}
        self.assertEqual(by_name["TheHive (Community)"]["license_verdict"], "violation")
        self.assertEqual(by_name["Grafana Loki"]["license_verdict"], "ok")
        self.assertEqual(by_name["Zammad"]["license_verdict"], "exception")
        self.assertEqual(by_name["age"]["license_verdict"], "ok")
        self.assertEqual([i["component"] for i in result["violations"]],
                         ["TheHive (Community)"])
        self.assertEqual([i["component"] for i in result["exceptions"]], ["Zammad"])

    def test_the_counts_let_the_caller_degrade_instead_of_guessing(self) -> None:
        result = _classify([])
        self.assertTrue(result["catalog_built"])
        self.assertTrue(result["scoped"])
        self.assertEqual(result["applicable_total"], 4)
        self.assertEqual(result["chosen_total"], 3)

    def test_no_mentions_empty_stack_and_empty_catalog_never_raise(self) -> None:
        self.assertEqual(_classify([])["mentions"], [])
        self.assertEqual(gate_lib.classify(["age"], {}, _capabilities())["mentions"][0]["status"],
                         "orphaned")
        # Status comes from stack.json alone; the catalog only carries the license.
        empty = gate_lib.classify(["age"], _stack(), {})
        self.assertFalse(empty["catalog_built"])
        self.assertEqual(empty["mentions"][0]["status"], "on_stack")
        self.assertEqual(empty["mentions"][0]["license_verdict"], "ok")


class TestRenderSummary(unittest.TestCase):
    """One advisory paragraph, and it always names the next command."""

    def test_unbuilt_catalog_and_unscoped_stack_name_their_commands(self) -> None:
        self.assertIn("co-capabilities",
                      gate_lib.render_summary(gate_lib.classify([], _stack(), {}), "prd", CFG))
        unscoped = {"choices": {"gdpr/x": {"options": ["age"], "applicable": True}}}
        text = gate_lib.render_summary(
            gate_lib.classify([], unscoped, _capabilities()), "plan", CFG)
        self.assertIn("scope.py", text)

    def test_nothing_chosen_points_at_the_selection_pass(self) -> None:
        stack = _stack()
        for entry in stack["choices"].values():
            entry["chosen"] = None
        text = gate_lib.render_summary(
            gate_lib.classify(["OpenBao"], stack, _capabilities()), "prd", CFG)
        self.assertIn("selection.py", text)

    def test_off_stack_leads_and_names_the_recorded_choice(self) -> None:
        text = gate_lib.render_summary(_classify(["OpenBao"]), "plan", CFG)
        self.assertIn("OpenBao", text)
        self.assertIn("gdpr/encryption-at-rest", text)
        self.assertIn("age", text)

    def test_a_clean_document_says_so_in_one_line(self) -> None:
        text = gate_lib.render_summary(_classify(["age"]), "plan", CFG)
        self.assertIn("1 catalog component(s) named", text)
        self.assertEqual(text.count("\n"), 0)

    def test_zero_mentions_is_its_own_sentence(self) -> None:
        self.assertIn("names no catalog component",
                      gate_lib.render_summary(_classify([]), "prd", CFG))


class TestDebounce(unittest.TestCase):
    """One LLM run per document per meaningful change."""

    def setUp(self) -> None:
        self.result = _classify(["OpenBao"])

    def test_an_unchanged_hash_spawns_nothing(self) -> None:
        state = gate_lib.record_spawn({}, "/repo/x.prd.md", "abc", "2026-01-01T00:00:00+01:00")
        self.assertFalse(gate_lib.should_spawn(state, "/repo/x.prd.md", "abc", self.result))
        self.assertTrue(gate_lib.should_spawn(state, "/repo/x.prd.md", "def", self.result))
        self.assertTrue(gate_lib.should_spawn(state, "/repo/y.prd.md", "abc", self.result))

    def test_nothing_to_enforce_spawns_nothing_even_on_a_changed_hash(self) -> None:
        stack = _stack()
        for entry in stack["choices"].values():
            entry["chosen"] = None
        nothing_chosen = gate_lib.classify(["OpenBao"], stack, _capabilities())
        self.assertFalse(gate_lib.should_spawn({}, "/repo/x.prd.md", "abc", nothing_chosen))
        unbuilt = gate_lib.classify(["OpenBao"], _stack(), {})
        self.assertFalse(gate_lib.should_spawn({}, "/repo/x.prd.md", "abc", unbuilt))

    def test_the_ledger_round_trips_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "reports" / ".state.json"
            state = gate_lib.record_spawn({}, "/repo/x.prd.md", "abc", "2026-01-01T00:00:00+01:00")
            gate_lib.save_state(path, state)
            self.assertEqual(gate_lib.load_state(path), state)
            done = gate_lib.record_outcome(gate_lib.load_state(path), "/repo/x.prd.md",
                                           "/repo/reports/x.prd.md", True,
                                           "2026-01-01T00:01:00+01:00")
            gate_lib.save_state(path, done)
            entry = gate_lib.load_state(path)["documents"]["/repo/x.prd.md"]
            self.assertEqual(entry["hash"], "abc")
            self.assertTrue(entry["ok"])
            self.assertEqual(entry["report"], "/repo/reports/x.prd.md")

    def test_a_missing_or_corrupt_ledger_reads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / ".state.json"
            self.assertEqual(gate_lib.load_state(path), {})
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(gate_lib.load_state(path), {})


class TestVerdict(unittest.TestCase):
    """The agent proposes; this decides — and invented names decide nothing."""

    def _verdict(self, raw: dict) -> dict:
        return gate_lib.verdict(raw, _stack(), _capabilities())

    def test_a_proposed_off_stack_component_fails(self) -> None:
        v = self._verdict({"proposed": ["OpenBao"]})
        self.assertFalse(v["ok"])
        self.assertEqual([i["component"] for i in v["off_stack"]], ["OpenBao"])

    def test_a_mentioned_but_unproposed_component_passes(self) -> None:
        self.assertTrue(self._verdict({"proposed": []})["ok"])
        self.assertTrue(self._verdict({"proposed": ["age"]})["ok"])

    def test_a_license_violation_fails_even_when_it_is_on_no_capability(self) -> None:
        v = self._verdict({"proposed": ["TheHive (Community)"]})
        self.assertFalse(v["ok"])
        self.assertEqual([i["component"] for i in v["violations"]], ["TheHive (Community)"])

    def test_a_recorded_exception_is_not_a_failure(self) -> None:
        self.assertTrue(self._verdict({"proposed": ["Zammad"]})["ok"])

    def test_an_invented_component_is_filtered_before_the_math(self) -> None:
        v = self._verdict({"proposed": ["Vaultwarden", "age"]})
        self.assertEqual(v["proposed"], ["age"])
        self.assertTrue(v["ok"])

    def test_an_invented_capability_key_is_filtered_out(self) -> None:
        v = self._verdict({"proposed": [],
                           "ignored_capabilities": ["gdpr/consent-capture",
                                                    "soc2/case-management",
                                                    "gdpr/invented"]})
        self.assertEqual(v["ignored_capabilities"], ["soc2/case-management"])

    def test_an_ignored_capability_is_reported_never_fatal(self) -> None:
        v = self._verdict({"proposed": [], "ignored_capabilities": ["soc2/case-management"]})
        self.assertTrue(v["ok"])


if __name__ == "__main__":
    unittest.main()
