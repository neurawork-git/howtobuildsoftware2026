"""Prompt/parse/preflight tests for rank.py. No LLM, no network.

``rank.py`` imports ``claude_agent_sdk`` inside ``_run_agent`` only, so the module
imports cleanly here without an SDK or an API key.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import rank


def _caps() -> list[dict]:
    """One framework's applicable capabilities, as rankable_universe returns them."""
    return [
        {
            "key": "gdpr/encryption-at-rest",
            "framework": "gdpr",
            "capability": "Encryption at rest",
            "mandatory_linked": True,
            "category": "Data Protection",
            "description": "Encrypt stored personal data.",
            "options": ["OpenBao", "age"],
            "components": [
                {"name": "OpenBao", "license": "MPL-2.0", "role": "in-product",
                 "verdict": "keep", "why": "self-hostable secret store"},
                {"name": "age", "license": "BSD-3-Clause", "role": "in-product",
                 "verdict": "replaced", "why": "single-binary file encryption"},
            ],
        },
    ]


class TestBuildRankPrompt(unittest.TestCase):
    def test_carries_the_product_keys_components_and_shard_path(self) -> None:
        out = rank.build_rank_prompt("gdpr", _caps(), "We store user emails.",
                                     Path("/tmp/.shards/rank-gdpr.json"))
        self.assertIn("We store user emails.", out)
        self.assertIn("gdpr/encryption-at-rest", out)
        self.assertIn("OpenBao", out)
        self.assertIn("MPL-2.0", out)
        self.assertIn("in-product", out)
        self.assertIn("single-binary file encryption", out)
        self.assertIn("/tmp/.shards/rank-gdpr.json", out)

    def test_states_the_closed_pool_requirement(self) -> None:
        out = rank.build_rank_prompt("gdpr", _caps(), "p", Path("/tmp/s.json"))
        self.assertIn("Never add a component, never leave one out", out)
        self.assertIn("rank ALL of them", out)

    def test_embeds_the_constitution_verbatim(self) -> None:
        """AGENTS.md *is* the spec — it must reach the agent, not just describe it."""
        original = rank._constitution
        rank._constitution = lambda: "CONSTITUTION-MARKER-7f3a"
        try:
            out = rank.build_rank_prompt("gdpr", _caps(), "p", Path("/tmp/s.json"))
        finally:
            rank._constitution = original
        self.assertIn("CONSTITUTION-MARKER-7f3a", out)

    def test_states_the_rationale_and_license_rules(self) -> None:
        out = rank.build_rank_prompt("gdpr", _caps(), "p", Path("/tmp/s.json"))
        self.assertIn('non-empty "rationale"', out)
        self.assertIn("rank it last and say so", out)
        self.assertIn("SUPERSEDED", out)


class TestParseRankShard(unittest.TestCase):
    KEYS = {"gdpr/encryption-at-rest"}

    def _shard(self) -> list[dict]:
        return [{"key": "gdpr/encryption-at-rest", "ranked": [
            {"component": " age ", "rationale": " single binary "},
            {"component": "OpenBao", "rationale": "needs an operator"},
        ]}]

    def test_parses_and_strips(self) -> None:
        out = rank.parse_rank_shard(self._shard(), self.KEYS, "gdpr")
        self.assertEqual(out["gdpr/encryption-at-rest"][0],
                         {"component": "age", "rationale": "single binary"})

    def test_rejects_a_non_array(self) -> None:
        with self.assertRaises(TypeError):
            rank.parse_rank_shard({"key": "x"}, self.KEYS, "gdpr")

    def test_rejects_a_dropped_key(self) -> None:
        with self.assertRaises(RuntimeError) as cm:
            rank.parse_rank_shard([], self.KEYS, "gdpr")
        self.assertIn("no ranking", str(cm.exception))

    def test_rejects_an_invented_key(self) -> None:
        shard = self._shard()
        shard.append({"key": "gdpr/invented", "ranked": [{"component": "X", "rationale": "y"}]})
        with self.assertRaises(RuntimeError) as cm:
            rank.parse_rank_shard(shard, self.KEYS, "gdpr")
        self.assertIn("unknown key", str(cm.exception))

    def test_rejects_a_duplicate_ranking(self) -> None:
        shard = self._shard() * 2
        with self.assertRaises(RuntimeError) as cm:
            rank.parse_rank_shard(shard, self.KEYS, "gdpr")
        self.assertIn("duplicate", str(cm.exception))

    def test_rejects_an_empty_ranked_list(self) -> None:
        with self.assertRaises(RuntimeError) as cm:
            rank.parse_rank_shard([{"key": "gdpr/encryption-at-rest", "ranked": []}],
                                  self.KEYS, "gdpr")
        self.assertIn("no ranked components", str(cm.exception))

    def test_rejects_an_entry_naming_no_component(self) -> None:
        shard = [{"key": "gdpr/encryption-at-rest",
                  "ranked": [{"component": "  ", "rationale": "r"}]}]
        with self.assertRaises(RuntimeError) as cm:
            rank.parse_rank_shard(shard, self.KEYS, "gdpr")
        self.assertIn("naming no component", str(cm.exception))

    def test_keeps_a_blank_rationale_for_the_gate_to_report(self) -> None:
        """Parsing validates shape; the missing reason is the gate's finding to name."""
        shard = [{"key": "gdpr/encryption-at-rest",
                  "ranked": [{"component": "age", "rationale": ""}]}]
        out = rank.parse_rank_shard(shard, self.KEYS, "gdpr")
        self.assertEqual(out["gdpr/encryption-at-rest"][0]["rationale"], "")


