"""Stdlib tests for the harness doctor.

Fixtures are temp repos built from the REAL shipped payload (the same files
``install.py`` copies), so "complete install" means what it means in production and
an added payload script cannot silently fall out of the integrity check.

Environment findings (uv on PATH, an API key, the python version) depend on the
machine running the suite, so every assertion here is scoped to one engine's
findings. The whole-report behaviour — exit codes, --json, the live stall — is
proved by the plan's runtime validation runs, not here. No network, no LLM.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import doctor  # noqa: E402
import harness_probe as probe  # noqa: E402

DAY = 24 * 3600


def make_repo(tmp: Path, *, worktree: bool = False) -> Path:
    """A repo root the doctor can resolve: `.git` dir, or `.git` file for a worktree."""
    repo = tmp / "repo"
    repo.mkdir()
    if worktree:
        (repo / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n", encoding="utf-8")
    else:
        (repo / ".git").mkdir()
    return repo


def install(repo: Path, engine_name: str, dirname: str, version: str | None = None) -> Path:
    """Materialise a complete install of `engine_name`, mirroring install.py."""
    engine = probe.ENGINES[engine_name]
    source = PLUGIN_ROOT / "engines" / engine_name
    target = repo / dirname
    for rel in probe.payload_files(PLUGIN_ROOT, engine_name):
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / "payload" / rel, dst)
    shutil.copytree(
        PLUGIN_ROOT / "engines" / "_shared",
        target / "_shared",
        ignore=shutil.ignore_patterns("__pycache__"),
        dirs_exist_ok=True,
    )
    for rel, _tracked in engine.data_dirs:
        (target / rel).mkdir(parents=True, exist_ok=True)
    (target / ".venv").mkdir(exist_ok=True)
    (target / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    shutil.copy2(source / "config.default.json", target / "config.json")
    (target / "VERSION").write_text(
        version or (source / "VERSION").read_text(encoding="utf-8").strip(),
        encoding="utf-8",
    )
    return target


def settings_for(repo: Path, *pairs: tuple[str, str]) -> dict:
    """Write a settings.json wiring every hook of each (engine, dirname) pair."""
    hooks: dict[str, list] = {}
    for engine_name, dirname in pairs:
        for event, script in probe.ENGINES[engine_name].hooks.items():
            command = f'uv run --directory "$CLAUDE_PROJECT_DIR/{dirname}" python {script}'
            hooks.setdefault(event, [{"matcher": "", "hooks": []}])
            hooks[event][0]["hooks"].append(
                {"type": "command", "command": command, "timeout": 10}
            )
    data = {"hooks": hooks}
    claude = repo / ".claude"
    claude.mkdir(exist_ok=True)
    (claude / "settings.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def daily(target: Path, name: str, body: str = "log\n") -> Path:
    path = target / "daily" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def stamp(target: Path, engine_name: str, ts: float) -> None:
    queue = probe.ENGINES[engine_name].queue
    assert queue is not None
    path = target / queue.stamp
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ts": ts}), encoding="utf-8")


def lock(target: Path, engine_name: str, mtime: float) -> Path:
    import os

    queue = probe.ENGINES[engine_name].queue
    assert queue is not None
    path = target / queue.lock
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(mtime), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def state(target: Path, engine_name: str, ingested: dict) -> None:
    queue = probe.ENGINES[engine_name].queue
    assert queue is not None
    path = target / queue.state
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ingested": ingested}), encoding="utf-8")


class DoctorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.now = 1_800_000_000.0

    def run_checks(self, repo: Path) -> list[doctor.Finding]:
        return doctor.run_checks(repo, PLUGIN_ROOT, now=self.now)

    def for_engine(self, findings: list[doctor.Finding], engine: str) -> list[doctor.Finding]:
        return [f for f in findings if f.engine == engine]

    def loud(self, findings: list[doctor.Finding], engine: str) -> list[doctor.Finding]:
        """Only the findings that would change the exit code."""
        return [f for f in self.for_engine(findings, engine) if f.severity in ("WARN", "ERROR")]

    def check(self, findings: list[doctor.Finding], engine: str, name: str):
        matches = [f for f in self.for_engine(findings, engine) if f.check == name]
        self.assertTrue(matches, f"no '{name}' finding for {engine}")
        return matches[0]


class HealthyInstallTests(DoctorTestCase):
    def test_a_complete_current_drained_install_is_quiet(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "knowledge-compiler", "knowledge-base")
        settings_for(repo, ("knowledge-compiler", "knowledge-base"))
        log = daily(target, "2026-08-20.md")
        state(repo / "knowledge-base", "knowledge-compiler",
              {"2026-08-20.md": {"hash": doctor.file_hash(log)}})
        stamp(target, "knowledge-compiler", self.now - 60)

        self.assertEqual(
            [(f.severity, f.check, f.message)
             for f in self.loud(self.run_checks(repo), "knowledge-compiler")],
            [],
        )

    def test_an_absent_engine_is_a_note_not_a_fault(self) -> None:
        repo = make_repo(self.tmp)
        settings_for(repo)
        self.assertEqual(self.loud(self.run_checks(repo), "stack-compiler"), [])
        self.assertEqual(
            self.check(self.run_checks(repo), "stack-compiler", "discovery").severity,
            "NOTE",
        )


class QueueTests(DoctorTestCase):
    def _stalled(self, *, worktree: bool = False) -> Path:
        repo = make_repo(self.tmp, worktree=worktree)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md")
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        lock(target, "claudemd-lerner", self.now - 600)  # fresh: 10 min old, gate is 6h
        return repo

    def test_a_fresh_lock_over_an_older_stamp_is_the_stall(self) -> None:
        finding = self.check(self.run_checks(self._stalled()), "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("1 pending", finding.message)
        self.assertIn("never completed", finding.message)
        # The lock time and the reopen time are what makes the finding actionable.
        self.assertIn(doctor.stamp_time(self.now - 600), finding.message)
        self.assertIn(doctor.stamp_time(self.now - 600 + 6 * 3600), finding.message)
        self.assertIn("scripts/update.py", finding.fix)

    def test_the_same_stall_inside_a_worktree_is_suppressed_by_design(self) -> None:
        finding = self.check(
            self.run_checks(self._stalled(worktree=True)), "claudemd-lerner", "queue"
        )
        self.assertEqual(finding.severity, "NOTE")
        self.assertIn("worktree", finding.message)

    def test_an_eligible_gate_warns_rather_than_errors(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md")
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)  # no lock at all
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("eligible", finding.message)

    def test_a_missing_state_file_makes_every_log_pending(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        for name in ("2026-07-02.md", "2026-07-23.md", "2026-08-20.md"):
            daily(target, name)
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertIn("3 pending", finding.message)
        self.assertIn("no scripts/state.json", finding.message)

    def test_a_log_edited_after_ingestion_counts_as_pending(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        log = daily(target, "2026-08-20.md", "original\n")
        state(target, "claudemd-lerner", {"2026-08-20.md": {"hash": doctor.file_hash(log)}})
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        self.assertEqual(
            self.check(self.run_checks(repo), "claudemd-lerner", "queue").severity, "OK"
        )

        log.write_text("edited since it was ingested\n", encoding="utf-8")
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertIn("1 pending", finding.message)


class VersionTests(DoctorTestCase):
    def _repo(self, version: str | None = None) -> Path:
        repo = make_repo(self.tmp)
        install(repo, "knowledge-compiler", "knowledge-base", version=version)
        settings_for(repo, ("knowledge-compiler", "knowledge-base"))
        return repo

    def test_behind_names_both_versions_and_the_installer(self) -> None:
        shipped = (PLUGIN_ROOT / "engines" / "knowledge-compiler" / "VERSION").read_text().strip()
        finding = self.check(self.run_checks(self._repo("0")), "knowledge-compiler", "version")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("0", finding.message)
        self.assertIn(shipped, finding.message)
        self.assertIn("/neurawork-cc-harness:knowledge-compiler", finding.fix)

    def test_current_is_ok(self) -> None:
        self.assertEqual(
            self.check(self.run_checks(self._repo()), "knowledge-compiler", "version").severity,
            "OK",
        )

    def test_edited_shared_helper_reports_drift(self) -> None:
        repo = self._repo()
        target = repo / "knowledge-base" / "_shared" / "gitctx.py"
        target.write_text(target.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")
        finding = self.check(self.run_checks(repo), "knowledge-compiler", "shared")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("gitctx.py", finding.message)

    def test_the_shared_fix_never_points_at_a_payload(self) -> None:
        # `_shared/` is deliberately absent from every payload/ — the installer copies it
        # from engines/_shared/. An installer-less engine told to "mirror the payload"
        # would go looking for files that are not there.
        repo = make_repo(self.tmp)
        install(repo, "stack-compiler", "stack-base")
        settings_for(repo, ("stack-compiler", "stack-base"))
        target = repo / "stack-base" / "_shared" / "gitctx.py"
        target.write_text(target.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")
        finding = self.check(self.run_checks(repo), "stack-compiler", "shared")
        self.assertNotIn("payload", finding.fix)
        self.assertIn("engines/_shared", finding.fix)


class WiringTests(DoctorTestCase):
    def test_an_installed_dir_with_no_hook_is_an_error(self) -> None:
        repo = make_repo(self.tmp)
        install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo)  # nothing wired
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "discovery")
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("not wired", finding.message)
        self.assertIn("/neurawork-cc-harness:claudemd-lerner", finding.fix)

    def test_a_hook_pointing_at_a_missing_dir_is_an_orphan(self) -> None:
        repo = make_repo(self.tmp)
        settings_for(repo, ("knowledge-compiler", "gone"))
        finding = self.check(self.run_checks(repo), "knowledge-compiler", "discovery")
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("orphaned hook", finding.message)

    def test_a_partially_wired_install_names_the_missing_events(self) -> None:
        repo = make_repo(self.tmp)
        install(repo, "knowledge-compiler", "knowledge-base")
        claude = repo / ".claude"
        claude.mkdir()
        command = ('uv run --directory "$CLAUDE_PROJECT_DIR/knowledge-base" python '
                   "hooks/session-start.py")
        (claude / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": [
            {"matcher": "", "hooks": [{"type": "command", "command": command}]}
        ]}}), encoding="utf-8")
        finding = self.check(self.run_checks(repo), "knowledge-compiler", "wiring")
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("SessionEnd", finding.message)

    def test_a_missing_payload_file_is_an_integrity_error(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "knowledge-compiler", "knowledge-base")
        (target / "scripts" / "compile.py").unlink()
        settings_for(repo, ("knowledge-compiler", "knowledge-base"))
        finding = self.check(self.run_checks(repo), "knowledge-compiler", "integrity")
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("scripts/compile.py", finding.message)

    def test_an_absent_venv_warns_with_the_sync_command(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "knowledge-compiler", "knowledge-base")
        (target / ".venv").rmdir()
        settings_for(repo, ("knowledge-compiler", "knowledge-base"))
        finding = self.check(self.run_checks(repo), "knowledge-compiler", "venv")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("uv sync --directory knowledge-base", finding.fix)

    def test_an_untracked_data_dir_is_only_a_note(self) -> None:
        # daily/ is gitignored: legitimately absent in a fresh clone and in a worktree.
        repo = make_repo(self.tmp)
        target = install(repo, "knowledge-compiler", "knowledge-base")
        (target / "daily").rmdir()
        settings_for(repo, ("knowledge-compiler", "knowledge-base"))
        severities = {f.severity for f in self.for_engine(self.run_checks(repo),
                                                          "knowledge-compiler")
                      if f.check == "data" and "daily" in f.message}
        self.assertEqual(severities, {"NOTE"})

    def test_a_tracked_data_dir_missing_is_an_error(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "knowledge-compiler", "knowledge-base")
        shutil.rmtree(target / "knowledge")
        settings_for(repo, ("knowledge-compiler", "knowledge-base"))
        severities = {f.severity for f in self.for_engine(self.run_checks(repo), "knowledge-compiler")
                      if f.check == "data" and "knowledge" in f.message}
        self.assertEqual(severities, {"ERROR"})


class DegradedEnvironmentTests(DoctorTestCase):
    def test_unparsable_settings_still_produces_a_report(self) -> None:
        repo = make_repo(self.tmp)
        install(repo, "claudemd-lerner", "claudemd-lerner")
        claude = repo / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text("{ not json", encoding="utf-8")

        findings = self.run_checks(repo)
        settings_finding = self.check(findings, "-", "settings")
        self.assertEqual(settings_finding.severity, "ERROR")
        # The whole point: discovery keeps working off the directory scan.
        discovery = self.check(findings, "claudemd-lerner", "discovery")
        self.assertIn("claudemd-lerner", discovery.message)


class CatalogTests(DoctorTestCase):
    def test_a_missing_framework_catalog_warns_with_the_extract_command(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "compliance-compiler", "compliance-base")
        settings_for(repo, ("compliance-compiler", "compliance-base"))
        finding = self.check(self.run_checks(repo), "compliance-compiler", "catalog")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("gdpr.json", finding.message)
        self.assertIn("co-extract", finding.fix)

        seed = PLUGIN_ROOT / "engines" / "compliance-compiler" / "payload" / "catalog-seed"
        for src in seed.glob("*.json"):
            shutil.copy2(src, target / "catalog" / src.name)
        (target / "catalog" / "stack.json").write_text("{}", encoding="utf-8")
        self.assertEqual(
            self.check(self.run_checks(repo), "compliance-compiler", "catalog").severity, "OK"
        )

    def test_an_unparsable_catalog_file_is_an_error(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "compliance-compiler", "compliance-base")
        settings_for(repo, ("compliance-compiler", "compliance-base"))
        (target / "catalog" / "gdpr.json").write_text("{ broken", encoding="utf-8")
        severities = {f.severity for f in self.for_engine(self.run_checks(repo), "compliance-compiler")
                      if f.check == "catalog"}
        self.assertIn("ERROR", severities)


class ReportTests(DoctorTestCase):
    def _findings(self, *severities: str) -> list[doctor.Finding]:
        return [doctor.Finding(s, "e", "c", "m", "f") for s in severities]

    def test_exit_code_follows_the_worst_severity(self) -> None:
        for severities, worst, code in (
            (("OK",), "OK", 0),
            (("OK", "NOTE"), "NOTE", 0),
            (("NOTE", "WARN"), "WARN", 1),
            (("WARN", "ERROR", "OK"), "ERROR", 2),
        ):
            with self.subTest(severities=severities):
                findings = self._findings(*severities)
                self.assertEqual(doctor.worst(findings), worst)
                self.assertEqual(doctor.exit_code(findings), code)

    def test_json_payload_carries_the_findings_and_the_worst(self) -> None:
        findings = self._findings("OK", "ERROR")
        payload = json.loads(doctor.render_json(Path("/repo"), PLUGIN_ROOT, findings))
        self.assertEqual(payload["repo"], "/repo")
        self.assertEqual(payload["worst"], "ERROR")
        self.assertEqual(len(payload["findings"]), 2)
        self.assertEqual(payload["findings"][0]["severity"], "OK")

    def test_the_text_report_prints_every_fix(self) -> None:
        text = doctor.render_text(
            Path("/repo"), PLUGIN_ROOT,
            [doctor.Finding("ERROR", "claudemd-lerner", "queue", "stalled", "run update.py")],
        )
        self.assertIn("ERROR", text)
        self.assertIn("stalled", text)
        self.assertIn("run update.py", text)


class ReadOnlyTests(DoctorTestCase):
    def test_a_run_leaves_the_repo_byte_identical(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md")
        lock(target, "claudemd-lerner", self.now - 600)

        def snapshot() -> dict[str, tuple[int, float]]:
            return {
                str(p.relative_to(repo)): (p.stat().st_size, p.stat().st_mtime)
                for p in sorted(repo.rglob("*")) if p.is_file()
            }

        before = snapshot()
        self.run_checks(repo)
        self.assertEqual(snapshot(), before)

    def test_the_source_spawns_nothing(self) -> None:
        source = (PLUGIN_ROOT / "scripts" / "doctor.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "Popen", "mkdir", "write_text", "os.remove", "unlink"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(
                    forbidden,
                    source,
                    "the doctor's whole contract is that it only reads — it must be "
                    "runnable against a broken install without changing its state",
                )


if __name__ == "__main__":
    unittest.main()
