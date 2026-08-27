"""Plugin currency, the never-ran queue verdict and the credentials three-state.

Every fixture is a temp `plugins/` root — never the live `~/.claude`, whose contents
change the moment the operator runs `/plugin update` (`test_harness_probe.py:8-9`).
The doctor reads outside the repo for the only time here, so the read-only guard is
re-asserted against the new path as well. No network, no LLM.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import doctor  # noqa: E402
import harness_probe as probe  # noqa: E402

from test_doctor import (  # noqa: E402
    DAY,
    DoctorTestCase,
    daily,
    install,
    make_repo,
    settings_for,
    stamp,
    state,
)

MARKET = "neurawork-harness"


def set_env(case: unittest.TestCase, **values: str | None) -> None:
    """Set (or clear, with None) env vars for one test and restore them afterwards."""
    previous = {key: os.environ.get(key) for key in values}

    def restore() -> None:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    case.addCleanup(restore)
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class PluginFixture(DoctorTestCase):
    def plugins_root(
        self,
        *,
        installed: str | None = "0.5.0",
        available: str | None = "0.5.1",
        cached: tuple[str, ...] = (),
        installed_json: object | None = None,
        marketplace_known: bool = True,
    ) -> Path:
        """A fake `~/.claude/plugins` carrying the four artifacts the probe reads."""
        root = self.tmp / "claude" / "plugins"
        cache = root / "cache" / MARKET / probe.PLUGIN_NAME
        location = root / "marketplaces" / MARKET

        if installed_json is not None:
            write_json(root / "installed_plugins.json", installed_json)
        elif installed is not None:
            (cache / installed).mkdir(parents=True, exist_ok=True)
            write_json(root / "installed_plugins.json", {
                "version": 2,
                "plugins": {
                    f"{probe.PLUGIN_NAME}@{MARKET}": [{
                        "scope": "user",
                        "installPath": str(cache / installed),
                        "version": installed,
                        "gitCommitSha": "0" * 40,
                    }],
                },
            })
        else:
            write_json(root / "installed_plugins.json", {"version": 2, "plugins": {}})

        for name in cached:
            (cache / name).mkdir(parents=True, exist_ok=True)

        if marketplace_known:
            write_json(root / "known_marketplaces.json", {
                MARKET: {"installLocation": str(location)},
            })
        else:
            write_json(root / "known_marketplaces.json", {})

        write_json(location / ".claude-plugin" / "marketplace.json", {
            "name": MARKET,
            "plugins": [{
                "name": probe.PLUGIN_NAME,
                "source": {"source": "git-subdir", "path": "plugins/harness"},
            }],
        })
        if available is not None:
            write_json(
                location / "plugins" / "harness" / ".claude-plugin" / "plugin.json",
                {"name": probe.PLUGIN_NAME, "version": available},
            )
        return root

    def plugin_findings(self, plugins_root: Path | None) -> list[doctor.Finding]:
        """`check_plugin` against a temp config dir, so the live install is never read."""
        config_dir = (
            plugins_root.parent if plugins_root is not None else self.tmp / "no-claude"
        )
        set_env(self, CLAUDE_CONFIG_DIR=str(config_dir))
        return doctor.check_plugin(PLUGIN_ROOT)

    def named(self, findings: list[doctor.Finding], check: str) -> doctor.Finding | None:
        matches = [f for f in findings if f.check == check]
        return matches[0] if matches else None


class PluginCurrencyTests(PluginFixture):
    def test_an_older_install_than_the_marketplace_is_the_warn(self) -> None:
        findings = self.plugin_findings(self.plugins_root())
        currency = self.named(findings, "currency")
        assert currency is not None
        self.assertEqual(currency.severity, "WARN")
        self.assertIn("0.5.0", currency.message)
        self.assertIn("0.5.1", currency.message)
        self.assertIn("/plugin update", currency.fix)
        self.assertIn("/reload-plugins", currency.fix)

    def test_a_matching_install_is_quiet(self) -> None:
        findings = self.plugin_findings(self.plugins_root(installed="0.5.1"))
        currency = self.named(findings, "currency")
        assert currency is not None
        self.assertEqual(currency.severity, "OK")
        self.assertIn("0.5.1", currency.message)

    def test_an_install_ahead_of_the_clone_is_only_a_note(self) -> None:
        # The harness's own repo bumps the source before the clone is refreshed; a WARN
        # here would fail the exit code on every developer machine.
        findings = self.plugin_findings(self.plugins_root(installed="0.6.0"))
        currency = self.named(findings, "currency")
        assert currency is not None
        self.assertEqual(currency.severity, "NOTE")
        self.assertIn("AHEAD", currency.message)

    def test_no_plugins_dir_yields_exactly_one_note(self) -> None:
        # A CI checkout installed the plugin some other way, or not at all. The rest of
        # the report must still be produced.
        findings = self.plugin_findings(None)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "NOTE")
        self.assertNotIn("WARN", [f.severity for f in findings])

    def test_an_unparsable_registry_is_a_note_not_a_crash(self) -> None:
        root = self.plugins_root()
        (root / "installed_plugins.json").write_text("{ this is not json", encoding="utf-8")
        findings = self.plugin_findings(root)
        currency = self.named(findings, "currency")
        assert currency is not None
        self.assertEqual(currency.severity, "NOTE")
        self.assertIn("installed_plugins.json", currency.message)

    def test_an_unknown_marketplace_names_the_artifact_that_was_missing(self) -> None:
        findings = self.plugin_findings(self.plugins_root(marketplace_known=False))
        currency = self.named(findings, "currency")
        assert currency is not None
        self.assertEqual(currency.severity, "NOTE")
        self.assertIn("known_marketplaces.json", currency.message)

    def test_leftover_cache_versions_are_listed_without_a_removal_command(self) -> None:
        findings = self.plugin_findings(
            self.plugins_root(cached=("0.1.0", "0.3.1"))
        )
        cache = self.named(findings, "cache")
        assert cache is not None
        self.assertEqual(cache.severity, "NOTE")
        self.assertIn("0.1.0", cache.message)
        self.assertIn("0.3.1", cache.message)
        self.assertNotIn("0.5.0", cache.message, "the installed version is not leftover")
        self.assertEqual(cache.fix, "", "the doctor reports; it never removes")

    def test_no_leftovers_produces_no_cache_finding(self) -> None:
        self.assertIsNone(self.named(self.plugin_findings(self.plugins_root()), "cache"))

    def test_the_user_scope_install_wins_over_another_scope(self) -> None:
        root = self.plugins_root()
        path = root / "cache" / MARKET / probe.PLUGIN_NAME / "0.5.0"
        write_json(root / "installed_plugins.json", {
            "version": 2,
            "plugins": {
                f"{probe.PLUGIN_NAME}@{MARKET}": [
                    {"scope": "project", "installPath": str(path), "version": "0.2.0"},
                    {"scope": "user", "installPath": str(path), "version": "0.5.0"},
                ],
            },
        })
        currency = self.named(self.plugin_findings(root), "currency")
        assert currency is not None
        self.assertIn("0.5.0", currency.message)
        self.assertNotIn("0.2.0", currency.message)

    def test_a_running_root_other_than_the_install_path_is_noted(self) -> None:
        # The doctor here always runs from the repo checkout, never from the cache dir
        # the fixture names — the exact "I updated but the session still runs the old
        # cache" shape.
        running = self.named(self.plugin_findings(self.plugins_root()), "running")
        assert running is not None
        self.assertEqual(running.severity, "NOTE")
        self.assertIn(str(PLUGIN_ROOT), running.message)
        self.assertIn("/reload-plugins", running.fix)

    def test_reinstall_is_only_flagged_when_behind_and_an_engine_drifted(self) -> None:
        root = self.plugins_root()
        clone = root / "marketplaces" / MARKET / "plugins" / "harness"
        for engine in probe.ENGINES:
            path = clone / "engines" / engine / "VERSION"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("99\n", encoding="utf-8")
        reinstall = self.named(self.plugin_findings(root), "reinstall")
        assert reinstall is not None
        self.assertEqual(reinstall.severity, "NOTE")
        self.assertIn("claudemd-lerner", reinstall.message)

    def test_a_current_plugin_never_gets_the_reinstall_note(self) -> None:
        root = self.plugins_root(installed="0.5.1")
        clone = root / "marketplaces" / MARKET / "plugins" / "harness"
        path = clone / "engines" / "claudemd-lerner" / "VERSION"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("99\n", encoding="utf-8")
        self.assertIsNone(self.named(self.plugin_findings(root), "reinstall"))

    def test_the_findings_survive_json_rendering(self) -> None:
        findings = self.plugin_findings(self.plugins_root())
        payload = json.loads(doctor.render_json(Path("/repo"), PLUGIN_ROOT, findings))
        self.assertEqual(
            [f["check"] for f in payload["findings"] if f["engine"] == doctor.PLUGIN],
            [f.check for f in findings],
        )
        self.assertEqual(payload["worst"], "WARN")

    def test_the_plugin_section_renders_as_its_own_group(self) -> None:
        text = doctor.render_text(
            Path("/repo"), PLUGIN_ROOT, self.plugin_findings(self.plugins_root())
        )
        self.assertIn("\nplugin\n", text)


class NeverRanQueueTests(DoctorTestCase):
    """A completion stamp with no ingest state is the one shape that proves a run
    never did any work — the exact state a detached, output-discarding hook leaves."""

    def _staged(self, *, with_state: bool) -> Path:
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md", mtime=self.now - 3600)
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        if with_state:
            state(target, "claudemd-lerner", {"2026-07-01.md": {"hash": "cafe"}})
        return repo

    def test_a_stamp_with_no_ingest_state_is_a_warn_naming_the_state_file(self) -> None:
        findings = self.run_checks(self._staged(with_state=False))
        finding = self.check(findings, "claudemd-lerner", "queue")
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("scripts/state.json", finding.message)
        self.assertIn("scripts/last-update.json", finding.message)
        self.assertIn("scripts/update.py", finding.fix)
        self.assertEqual(doctor.exit_code(findings), 1)
        self.assertEqual(
            len([f for f in findings if f.engine == "claudemd-lerner" and f.check == "queue"]),
            1,
            "exactly one queue verdict per engine",
        )

    def test_a_fresh_install_with_neither_file_keeps_its_lower_severity(self) -> None:
        # No stamp at all is a queue that has simply never been drained yet — the gate
        # is eligible and will spawn. Calling that "the engine never ran" would make
        # every fresh install loud.
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md", mtime=self.now - 3600)
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertIn("eligible", finding.message)
        self.assertNotIn("does not exist", finding.message)

    def test_an_ingesting_run_is_judged_by_the_gate_as_before(self) -> None:
        finding = self.check(
            self.run_checks(self._staged(with_state=True)), "claudemd-lerner", "queue"
        )
        self.assertIn("eligible", finding.message)

    def test_a_run_still_in_flight_outranks_the_never_ran_verdict(self) -> None:
        # A live run has not written state.json yet either. "A run is stuck/running
        # right now" is both truer and more actionable, so the lock branches stay first.
        repo = make_repo(self.tmp)
        target = install(repo, "claudemd-lerner", "claudemd-lerner")
        settings_for(repo, ("claudemd-lerner", "claudemd-lerner"))
        daily(target, "2026-08-20.md", mtime=self.now - 3600)
        stamp(target, "claudemd-lerner", self.now - 60 * DAY)
        from test_doctor import lock

        lock(target, "claudemd-lerner", self.now - 5 * 60)
        finding = self.check(self.run_checks(repo), "claudemd-lerner", "queue")
        self.assertIn("still in flight", finding.message)


class CredentialsTests(DoctorTestCase):
    def _credentials(self, findings: list[doctor.Finding]) -> doctor.Finding:
        return self.check(findings, doctor.REPO, "credentials")

    def _config_dir(self, *, with_login: bool) -> Path:
        config = self.tmp / "claude-config"
        config.mkdir(exist_ok=True)
        if with_login:
            (config / ".credentials.json").write_text(
                '{"claudeAiOauth": {"accessToken": "sk-fixture-SECRET-VALUE"}}',
                encoding="utf-8",
            )
        return config

    def _run(self, *, with_login: bool, api_key: str | None) -> list[doctor.Finding]:
        repo = make_repo(self.tmp)
        settings_for(repo)
        set_env(
            self,
            CLAUDE_CONFIG_DIR=str(self._config_dir(with_login=with_login)),
            CLAUDE_CODE_OAUTH_TOKEN=None,
            ANTHROPIC_API_KEY=api_key,
        )
        return self.run_checks(repo)

    def test_an_api_key_is_ok(self) -> None:
        self.assertEqual(self._credentials(self._run(with_login=True, api_key="sk-x")).severity,
                         "OK")

    def test_a_subscription_login_without_a_key_is_a_note(self) -> None:
        finding = self._credentials(self._run(with_login=True, api_key=None))
        self.assertEqual(finding.severity, "NOTE")
        self.assertIn("fall back", finding.message)
        self.assertNotIn("cannot run", finding.message)
        self.assertIn("ANTHROPIC_API_KEY", finding.fix)

    def test_no_auth_at_all_stays_a_warn(self) -> None:
        finding = self._credentials(self._run(with_login=False, api_key=None))
        self.assertEqual(finding.severity, "WARN")
        self.assertIn("cannot run", finding.message)

    def test_the_report_never_carries_the_credentials_contents(self) -> None:
        findings = self._run(with_login=True, api_key=None)
        for render in (doctor.render_text, doctor.render_json):
            with self.subTest(render=render.__name__):
                output = render(Path("/repo"), PLUGIN_ROOT, findings)
                self.assertNotIn("sk-fixture-SECRET-VALUE", output)
                self.assertNotIn("claudeAiOauth", output)


class ReadOnlyAcrossThePluginsDirTests(PluginFixture):
    def test_reading_the_plugins_dir_changes_nothing_in_it(self) -> None:
        root = self.plugins_root(cached=("0.1.0",))

        def snapshot() -> dict[str, tuple[int, float]]:
            return {
                str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime)
                for p in sorted(root.rglob("*")) if p.is_file()
            }

        before = snapshot()
        self.plugin_findings(root)
        self.assertEqual(snapshot(), before)

    def test_the_probe_source_spawns_nothing_either(self) -> None:
        # The doctor's own guard (`test_doctor.py`) cannot see the module it delegates
        # the new outside-the-repo reads to.
        source = (PLUGIN_ROOT / "scripts" / "harness_probe.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "Popen", "mkdir", "write_text", "os.remove", "unlink"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
