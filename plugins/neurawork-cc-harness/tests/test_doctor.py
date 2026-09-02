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
from dataclasses import replace
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import doctor  # noqa: E402
import harness_probe as probe  # noqa: E402

DAY = 24 * 3600


def make_repo(tmp: Path, *, name: str = "repo") -> Path:
    """A main checkout the doctor can resolve: `.git` is a directory."""
    repo = tmp / name
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def make_worktree(tmp: Path, main: Path | str, *, name: str = "wt") -> Path:
    """A linked worktree: `.git` is a FILE holding `gitdir: <main>/.git/worktrees/<name>`.

    Pass `main` as a string to fabricate a gitdir the doctor cannot resolve.
    """
    wt = tmp / name
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {main}/.git/worktrees/{name}\n", encoding="utf-8")
    return wt


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


def daily(target: Path, name: str, body: str = "log\n", mtime: float | None = None) -> Path:
    """A daily log. `mtime` is explicit wherever the gate's `has_new_daily` matters — a
    file written now carries real wall-clock time, which is far in the PAST relative to
    the fixtures' synthetic `self.now`."""
    import os

    path = target / "daily" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
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
    def _stalled(self, *, lock_age: float = 2 * 3600) -> Path:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md", mtime=self.now - 3600)  # newer than the stamp
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        # Fresh against the 6h gate, but well past the in-flight grace.
        lock(target, "claudemd-lerner", self.now - lock_age)
        return repo

    def test_a_fresh_lock_over_an_older_stamp_is_the_stall(self) -> None:
        finding = self.check(self.run_checks(self._stalled()), "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("1 pending", finding.message)
        self.assertIn("never completed", finding.message)
        # The lock time and the reopen time are what makes the finding actionable.
        self.assertIn(doctor.stamp_time(self.now - 2 * 3600), finding.message)
        self.assertIn(doctor.stamp_time(self.now - 2 * 3600 + 6 * 3600), finding.message)
        self.assertIn("scripts/update.py", finding.fix)

    def test_a_run_still_in_flight_is_not_called_a_stall(self) -> None:
        # The gate hooks write the lock before spawning and the child stamps completion
        # only at the end, so a HEALTHY live run looks exactly like the stall above. An
        # ERROR here would tell the user to delete the lock of a compile still writing.
        repo = self._stalled(lock_age=5 * 60)
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "NOTE")
        self.assertIn("still in flight", finding.message)
        self.assertEqual(
            finding.fix, "", "an in-flight run must not be offered a lock-removal fix"
        )

    def _worktree_over(self, main: Path | str, *, name: str = "wt") -> Path:
        """A worktree carrying only the install CODE — the queue state never lives here.

        Every capture hook resolves its output through `_shared/gitctx.state_home()` and
        writes daily/, state.json, the stamp and the lock into the MAIN checkout, and all
        four are gitignored, so a worktree genuinely has none of them. A fixture that put
        logs in the worktree would be testing a state production cannot reach.
        """
        wt = make_worktree(self.tmp, main, name=name)
        install(wt, "claudemd-lerner", "claudemd-lerner")
        settings_for(wt, ("claudemd-lerner", "claudemd-lerner"))
        return wt

    def test_a_worktree_reads_the_queue_from_the_main_checkout(self) -> None:
        # Run from a worktree, the doctor must report the MAIN checkout's queue. Reading
        # the worktree's own empty dirs would answer "drained — 0 pending daily logs of 0"
        # at exit 0 for a repo whose harness has stopped, and this repo's documented flow
        # (/nw-worktree → implement → ship) makes the worktree the likely place to run it.
        main = self._stalled()
        finding = self.check(
            self.run_checks(self._worktree_over(main)), "claudemd-lerner", "queue"
        )
        self.assertEqual(finding.severity, "ERROR")
        self.assertIn("1 pending", finding.message)
        self.assertIn("never completed", finding.message)
        self.assertIn(str(main), finding.message, "say which checkout was read")
        # The cure has to act on the checkout that was read. A bare relative command runs
        # against the worktree's own empty install dir and reports "nothing to do".
        self.assertIn(
            str(main),
            finding.fix,
            "a fix rooted in the worktree silently no-ops and contradicts the finding",
        )

    def test_an_unresolvable_main_checkout_is_never_called_drained(self) -> None:
        wt = self._worktree_over("/nowhere/that/exists", name="orphan-wt")
        finding = self.check(self.run_checks(wt), "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "NOTE")
        self.assertNotIn(
            "drained",
            finding.message,
            "a queue that could not be read must never be reported as empty",
        )
        self.assertIn("main checkout", finding.message)
        self.assertIn("--repo", finding.fix)

    def test_an_eligible_gate_warns_rather_than_errors(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md", mtime=self.now - 3600)
        # An earlier log really was ingested, so the stamp is trustworthy and the gate
        # condition is what is under test here — not "this engine never ran".
        state(target, "claudemd-lerner", {"2026-07-01.md": {"hash": "cafe"}})
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)  # no lock at all
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("eligible", finding.message)

    def test_a_stamp_newer_than_every_log_means_the_gate_never_fires(self) -> None:
        # The gate's first input is `newest daily mtime > last_ts`, not "is there work
        # left". A run that stamped completion without ingesting its logs leaves the
        # queue full AND the gate permanently shut: nothing spawns again until capture
        # writes another log. Reporting that as "eligible" or "reopens at X" would call
        # the exact went-quiet state this command exists to surface self-healing.
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md", mtime=self.now - 7 * DAY)
        state(target, "claudemd-lerner", {"2026-07-01.md": {"hash": "cafe"}})
        stamp(target, "claudemd-lerner", self.now - 60)  # stamped AFTER the newest log
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("will NOT spawn on its own", finding.message)
        self.assertNotIn("eligible", finding.message)
        self.assertNotIn("reopens", finding.message)
        self.assertIn("scripts/update.py", finding.fix)

    def test_a_missing_state_file_makes_every_log_pending(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        for name in ("2026-07-02.md", "2026-07-23.md", "2026-08-20.md"):
            daily(target, name, mtime=self.now - 3600)
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertIn("3 pending", finding.message)
        self.assertIn("no scripts/state.json", finding.message)

    def test_a_log_edited_after_ingestion_counts_as_pending(self) -> None:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        log = daily(target, "2026-08-20.md", "original\n", mtime=self.now - 3600)
        state(target, "claudemd-lerner", {"2026-08-20.md": {"hash": doctor.file_hash(log)}})
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        self.assertEqual(
            self.check(self.run_checks(repo), "claudemd-lerner", "queue").severity, "OK"
        )

        daily(target, "2026-08-20.md", "edited since it was ingested\n", mtime=self.now - 1800)
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertIn("1 pending", finding.message)


class MainCheckoutRootTests(unittest.TestCase):
    """Resolving the main checkout from a worktree's `.git` file, process-free.

    Every ambiguous layout must answer None: the caller then says it could not look,
    which is the only honest alternative to reading the wrong directory.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_resolves_a_real_linked_worktree(self) -> None:
        main = make_repo(self.tmp)
        wt = make_worktree(self.tmp, main)
        self.assertEqual(doctor.main_checkout_root(wt), main)

    def test_a_main_checkout_has_no_gitdir_file(self) -> None:
        self.assertIsNone(doctor.main_checkout_root(make_repo(self.tmp)))

    def test_a_relative_gitdir_is_not_guessed_at(self) -> None:
        wt = self.tmp / "wt"
        wt.mkdir()
        (wt / ".git").write_text("gitdir: ../main/.git/worktrees/wt\n", encoding="utf-8")
        self.assertIsNone(doctor.main_checkout_root(wt))

    def test_an_unexpected_layout_is_not_guessed_at(self) -> None:
        wt = self.tmp / "wt2"
        wt.mkdir()
        (wt / ".git").write_text("gitdir: /some/other/place\n", encoding="utf-8")
        self.assertIsNone(doctor.main_checkout_root(wt))


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
        # would go looking for files that are not there. All four shipped engines now
        # have an installer, so the branch is exercised through a synthetic one: it is
        # the guard for the next engine that arrives before its install.py.
        repo = make_repo(self.tmp)
        install(repo, "stack-compiler", "stack-base")
        settings_for(repo, ("stack-compiler", "stack-base"))
        target = repo / "stack-base" / "_shared" / "gitctx.py"
        target.write_text(target.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")
        engine = replace(probe.ENGINES["stack-compiler"], install_skill=None)
        installed = probe.Install("stack-compiler", "stack-base", "both", [], True)
        finding = doctor.check_shared(repo, PLUGIN_ROOT, installed, engine)[0]
        self.assertEqual(finding.severity, "WARN")
        self.assertNotIn("payload", finding.fix)
        self.assertIn("engines/_shared", finding.fix)

    def test_a_drifted_shared_on_an_installable_engine_names_its_installer(self) -> None:
        repo = make_repo(self.tmp)
        install(repo, "stack-compiler", "stack-base")
        settings_for(repo, ("stack-compiler", "stack-base"))
        target = repo / "stack-base" / "_shared" / "gitctx.py"
        target.write_text(target.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")
        finding = self.check(self.run_checks(repo), "stack-compiler", "shared")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("/neurawork-cc-harness:stack-compiler", finding.fix)


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


class PrpStoreTests(DoctorTestCase):
    """How the artifact store is wired — the wiring a silent gate depends on."""

    def setUp(self) -> None:
        super().setUp()
        import os

        self.prp_home = self.tmp / "prp-home"
        previous = os.environ.get("PRP_HOME")
        os.environ["PRP_HOME"] = str(self.prp_home)
        self.addCleanup(lambda: os.environ.__setitem__("PRP_HOME", previous)
                        if previous is not None else os.environ.pop("PRP_HOME", None))

    def _gated_repo(self, *, name: str = "repo") -> Path:
        repo = make_repo(self.tmp, name=name)
        install(repo, "stack-compiler", "stack-base")
        settings_for(repo, ("stack-compiler", "stack-base"))
        return repo

    def _link(self, repo: Path, target: Path) -> Path:
        link = self.prp_home / doctor.key_for_root(repo.resolve())
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target, target_is_directory=True)
        return link

    def _set_env(self, repo: Path, value: str) -> None:
        path = repo / ".claude" / "settings.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("env", {})["PRP_HOME"] = value
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def test_a_repo_with_no_gate_engine_has_no_store_to_wire(self) -> None:
        repo = make_repo(self.tmp)
        install(repo, "knowledge-compiler", "knowledge-base")
        settings_for(repo, ("knowledge-compiler", "knowledge-base"))
        self.assertEqual(
            [f for f in self.run_checks(repo) if f.check == "prp-store"], [])

    def test_a_linked_store_is_ok(self) -> None:
        repo = self._gated_repo()
        (repo / ".claude" / "PRPs").mkdir(parents=True)
        self._link(repo, repo / ".claude" / "PRPs")
        finding = self.check(self.run_checks(repo), doctor.REPO, "prp-store")
        self.assertEqual(finding.severity, "OK")
        self.assertIn(str(repo / ".claude" / "PRPs"), finding.message)

    def test_no_wiring_at_all_warns_that_documents_land_outside_the_repo(self) -> None:
        finding = self.check(self.run_checks(self._gated_repo()), doctor.REPO, "prp-store")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("no gate sees it", finding.message)

    def test_prp_home_alone_is_the_older_wiring_not_a_fault(self) -> None:
        repo = self._gated_repo()
        self._set_env(repo, ".claude/PRPs")
        finding = self.check(self.run_checks(repo), doctor.REPO, "prp-store")
        self.assertEqual(finding.severity, "NOTE")
        self.assertIn("env.PRP_HOME", finding.message)

    def test_both_wirings_say_which_one_wins(self) -> None:
        repo = self._gated_repo()
        (repo / ".claude" / "PRPs").mkdir(parents=True)
        self._link(repo, repo / ".claude" / "PRPs")
        self._set_env(repo, ".claude/PRPs")
        finding = self.check(self.run_checks(repo), doctor.REPO, "prp-store")
        self.assertEqual(finding.severity, "NOTE")
        self.assertIn("PRP_HOME wins", finding.message)

    def test_a_link_pointing_somewhere_else_names_both_paths(self) -> None:
        repo = self._gated_repo()
        elsewhere = self.tmp / "other-store"
        elsewhere.mkdir()
        self._link(repo, elsewhere)
        finding = self.check(self.run_checks(repo), doctor.REPO, "prp-store")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn(str(elsewhere), finding.message)
        self.assertIn(str(repo / ".claude" / "PRPs"), finding.message)

    def test_a_worktree_only_document_is_a_split_store(self) -> None:
        main = self._gated_repo(name="main")
        (main / ".claude" / "PRPs" / "plans").mkdir(parents=True)
        self._link(main, main / ".claude" / "PRPs")
        wt = make_worktree(self.tmp, main, name="wt")
        install(wt, "stack-compiler", "stack-base")
        settings_for(wt, ("stack-compiler", "stack-base"))
        stranded = wt / ".claude" / "PRPs" / "plans" / "feature.plan.md"
        stranded.parent.mkdir(parents=True)
        stranded.write_text("plan\n", encoding="utf-8")

        split = [f for f in self.run_checks(wt)
                 if f.check == "prp-store" and "split store" in f.message]
        self.assertEqual(len(split), 1, "the worktree-only document was not reported")
        self.assertEqual(split[0].severity, "WARN")
        self.assertIn("plans/feature.plan.md", split[0].message)


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
