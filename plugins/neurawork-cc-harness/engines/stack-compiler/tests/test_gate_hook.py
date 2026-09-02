"""CLI tests for hooks/st-post-tooluse.py over a temp install.

Every case here is one the hook provably cannot spawn an agent for — a non-write
tool, a path it does not gate, an unbuilt catalog, a stack with nothing chosen, or a
debounce hit. That is deliberate: the spawn decision itself is a pure function
(``gate_lib.should_spawn``) tested in ``test_gate_lib.py``, so nothing here needs to
launch a real agent. No LLM, no network, no API key.
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

import gate_lib  # type: ignore[reportMissingImports]  # on sys.path only at runtime
import scope_lib  # type: ignore[reportMissingImports]


def _git(args: list[str], cwd: Path) -> None:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
           "PATH": os.environ.get("PATH", ""), "HOME": str(cwd)}
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   text=True, env=env)


CAPABILITIES = {
    "license_policy": {"embeddable": ["MIT"], "not_in_product": ["AGPL-3.0"]},
    "frameworks": {"gdpr": {"capabilities": [
        {"name": "Encryption at rest", "category": "Data Protection", "stack": [
            {"name": "OpenBao", "license": "MIT", "role": "in-product", "verdict": "keep",
             "why": "self-hostable secret store"},
            {"name": "age", "license": "MIT", "role": "in-product", "verdict": "keep",
             "why": "single-binary file encryption"},
        ]},
    ]}},
}


def _stack(chosen: str | None) -> dict:
    return {"choices": {"gdpr/encryption-at-rest": {
        "capability": "Encryption at rest", "framework": "gdpr",
        "options": ["OpenBao", "age"], "chosen": chosen, "applicable": True,
        "applicability_reason": "", "scoped_from": "prod-1",
    }}}


class TestGateHook(unittest.TestCase):
    def _install(self, tmp: Path, cfg: dict | None = None) -> Path:
        """A real install layout: hooks/ and scripts/ next to _shared/."""
        root = tmp / "stack-base"
        (root / "scripts").mkdir(parents=True)
        (root / "hooks").mkdir(parents=True)
        for script in (PAYLOAD / "scripts").glob("*.py"):
            shutil.copy2(script, root / "scripts" / script.name)
        for hook in (PAYLOAD / "hooks").glob("*.py"):
            shutil.copy2(hook, root / "hooks" / hook.name)
        shutil.copytree(ENGINES / "_shared", root / "_shared",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        if cfg is not None:
            (root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        return root

    def _catalog(self, tmp: Path, stack: dict) -> None:
        catalog = tmp / "compliance-base" / "catalog"
        catalog.mkdir(parents=True)
        (catalog / "capabilities.json").write_text(json.dumps(CAPABILITIES), encoding="utf-8")
        (catalog / "stack.json").write_text(json.dumps(stack), encoding="utf-8")

    def _doc(self, tmp: Path, rel: str, text: str) -> Path:
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _run(self, root: Path, payload: dict) -> subprocess.CompletedProcess:
        env = dict(os.environ, STACK_ROOT=str(root))
        env.pop("CLAUDE_INVOKED_BY", None)  # the recursion guard would exit(0) on it
        return subprocess.run(
            [sys.executable, str(root / "hooks" / "st-post-tooluse.py")],
            input=json.dumps(payload), capture_output=True, text=True, env=env,
            timeout=60, check=False,
        )

    def _advisory(self, res: subprocess.CompletedProcess) -> str:
        return json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]

    # ── Paths the hook does not gate: exit 0, print nothing at all ──

    def test_a_non_write_tool_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = self._install(Path(t))
            res = self._run(root, {"tool_name": "Read",
                                   "tool_input": {"file_path": "x.prd.md"}})
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, "")

    def test_a_non_prp_path_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            doc = self._doc(tmp, "docs/notes.md", "OpenBao everywhere")
            res = self._run(root, {"tool_name": "Write",
                                   "tool_input": {"file_path": str(doc)}})
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, "")

    def test_an_archived_plan_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            self._catalog(tmp, _stack("age"))
            doc = self._doc(tmp, ".claude/PRPs/plans/completed/old.plan.md", "OpenBao")
            res = self._run(root, {"tool_name": "Edit",
                                   "tool_input": {"file_path": str(doc)}})
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, "")

    def test_an_absent_document_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            res = self._run(root, {"tool_name": "Write", "tool_input": {
                "file_path": str(tmp / ".claude/PRPs/prds/ghost.prd.md")}})
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, "")

    def test_an_unreadable_payload_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            root = self._install(Path(t))
            res = self._run(root, {})
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, "")

    # ── Paths the hook gates but cannot spawn for ──

    def test_an_unbuilt_catalog_says_so_and_writes_no_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            doc = self._doc(tmp, ".claude/PRPs/prds/product.prd.md", "We will use OpenBao.")
            res = self._run(root, {"tool_name": "Write",
                                   "tool_input": {"file_path": str(doc)}})
            self.assertEqual(res.returncode, 0)
            self.assertIn("co-capabilities", self._advisory(res))
            self.assertFalse((root / "reports" / ".state.json").exists())

    def test_a_zero_chosen_stack_names_the_selection_pass_and_spawns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            self._catalog(tmp, _stack(None))
            doc = self._doc(tmp, ".claude/PRPs/prds/product.prd.md", "We will use OpenBao.")
            res = self._run(root, {"tool_name": "Write",
                                   "tool_input": {"file_path": str(doc)}})
            self.assertEqual(res.returncode, 0)
            self.assertIn("selection.py", self._advisory(res))
            self.assertFalse((root / "reports" / ".state.json").exists())

    def test_a_debounce_hit_reports_but_spawns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            self._catalog(tmp, _stack("age"))
            text = "We will use OpenBao for this.\n"
            doc = self._doc(tmp, ".claude/PRPs/plans/feature.plan.md", text)
            state_file = root / "reports" / ".state.json"
            before = gate_lib.record_spawn({}, str(doc), scope_lib.product_hash(text),
                                           "2026-01-01T00:00:00+01:00")
            gate_lib.save_state(state_file, before)

            res = self._run(root, {"tool_name": "Write",
                                   "tool_input": {"file_path": str(doc)}})
            self.assertEqual(res.returncode, 0)
            advisory = self._advisory(res)
            self.assertIn("OpenBao", advisory)
            self.assertIn("gdpr/encryption-at-rest", advisory)
            self.assertIn("age", advisory)
            self.assertEqual(gate_lib.load_state(state_file), before,
                             "an unchanged document re-stamped the ledger")
            self.assertNotIn("decision", json.loads(res.stdout))

    def test_a_document_in_the_prp_store_layout_is_gated(self) -> None:
        # The defect this suite missed: with the store wired through ``PRP_HOME``,
        # every document prp-core writes sits under ``<slug>-<hash8>/`` and the hook
        # returned before printing anything — indistinguishable from a gate that ran
        # and approved. Pre-stamp the ledger so this stays a spawn-free case.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp)
            self._catalog(tmp, _stack("age"))
            text = "We will use OpenBao for this.\n"
            store = ".claude/PRPs/howtobuildsoftware2026-35325a96"
            for rel in (f"{store}/plans/feature.plan.md", f"{store}/prds/product.prd.md"):
                doc = self._doc(tmp, rel, text)
                state_file = root / "reports" / ".state.json"
                gate_lib.save_state(
                    state_file,
                    gate_lib.record_spawn(gate_lib.load_state(state_file), str(doc),
                                          scope_lib.product_hash(text),
                                          "2026-01-01T00:00:00+01:00"))
                res = self._run(root, {"tool_name": "Write",
                                       "tool_input": {"file_path": str(doc)}})
                self.assertEqual(res.returncode, 0)
                self.assertNotEqual(res.stdout, "", f"{rel}: the gate stayed silent")
                self.assertIn("OpenBao", self._advisory(res))

    def test_a_worktree_session_writing_through_the_linked_store_is_gated(self) -> None:
        # The symlinked store puts a worktree session's document in the MAIN checkout,
        # so `relative_to(<worktree>)` finds nothing and the hook would return before
        # printing — the same silent gate, one layer down. The install under test is the
        # WORKTREE's; the document it must still classify lives in the main checkout.
        if shutil.which("git") is None:
            self.skipTest("git not on PATH")
        with tempfile.TemporaryDirectory() as t:
            base = Path(t).resolve()
            main, wt = base / "main", base / "wt"
            _git(["init", "-q", "-b", "main", str(main)], base)
            _git(["-C", str(main), "commit", "-q", "--allow-empty", "-m", "init"], base)
            _git(["-C", str(main), "worktree", "add", "-q", str(wt), "-b", "side"], base)

            root = self._install(wt)          # the worktree's own install
            self._catalog(wt, _stack("age"))  # …and its own catalog
            text = "We will use OpenBao for this.\n"
            doc = self._doc(main, ".claude/PRPs/plans/feature.plan.md", text)
            link = base / "prp-home" / "main-key"
            link.parent.mkdir(parents=True)
            link.symlink_to(main / ".claude" / "PRPs", target_is_directory=True)
            through_link = link / "plans" / "feature.plan.md"
            self.assertTrue(through_link.exists(), "the fixture link does not resolve")

            state_file = root / "reports" / ".state.json"
            gate_lib.save_state(
                state_file,
                gate_lib.record_spawn(gate_lib.load_state(state_file), str(doc),
                                      scope_lib.product_hash(text),
                                      "2026-01-01T00:00:00+01:00"))
            res = self._run(root, {"tool_name": "Write",
                                   "tool_input": {"file_path": str(through_link)}})
            self.assertEqual(res.returncode, 0)
            self.assertNotEqual(res.stdout, "", "the gate stayed silent for a worktree write")
            self.assertIn("OpenBao", self._advisory(res))

    def test_block_mode_blocks_only_on_an_off_stack_component(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root = self._install(tmp, cfg={"validate_mode": {"prd": "warn", "plan": "block"}})
            self._catalog(tmp, _stack("age"))
            blocked = "We will use OpenBao for this.\n"
            clean = "We will use age for this.\n"
            for rel, text, expect_block in (
                (".claude/PRPs/plans/off.plan.md", blocked, True),
                (".claude/PRPs/plans/on.plan.md", clean, False),
                (".claude/PRPs/prds/off.prd.md", blocked, False),  # prd stays on warn
            ):
                doc = self._doc(tmp, rel, text)
                # Pre-stamp the ledger so this write is a debounce hit and spawns nothing.
                gate_lib.save_state(
                    root / "reports" / ".state.json",
                    gate_lib.record_spawn(gate_lib.load_state(root / "reports" / ".state.json"),
                                          str(doc), scope_lib.product_hash(text),
                                          "2026-01-01T00:00:00+01:00"))
                res = self._run(root, {"tool_name": "Write",
                                       "tool_input": {"file_path": str(doc)}})
                self.assertEqual(res.returncode, 0)
                self.assertEqual(json.loads(res.stdout).get("decision") == "block", expect_block,
                                 f"{rel} blocked unexpectedly" if not expect_block
                                 else f"{rel} did not block")


if __name__ == "__main__":
    unittest.main()
