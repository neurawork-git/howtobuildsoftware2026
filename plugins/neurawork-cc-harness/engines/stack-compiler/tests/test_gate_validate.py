"""CLI tests for validate.py: the preflight ladder, and the verdict it will not judge on.

Every case here stops before the agent call — a missing dependency, an unscoped
stack, or an unusable verdict file. The set math itself lives in ``gate_lib.verdict``
and is tested in ``test_gate_lib.py``. No LLM, no network, no API key.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
ENGINES = ENGINE.parent
PAYLOAD = ENGINE / "payload"
sys.path.insert(0, str(PAYLOAD / "scripts"))

import validate

CAPABILITIES = {
    "license_policy": {"embeddable": ["MIT"], "not_in_product": ["AGPL-3.0"]},
    "frameworks": {"gdpr": {"capabilities": [
        {"name": "Encryption at rest", "category": "Data Protection", "stack": [
            {"name": "OpenBao", "license": "MIT", "role": "in-product", "verdict": "keep",
             "why": "self-hostable secret store"},
        ]},
    ]}},
}


class TestValidateCLI(unittest.TestCase):
    """A missing dependency fails loudly and cheaply, and never calls an agent."""

    def _install(self, tmp: Path) -> Path:
        root = tmp / "stack-base"
        (root / "scripts").mkdir(parents=True)
        for script in (PAYLOAD / "scripts").glob("*.py"):
            shutil.copy2(script, root / "scripts" / script.name)
        shutil.copytree(ENGINES / "_shared", root / "_shared",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        return root

    def _doc(self, tmp: Path, rel: str = ".claude/PRPs/prds/product.prd.md") -> Path:
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("We will use OpenBao.\n", encoding="utf-8")
        return path

    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, STACK_ROOT=str(root))
        return subprocess.run([sys.executable, str(root / "scripts" / "validate.py"), *args],
                              capture_output=True, text=True, env=env, timeout=60, check=False)

    def test_no_argument_prints_usage(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            res = self._run(self._install(Path(t)))
            self.assertEqual(res.returncode, 2)
            self.assertIn("Usage", res.stdout)

    def test_a_missing_document_fails(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            res = self._run(self._install(tmp), str(tmp / ".claude/PRPs/prds/ghost.prd.md"))
            self.assertEqual(res.returncode, 1)
            self.assertIn("not found", res.stdout)

    def test_missing_compliance_install(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            res = self._run(self._install(tmp), str(self._doc(tmp)))
            self.assertEqual(res.returncode, 1)
            self.assertIn("No compliance install", res.stdout)

    def test_missing_stack_json_names_the_scaffold_command(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            catalog = tmp / "compliance-base" / "catalog"
            catalog.mkdir(parents=True)
            (catalog / "capabilities.json").write_text(json.dumps(CAPABILITIES),
                                                       encoding="utf-8")
            res = self._run(root, str(self._doc(tmp)))
            self.assertEqual(res.returncode, 1)
            self.assertIn("--scaffold", res.stdout)

    def test_an_unscoped_stack_points_at_the_scope_pass(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            catalog = tmp / "compliance-base" / "catalog"
            catalog.mkdir(parents=True)
            (catalog / "capabilities.json").write_text(json.dumps(CAPABILITIES),
                                                       encoding="utf-8")
            (catalog / "stack.json").write_text(json.dumps({"choices": {
                "gdpr/encryption-at-rest": {"capability": "Encryption at rest",
                                            "framework": "gdpr", "options": ["OpenBao"],
                                            "applicable": True, "scoped_from": None}}}),
                encoding="utf-8")
            res = self._run(root, str(self._doc(tmp)))
            self.assertEqual(res.returncode, 1)
            self.assertIn("no scoping decisions", res.stdout)
            self.assertIn("scope.py", res.stdout)
            self.assertFalse((root / "reports").exists(), "preflight wrote a report")


class TestRepoRootSplit(unittest.TestCase):
    """The catalog comes from the document's working tree, not from the install's.

    Inside a worktree the hook redirects ``STACK_ROOT`` to the main checkout so reports
    and the ledger survive `git worktree remove` — but the decisions a document is
    judged against are the ones its own branch records. Without the split, every
    scoping, ranking or selection branch would be checked against main's `stack.json`.
    """

    def _install(self, tmp: Path) -> Path:
        root = tmp / "main" / "stack-base"
        (root / "scripts").mkdir(parents=True)
        for script in (PAYLOAD / "scripts").glob("*.py"):
            shutil.copy2(script, root / "scripts" / script.name)
        shutil.copytree(ENGINES / "_shared", root / "_shared",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        return root

    def test_the_documents_tree_supplies_the_catalog(self) -> None:
        """Both trees are broken, but differently — the message names the one consulted.

        Deliberately proven on two failing preflights rather than on one passing run:
        a run that clears preflight calls the SDK agent, and no test in this suite may
        do that.
        """
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)                    # install under tmp/main
            # tmp/main has no compliance install at all; tmp/wt has one, missing stack.json.
            catalog = tmp / "wt" / "compliance-base" / "catalog"
            catalog.mkdir(parents=True)
            (catalog / "capabilities.json").write_text(json.dumps(CAPABILITIES),
                                                       encoding="utf-8")
            doc = tmp / "wt" / ".claude/PRPs/prds/product.prd.md"
            doc.parent.mkdir(parents=True)
            doc.write_text("We will use OpenBao.\n", encoding="utf-8")
            env = dict(os.environ, STACK_ROOT=str(root))

            without = subprocess.run(
                [sys.executable, str(root / "scripts" / "validate.py"), str(doc)],
                capture_output=True, text=True, env=env, timeout=60, check=False)
            self.assertEqual(without.returncode, 1)
            self.assertIn("No compliance install", without.stdout)

            with_root = subprocess.run(
                [sys.executable, str(root / "scripts" / "validate.py"), str(doc),
                 "--repo-root", str(tmp / "wt")],
                capture_output=True, text=True, env=env, timeout=60, check=False)
            self.assertEqual(with_root.returncode, 1)
            self.assertIn("--scaffold", with_root.stdout)
            self.assertNotIn("No compliance install", with_root.stdout)


class TestVerdictFile(unittest.TestCase):
    """A verdict this script cannot use is reported, never assumed to pass."""

    def test_absent_corrupt_and_malformed_all_read_as_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "x.stack.json"
            self.assertIsNone(validate._load_verdict(path))
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(validate._load_verdict(path))
            path.write_text(json.dumps({"reasoning": "forgot the list"}), encoding="utf-8")
            self.assertIsNone(validate._load_verdict(path))
            path.write_text(json.dumps({"proposed": "OpenBao"}), encoding="utf-8")
            self.assertIsNone(validate._load_verdict(path))

    def test_a_well_formed_verdict_is_returned_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "x.stack.json"
            raw = {"proposed": ["OpenBao"], "ignored_capabilities": [], "reasoning": "…"}
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(validate._load_verdict(path), raw)


if __name__ == "__main__":
    unittest.main()
