"""CLI tests for selection.py: preflight, sheet render, and a refused apply.

No LLM, no network — this pass has no agent at all. The subprocess runs the script
exactly as an install does, with ``STACK_ROOT`` pointing at a temp install.
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

ENGINES = Path(__file__).resolve().parent.parent.parent
SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import selection_lib


def _capabilities() -> dict:
    return {
        "generated": "2026-01-01",
        "license_policy": {"embeddable": ["MIT", "MPL-2.0"], "not_in_product": ["AGPL-3.0"]},
        "frameworks": {"gdpr": {"capabilities": [
            {"name": "Encryption at rest", "category": "Data Protection",
             "description": "Encrypt stored personal data.", "satisfies": ["GDPR-ART5-01"],
             "stack": [{"name": "OpenBao", "license": "MPL-2.0", "role": "in-product",
                        "verdict": "keep", "why": "self-hostable secret store"},
                       {"name": "age", "license": "MIT", "role": "in-product",
                        "verdict": "keep", "why": "single-binary file encryption"}]},
            {"name": "Consent capture", "category": "Governance & Privacy Ops",
             "description": "Record consent.", "satisfies": ["GDPR-ART7-01"],
             "stack": [{"name": "Klaro!", "license": "MIT", "role": "in-product",
                        "verdict": "keep", "why": "consent banner"}]},
        ]}},
    }


def _stack() -> dict:
    return {"choices": {
        "gdpr/encryption-at-rest": {
            "capability": "Encryption at rest", "framework": "gdpr", "mandatory_linked": True,
            "options": ["OpenBao", "age"], "chosen": None, "rationale": "", "chosen_from": None,
            "applicable": True, "applicability_reason": "", "scoped_from": "prod-1",
            "ranked": [{"component": "age", "rationale": "single binary, no operator"},
                       {"component": "OpenBao", "rationale": "needs an operator"}],
            "ranked_from": "prod-1",
        },
        "gdpr/consent-capture": {
            "capability": "Consent capture", "framework": "gdpr", "mandatory_linked": False,
            "options": ["Klaro!"], "chosen": None, "rationale": "", "chosen_from": None,
            "applicable": False, "applicability_reason": "no consent is ever collected",
            "scoped_from": "prod-1", "ranked": None, "ranked_from": None,
        },
    }}


class TestSelectionCLI(unittest.TestCase):
    """A missing dependency fails loudly and cheaply; a bad sheet writes nothing."""

    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, STACK_ROOT=str(root))
        return subprocess.run([sys.executable, str(root / "scripts" / "selection.py"), *args],
                              capture_output=True, text=True, env=env,
                              timeout=60, check=False)

    def _stack_dir(self, tmp: Path) -> Path:
        """A real install layout: scripts/ next to _shared/, as install.py lays it out.

        The script is run from there rather than from payload/ because it resolves
        ``_shared`` (the write guard) relative to its own parent directory.
        """
        root = tmp / "stack-base"
        (root / "scripts").mkdir(parents=True)
        for script in SCRIPTS.glob("*.py"):
            shutil.copy2(script, root / "scripts" / script.name)
        shutil.copytree(ENGINES / "_shared", root / "_shared",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        return root

    def _compliance(self, tmp: Path, stack_json: dict, capabilities: dict | None = None) -> Path:
        comp = tmp / "compliance-base"
        (comp / "catalog").mkdir(parents=True)
        (comp / "scripts").mkdir(parents=True)
        (comp / "scripts" / "stack.py").write_text("", encoding="utf-8")
        (comp / "catalog" / "capabilities.json").write_text(
            json.dumps(capabilities if capabilities is not None else _capabilities()),
            encoding="utf-8")
        (comp / "catalog" / "stack.json").write_text(json.dumps(stack_json), encoding="utf-8")
        return comp

    def test_missing_compliance_install(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            res = self._run(self._stack_dir(Path(t)))
            self.assertEqual(res.returncode, 1)
            self.assertIn("No compliance install", res.stdout)

    def test_missing_stack_json_names_the_scaffold_command(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            catalog = tmp / "compliance-base" / "catalog"
            catalog.mkdir(parents=True)
            (catalog / "capabilities.json").write_text("{}", encoding="utf-8")
            res = self._run(root)
            self.assertEqual(res.returncode, 1)
            self.assertIn("--scaffold", res.stdout)

    def test_an_unscoped_stack_points_at_the_scope_pass(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            self._compliance(tmp, {"choices": {"gdpr/x": {
                "capability": "X", "framework": "gdpr", "options": ["A"],
                "applicable": True, "scoped_from": None}}})
            res = self._run(root)
            self.assertEqual(res.returncode, 1)
            self.assertIn("no scoping decisions", res.stdout)
            self.assertIn("scope.py", res.stdout)

    def test_a_fully_scoped_out_product_has_nothing_to_select(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            self._compliance(tmp, {"choices": {"gdpr/x": {
                "capability": "X", "framework": "gdpr", "options": ["A"],
                "applicable": False, "scoped_from": "h1"}}})
            res = self._run(root)
            self.assertEqual(res.returncode, 0)
            self.assertIn("nothing to select", res.stdout)

    def test_renders_a_sheet_carrying_only_the_applicable_capability(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            self._compliance(tmp, _stack())
            res = self._run(root)
            self.assertEqual(res.returncode, 0)
            self.assertIn("1 applicable capability/-ies: 0 chosen, 1 undecided", res.stdout)
            sheets = list((root / "reports").glob("selection-sheet-*.md"))
            self.assertEqual(len(sheets), 1)
            md = sheets[0].read_text(encoding="utf-8")
            self.assertIn("## gdpr/encryption-at-rest", md)
            self.assertNotIn("gdpr/consent-capture", md)
            self.assertIn("\nchoice:\n", md)

    def test_an_off_pool_choice_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            stack_json = _stack()
            comp = self._compliance(tmp, stack_json)
            before = (comp / "catalog" / "stack.json").read_bytes()

            universe = selection_lib.selectable_universe(stack_json, _capabilities())
            sheet = root / "sheet.md"
            sheet.write_text(
                selection_lib.render_sheet(universe, "2026-02-02").replace(
                    "choice:\n", "choice: HashiCorp Vault\n", 1),
                encoding="utf-8")

            res = self._run(root, "--apply", str(sheet))
            self.assertEqual(res.returncode, 1)
            self.assertIn("no component 'HashiCorp Vault'", res.stdout)
            self.assertEqual((comp / "catalog" / "stack.json").read_bytes(), before)

    def test_an_unfilled_sheet_records_nothing_and_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            stack_json = _stack()
            comp = self._compliance(tmp, stack_json)
            before = (comp / "catalog" / "stack.json").read_bytes()

            universe = selection_lib.selectable_universe(stack_json, _capabilities())
            sheet = root / "sheet.md"
            sheet.write_text(selection_lib.render_sheet(universe, "2026-02-02"),
                             encoding="utf-8")

            res = self._run(root, "--apply", str(sheet))
            self.assertEqual(res.returncode, 0)
            self.assertIn("no filled `choice:` line", res.stdout)
            self.assertEqual((comp / "catalog" / "stack.json").read_bytes(), before)

    def test_dry_run_gates_and_reports_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._stack_dir(tmp)
            stack_json = _stack()
            comp = self._compliance(tmp, stack_json)
            before = (comp / "catalog" / "stack.json").read_bytes()

            universe = selection_lib.selectable_universe(stack_json, _capabilities())
            sheet = root / "sheet.md"
            sheet.write_text(
                selection_lib.render_sheet(universe, "2026-02-02").replace(
                    "choice:\n", "choice: 1\n", 1),
                encoding="utf-8")

            res = self._run(root, "--apply", str(sheet), "--dry-run")
            self.assertEqual(res.returncode, 0)
            self.assertIn("[DRY RUN]", res.stdout)
            self.assertEqual((comp / "catalog" / "stack.json").read_bytes(), before)
            self.assertTrue(list((root / "reports").glob("selection-2*.md")))


class TestSelectionReachesTheSchemaOwner(unittest.TestCase):
    """End to end against the real stack.py: the two engines' field names must match."""

    def _install(self, tmp: Path) -> tuple[Path, Path]:
        root = tmp / "stack-base"
        (root / "scripts").mkdir(parents=True)
        for script in SCRIPTS.glob("*.py"):
            shutil.copy2(script, root / "scripts" / script.name)
        shutil.copytree(ENGINES / "_shared", root / "_shared",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))

        comp = tmp / "compliance-base"
        (comp / "scripts").mkdir(parents=True)
        (comp / "catalog").mkdir(parents=True)
        for script in (ENGINES / "compliance-compiler" / "payload" / "scripts").glob("*.py"):
            shutil.copy2(script, comp / "scripts" / script.name)
        shutil.copytree(ENGINES / "_shared", comp / "_shared",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (comp / "catalog" / "gdpr.json").write_text(json.dumps(
            {"framework": "gdpr", "constraints": [{"id": "GDPR-ART5-01", "mandatory": True},
                                                  {"id": "GDPR-ART7-01", "mandatory": False}]}),
            encoding="utf-8")
        (comp / "catalog" / "capabilities.json").write_text(
            json.dumps(_capabilities()), encoding="utf-8")
        (comp / "catalog" / "stack.json").write_text(json.dumps(_stack()), encoding="utf-8")
        return root, comp

    def test_a_confirmed_choice_lands_in_stack_json_with_its_catalog_reference(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root, comp = self._install(tmp)

            universe = selection_lib.selectable_universe(_stack(), _capabilities())
            sheet = root / "sheet.md"
            sheet.write_text(
                selection_lib.render_sheet(universe, "2026-02-02").replace(
                    "choice:\n", "choice: 1\n", 1).replace(
                    "reason:\n", "reason: no operator to run a server\n", 1),
                encoding="utf-8")

            res = subprocess.run(
                [sys.executable, str(root / "scripts" / "selection.py"), "--apply", str(sheet)],
                capture_output=True, text=True, timeout=60, check=False,
                env=dict(os.environ, STACK_ROOT=str(root)))
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

            written = json.loads((comp / "catalog" / "stack.json").read_text(encoding="utf-8"))
            enc = written["choices"]["gdpr/encryption-at-rest"]
            self.assertEqual(enc["chosen"], "age")        # rank 1 of the recorded ranking
            self.assertEqual(enc["rationale"], "no operator to run a server")
            self.assertTrue(enc["chosen_from"])           # decided against a known catalog state
            self.assertEqual(enc["ranked_from"], "prod-1")   # ranking untouched
            self.assertEqual(enc["scoped_from"], "prod-1")   # scoping untouched
            # The scoped-out capability keeps its recorded decision and stays unchosen.
            self.assertIsNone(written["choices"]["gdpr/consent-capture"]["chosen"])
            self.assertIn("1 choice(s) recorded", res.stdout)


if __name__ == "__main__":
    unittest.main()
