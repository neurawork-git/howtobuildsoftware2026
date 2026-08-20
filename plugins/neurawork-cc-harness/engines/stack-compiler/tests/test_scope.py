"""Prompt-builder, shard-parsing and preflight tests for scope.py.

No SDK, no LLM, no network: ``claude_agent_sdk`` is imported inside the agent
functions, so the module imports and the pure parts run without it installed.
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

import scope  # noqa: E402

CAPS = [
    {"key": "gdpr/encryption-at-rest", "framework": "gdpr", "capability": "Encryption at rest",
     "category": "Data Protection", "description": "Encrypt stored personal data.",
     "mandatory_linked": True, "satisfies": ["GDPR-ART32-01"]},
    {"key": "gdpr/consent-capture", "framework": "gdpr", "capability": "Consent capture",
     "category": "Governance & Privacy Ops", "description": "Record consent.",
     "mandatory_linked": False, "satisfies": ["GDPR-ART7-01"]},
]


class TestBuildScopePrompt(unittest.TestCase):
    def test_carries_product_every_key_and_the_shard_path(self) -> None:
        p = scope.build_scope_prompt("gdpr", CAPS, "we store user emails",
                                     Path("/tmp/scope-gdpr.json"))
        self.assertIn("we store user emails", p)
        for c in CAPS:
            self.assertIn(c["key"], p)
            self.assertIn(c["description"], p)
        self.assertIn("/tmp/scope-gdpr.json", p)
        self.assertIn("mandatory_linked: true", p)
        self.assertIn("Decide on all 2 keys", p)

    def test_states_the_reason_requirement(self) -> None:
        p = scope.build_scope_prompt("gdpr", CAPS, "x", Path("/tmp/s.json"))
        self.assertIn('"applicable": false REQUIRES a non-empty "reason"', p)
        self.assertIn('When in doubt, "applicable": true', p)


class TestBuildChallengePrompt(unittest.TestCase):
    def test_carries_claims_and_demands_a_quote(self) -> None:
        items = [{"key": "gdpr/consent-capture", "capability": "Consent capture",
                  "description": "Record consent.", "reason": "no personal data is processed"}]
        p = scope.build_challenge_prompt("we store the user's email", items,
                                         Path("/tmp/challenge.json"))
        self.assertIn("no personal data is processed", p)
        self.assertIn("we store the user's email", p)
        self.assertIn("quoted verbatim", p)
        self.assertIn("Claims to challenge (1)", p)


SCOPE_KEYS = {c["key"] for c in CAPS}
CHALLENGED = {"gdpr/consent-capture"}


class TestParseScopeShard(unittest.TestCase):
    def _shard(self, **overrides) -> list[dict]:
        out = [{"key": c["key"], "applicable": True, "reason": ""} for c in CAPS]
        for item in out:
            item.update(overrides.get(item["key"], {}))
        return out

    def test_parses_and_strips(self) -> None:
        raw = self._shard(**{"gdpr/consent-capture": {"applicable": False,
                                                      "reason": "  no consent  "}})
        got = scope.parse_scope_shard(raw, SCOPE_KEYS, "gdpr")
        self.assertEqual(got["gdpr/consent-capture"],
                         {"applicable": False, "reason": "no consent"})
        self.assertTrue(got["gdpr/encryption-at-rest"]["applicable"])

    def test_rejects_a_non_array(self) -> None:
        with self.assertRaises(RuntimeError):
            scope.parse_scope_shard({"key": "x"}, SCOPE_KEYS, "gdpr")

    def test_rejects_a_dropped_key(self) -> None:
        with self.assertRaises(RuntimeError) as cm:
            scope.parse_scope_shard(self._shard()[:1], SCOPE_KEYS, "gdpr")
        self.assertIn("gdpr/consent-capture", str(cm.exception))

    def test_rejects_an_invented_key(self) -> None:
        raw = self._shard() + [{"key": "gdpr/invented", "applicable": True, "reason": ""}]
        with self.assertRaises(RuntimeError) as cm:
            scope.parse_scope_shard(raw, SCOPE_KEYS, "gdpr")
        self.assertIn("gdpr/invented", str(cm.exception))

    def test_rejects_a_duplicate_decision(self) -> None:
        raw = self._shard() + [{"key": "gdpr/consent-capture", "applicable": False,
                                "reason": "second opinion"}]
        with self.assertRaises(RuntimeError) as cm:
            scope.parse_scope_shard(raw, SCOPE_KEYS, "gdpr")
        self.assertIn("duplicate", str(cm.exception))


class TestParseChallengeShard(unittest.TestCase):
    def test_keeps_only_evidenced_refutations(self) -> None:
        raw = [{"key": "gdpr/consent-capture", "refuted": True,
                "evidence": "we store the user's email"}]
        self.assertEqual(scope.parse_challenge_shard(raw, CHALLENGED),
                         [{"key": "gdpr/consent-capture",
                           "evidence": "we store the user's email"}])

    def test_unevidenced_refutation_is_discarded(self) -> None:
        raw = [{"key": "gdpr/consent-capture", "refuted": True, "evidence": "   "}]
        self.assertEqual(scope.parse_challenge_shard(raw, CHALLENGED), [])

    def test_not_refuted_is_not_returned(self) -> None:
        raw = [{"key": "gdpr/consent-capture", "refuted": False, "evidence": "n/a"}]
        self.assertEqual(scope.parse_challenge_shard(raw, CHALLENGED), [])

    def test_rejects_a_verdict_on_an_unchallenged_key(self) -> None:
        raw = [{"key": "gdpr/encryption-at-rest", "refuted": True, "evidence": "q"}]
        with self.assertRaises(RuntimeError):
            scope.parse_challenge_shard(raw, CHALLENGED)


class TestAlreadyScoped(unittest.TestCase):
    def test_true_only_when_every_entry_carries_the_hash(self) -> None:
        s: dict = {"choices": {"a": {"scoped_from": "h1"}, "b": {"scoped_from": "h1"}}}
        self.assertTrue(scope.already_scoped(s, "h1"))
        self.assertFalse(scope.already_scoped(s, "h2"))
        s["choices"]["b"] = {"scoped_from": None}    # never scoped
        self.assertFalse(scope.already_scoped(s, "h1"))

    def test_empty_stack_is_never_already_scoped(self) -> None:
        self.assertFalse(scope.already_scoped({"choices": {}}, "h1"))


class TestPreflight(unittest.TestCase):
    """A missing dependency must fail loudly and cheaply, writing nothing."""

    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, STACK_ROOT=str(root))
        return subprocess.run([sys.executable, str(SCRIPTS / "scope.py"), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def _stack_dir(self, tmp: Path) -> Path:
        root = tmp / "stack-base"
        (root / "scripts").mkdir(parents=True)
        return root

    def test_missing_compliance_install(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = self._stack_dir(Path(t))
            res = self._run(root, "--dry-run")
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

    def test_absent_product_scaffolds_a_template_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            comp = tmp / "compliance-base"
            (comp / "catalog").mkdir(parents=True)
            (comp / "scripts").mkdir(parents=True)
            (comp / "scripts" / "stack.py").write_text("", encoding="utf-8")
            (comp / "catalog" / "capabilities.json").write_text("{}", encoding="utf-8")
            (comp / "catalog" / "stack.json").write_text(
                json.dumps({"choices": {}}), encoding="utf-8")
            res = self._run(root, "--dry-run")
            self.assertEqual(res.returncode, 1)
            self.assertIn("product template", res.stdout)
            self.assertTrue((root / "product.md").exists())
            self.assertIn("## What data it holds", (root / "product.md").read_text())


if __name__ == "__main__":
    unittest.main()