class TestIsScoped(unittest.TestCase):
    def test_false_until_a_scoping_pass_has_run(self) -> None:
        self.assertFalse(rank.is_scoped({"choices": {"a": {"scoped_from": None}}}))
        self.assertFalse(rank.is_scoped({"choices": {}}))

    def test_true_once_any_entry_carries_a_scope_hash(self) -> None:
        self.assertTrue(rank.is_scoped({"choices": {"a": {"scoped_from": "h1"}}}))


class TestAlreadyRanked(unittest.TestCase):
    def _stack(self, **enc) -> dict:
        base = {"applicable": True, "ranked": [{"component": "age", "rationale": "r"}],
                "ranked_from": "h1"}
        return {"choices": {"gdpr/encryption-at-rest": {**base, **enc}}}

    def test_true_when_every_applicable_entry_carries_the_hash(self) -> None:
        self.assertTrue(rank.already_ranked(self._stack(), "h1"))

    def test_false_on_a_different_product_hash(self) -> None:
        self.assertFalse(rank.already_ranked(self._stack(), "h2"))

    def test_false_when_an_applicable_entry_is_unranked(self) -> None:
        self.assertFalse(rank.already_ranked(self._stack(ranked=None), "h1"))

    def test_a_scoped_out_entry_without_a_ranking_does_not_block(self) -> None:
        stack = self._stack()
        stack["choices"]["gdpr/consent-capture"] = {
            "applicable": False, "ranked": None, "ranked_from": None}
        self.assertTrue(rank.already_ranked(stack, "h1"))

    def test_empty_stack_is_never_already_ranked(self) -> None:
        self.assertFalse(rank.already_ranked({"choices": {}}, "h1"))


class TestPreflight(unittest.TestCase):
    """A missing dependency must fail loudly and cheaply, writing nothing."""

    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, STACK_ROOT=str(root))
        return subprocess.run([sys.executable, str(SCRIPTS / "rank.py"), *args],
                              capture_output=True, text=True, env=env,
                              timeout=60, check=False)

    def _stack_dir(self, tmp: Path) -> Path:
        root = tmp / "stack-base"
        (root / "scripts").mkdir(parents=True)
        return root

    def _compliance(self, tmp: Path, stack_json: dict) -> None:
        comp = tmp / "compliance-base"
        (comp / "catalog").mkdir(parents=True)
        (comp / "scripts").mkdir(parents=True)
        (comp / "scripts" / "stack.py").write_text("", encoding="utf-8")
        (comp / "catalog" / "capabilities.json").write_text("{}", encoding="utf-8")
        (comp / "catalog" / "stack.json").write_text(json.dumps(stack_json), encoding="utf-8")

    def test_missing_compliance_install(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            res = self._run(self._stack_dir(Path(t)), "--dry-run")
            self.assertEqual(res.returncode, 1)
            self.assertIn("No compliance install", res.stdout)

    def test_missing_stack_json_names_the_scaffold_command(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            catalog = tmp / "compliance-base" / "catalog"
            catalog.mkdir(parents=True)
            (catalog / "capabilities.json").write_text("{}", encoding="utf-8")
            res = self._run(root, "--dry-run")
            self.assertEqual(res.returncode, 1)
            self.assertIn("--scaffold", res.stdout)

    def test_absent_product_points_at_the_scope_pass(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            self._compliance(tmp, {"choices": {}})
            res = self._run(root, "--dry-run")
            self.assertEqual(res.returncode, 1)
            self.assertIn("scope.py", res.stdout)
            self.assertFalse((root / "product.md").exists())  # scope.py owns the template

    def test_empty_product_stops(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            (root / "product.md").write_text("   \n", encoding="utf-8")
            self._compliance(tmp, {"choices": {}})
            res = self._run(root, "--dry-run")
            self.assertEqual(res.returncode, 1)
            self.assertIn("is empty", res.stdout)

    def test_an_unscoped_stack_stops_before_any_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            (root / "product.md").write_text("# Product\n\nStores emails.\n", encoding="utf-8")
            self._compliance(tmp, {"choices": {"gdpr/x": {
                "capability": "X", "framework": "gdpr", "options": ["A"],
                "applicable": True, "scoped_from": None}}})
            res = self._run(root, "--dry-run")
            self.assertEqual(res.returncode, 1)
            self.assertIn("no scoping decisions", res.stdout)

    def test_dry_run_reports_the_plan_without_an_llm(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            (root / "product.md").write_text("# Product\n\nStores emails.\n", encoding="utf-8")
            self._compliance(tmp, {"choices": {
                "gdpr/x": {"capability": "X", "framework": "gdpr", "options": ["A", "B"],
                           "applicable": True, "scoped_from": "h1"},
                "gdpr/y": {"capability": "Y", "framework": "gdpr", "options": ["C"],
                           "applicable": False, "scoped_from": "h1"},
            }})
            res = self._run(root, "--dry-run")
            self.assertEqual(res.returncode, 0)
            self.assertIn("[DRY RUN]", res.stdout)
            self.assertIn("2 components", res.stdout)      # only the applicable capability's
            self.assertIn("1 applicable capabilities", res.stdout)

    def test_a_fully_scoped_out_product_has_nothing_to_rank(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            (root / "product.md").write_text("# Product\n\nNothing.\n", encoding="utf-8")
            self._compliance(tmp, {"choices": {"gdpr/x": {
                "capability": "X", "framework": "gdpr", "options": ["A"],
                "applicable": False, "scoped_from": "h1"}}})
            res = self._run(root, "--dry-run")
            self.assertEqual(res.returncode, 0)
            self.assertIn("nothing to rank", res.stdout)


if __name__ == "__main__":
    unittest.main()
