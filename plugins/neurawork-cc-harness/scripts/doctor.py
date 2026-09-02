#!/usr/bin/env python3
"""Read-only health report for a repo's neurawork-cc-harness installs.

    python3 scripts/doctor.py [--repo <path>] [--json]

The engines run as detached, fire-and-forget hooks whose output goes nowhere, so a
compile or update that never finishes is invisible: the capture side keeps queueing
daily logs while the gate stays shut behind a lock nobody cleared. This answers, for
one repo: which engines are installed and where, whether each matches the shipped
version, whether its files and wiring are intact, and whether its queue is draining
— each problem paired with the command that fixes it.

Runs under system python3 with no `uv`, no venv and no API key, because half the
states it diagnoses would stop a `uv run` entry point from starting at all. It
resolves the repo root and worktree status from the layout of `.git` alone (a linked
worktree has a `.git` FILE, the main checkout a directory), so it needs no git
process either.

Read-only is the contract, not a convention: this module opens no file for output,
creates no directory, touches no lock and starts no process. `tests/test_doctor.py`
pins that mechanically, so a future edit that reaches for a repair cannot land here
— every finding names the command a human runs instead.

Findings are OK / NOTE / WARN / ERROR; the exit code is the worst severity
(0 / 0 / 1 / 2) and `--json` emits the same records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness_probe as probe  # noqa: E402

if str(Path(__file__).resolve().parents[1] / "engines") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engines"))

# The store key and its prefix rule have ONE owner — the module the installers wire the
# store with. Re-deriving either here would let the doctor look in a place no install
# ever writes. `link_path` takes an already-resolved main checkout, so importing it
# costs the doctor neither a git process nor a write.
from _shared.prp_store import STORE_SUBPATH, link_path

SEVERITIES = ("OK", "NOTE", "WARN", "ERROR")
RANK = {name: index for index, name in enumerate(SEVERITIES)}
EXIT = {"OK": 0, "NOTE": 0, "WARN": 1, "ERROR": 2}

# Findings that belong to the repo rather than to any one engine.
REPO = "-"

# Findings about the INSTALLED PLUGIN itself, which is neither the repo nor an engine:
# its own section, so "is what I am running current" reads separately from "is this
# repo's install intact".
PLUGIN = "plugin"

# How long a fresh lock over an older completion stamp reads as "still running" rather
# than "stalled". The gate hooks write the lock BEFORE spawning the child, and the child
# stamps its completion only at the very end, so that state is ALSO what a perfectly
# healthy run looks like for its whole duration. Without a grace the doctor would call
# every live compile a stall — and its fix, removing the lock, would start a second run
# writing the same state.json and the same output files as the one still going.
IN_FLIGHT_GRACE = 30 * 60


@dataclass
class Finding:
    severity: str
    engine: str
    check: str
    message: str
    fix: str = ""


# ── Small readers (none of them raise) ─────────────────────────────────

def file_hash(path: Path) -> str | None:
    """First 16 hex chars of a file's SHA-256 — the payload's own `file_hash`.

    Recomputed rather than trusted so a daily log edited after it was ingested
    counts as pending again, exactly as the compiler's own change detection does.
    """
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def read_json(path: Path) -> tuple[object | None, str | None]:
    """``(data, error)``. A missing file is ``(None, None)``, not an error."""
    if not path.exists():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def stamp_time(ts: float) -> str:
    """Local wall-clock, minute precision — a lock time a human can act on."""
    try:
        return datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "unknown"


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def repo_root_from(start: Path) -> Path | None:
    """The nearest ancestor holding a `.git` entry, or None."""
    try:
        current = Path(start).resolve()
    except OSError:
        return None
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def main_checkout_root(repo_root: Path) -> Path | None:
    """The MAIN checkout behind a linked worktree, read from its `.git` FILE.

    The file holds ``gitdir: <main>/.git/worktrees/<name>``, so the main working tree is
    three levels up. Every unexpected shape — a relative gitdir, a layout that is not
    ``.git/worktrees/<name>``, a root that is not a directory — answers None, and the
    caller then says it could not look. Guessing here would point the queue check at the
    wrong repository, which is worse than admitting the gap.

    This exists because the queue state is not where the doctor is standing: every capture
    hook resolves its output through ``_shared/gitctx.state_home()`` and writes the daily
    log, ``state.json``, the completion stamp and the lock into the MAIN checkout. A
    worktree holds none of them — they are gitignored too — so reading the queue out of a
    worktree finds an empty directory and calls a stalled harness drained.
    """
    try:
        text = (repo_root / ".git").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text.startswith("gitdir:"):
        return None
    gitdir = Path(text.split(":", 1)[1].strip())
    if not gitdir.is_absolute():
        return None
    if gitdir.parent.name != "worktrees" or gitdir.parent.parent.name != ".git":
        return None
    root = gitdir.parent.parent.parent
    return root if root.is_dir() else None


def in_worktree(repo_root: Path) -> bool:
    """True in a linked worktree: git puts a `.git` FILE there, not a directory."""
    return (repo_root / ".git").is_file()


def worst(findings: list[Finding]) -> str:
    return max((f.severity for f in findings), key=lambda s: RANK.get(s, 0), default="OK")


def exit_code(findings: list[Finding]) -> int:
    return EXIT[worst(findings)]


# ── Checks ─────────────────────────────────────────────────────────────

def _install_fix(engine: probe.Engine) -> str:
    if engine.install_skill:
        return f"re-run /neurawork-cc-harness:{engine.install_skill} (ADOPT — non-destructive)"
    return (
        f"{engine.name} ships no installer: mirror "
        f"plugins/neurawork-cc-harness/engines/{engine.name}/payload/ by hand"
    )


def check_environment(
    repo_root: Path, settings_error: str | None, worktree: bool
) -> list[Finding]:
    findings = [
        Finding(
            "ERROR", REPO, "settings",
            f".claude/settings.json does not parse ({settings_error}) — every hook in it "
            "is dead and wiring below is read from the directory scan only",
            "fix the JSON syntax, then re-run the installers to re-merge the hooks",
        )
        if settings_error else
        Finding("OK", REPO, "settings", ".claude/settings.json parses")
    ]

    if shutil.which("uv"):
        findings.append(Finding("OK", REPO, "uv", "uv is on PATH"))
    else:
        findings.append(Finding(
            "WARN", REPO, "uv",
            "uv is not on PATH — every harness hook is a `uv run`, so none of them run",
            "install uv: https://docs.astral.sh/uv/getting-started/installation/",
        ))

    version = ".".join(str(p) for p in sys.version_info[:3])
    if sys.version_info >= (3, 12):
        findings.append(Finding("OK", REPO, "python", f"python3 {version}"))
    else:
        findings.append(Finding(
            "WARN", REPO, "python", f"python3 {version} is below the required 3.12",
            "install python 3.12 or newer",
        ))

    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        findings.append(Finding("OK", REPO, "credentials", "an API credential is set"))
    elif (probe.claude_config_dir() / ".credentials.json").exists():
        # Existence only — the contents are never read, parsed or rendered. The engines
        # call the SDK, which spawns the bundled Claude Code CLI, which falls back to
        # this subscription login: "cannot run" would be false here. But subscription
        # credentials are not sanctioned for third-party plugin use (root CLAUDE.md, and
        # the knowledge base's connection article on why the SDK forces an API key), so
        # the fix line still asks for one.
        findings.append(Finding(
            "NOTE", REPO, "credentials",
            "neither ANTHROPIC_API_KEY nor CLAUDE_CODE_OAUTH_TOKEN is set — the engines "
            "will fall back to the bundled Claude Code CLI's subscription login, which is "
            "not sanctioned for third-party plugin use",
            "export ANTHROPIC_API_KEY=... (or CLAUDE_CODE_OAUTH_TOKEN)",
        ))
    else:
        findings.append(Finding(
            "WARN", REPO, "credentials",
            "neither ANTHROPIC_API_KEY nor CLAUDE_CODE_OAUTH_TOKEN is set and there is no "
            "subscription login either — capture keeps working, but compile / update / "
            "extract cannot run",
            "export ANTHROPIC_API_KEY=... (or CLAUDE_CODE_OAUTH_TOKEN)",
        ))

    if worktree:
        findings.append(Finding(
            "NOTE", REPO, "worktree",
            f"{repo_root} is a linked worktree — capture redirects into the main checkout "
            "and both compile gates are suppressed here by design, so the queue below is "
            "read from the main checkout, not from here",
        ))
    return findings


def check_plugin(plugin_root: Path) -> list[Finding]:
    """Is the installed plugin the newest one available, and is it what is running?

    Offline and read-only: every answer comes from JSON Claude Code already keeps on
    disk, including a local clone of the marketplace. Reads outside the repo for the
    only time — bounded to `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/`.
    """
    state = probe.probe_plugin(plugin_root)

    if state.plugins_dir is None:
        return [Finding(
            "NOTE", PLUGIN, "currency",
            f"plugin currency was not inspectable ({'; '.join(state.notes)}) — this run "
            "says nothing about whether the installed plugin is the newest one",
        )]

    findings: list[Finding] = []
    verdict = probe.compare(state.installed_version, state.available_version)
    if verdict == "same":
        findings.append(Finding(
            "OK", PLUGIN, "currency",
            f"installed {state.installed_version} matches the {state.marketplace} "
            "marketplace",
        ))
    elif verdict == "behind":
        findings.append(Finding(
            "WARN", PLUGIN, "currency",
            f"installed {state.installed_version} is behind the {state.marketplace} "
            f"marketplace's {state.available_version} — every fix shipped since then is "
            "stranded in the clone",
            f"/plugin update {probe.PLUGIN_NAME}, then /reload-plugins",
        ))
    elif verdict == "ahead":
        findings.append(Finding(
            "NOTE", PLUGIN, "currency",
            f"installed {state.installed_version} is AHEAD of the {state.marketplace} "
            f"marketplace's {state.available_version} — normal in the harness's own repo, "
            "where the source is bumped before the clone is refreshed",
        ))
    else:
        detail = "; ".join(state.notes) or (
            f"installed {state.installed_version!r} and available "
            f"{state.available_version!r} are not comparable"
        )
        findings.append(Finding(
            "NOTE", PLUGIN, "currency",
            f"cannot tell whether the plugin is current ({detail})",
        ))

    running = Path(plugin_root).resolve()
    if state.install_path is not None and running != state.install_path.resolve():
        findings.append(Finding(
            "NOTE", PLUGIN, "running",
            f"this doctor ran from {running} (version {state.running_version}), not from "
            f"the installed {state.install_path} (version {state.installed_version}) — a "
            "session started before an update keeps running the older cache",
            "restart the session, or /reload-plugins",
        ))

    if state.other_cached:
        findings.append(Finding(
            "NOTE", PLUGIN, "cache",
            f"{plural(len(state.other_cached), 'other version')} left in the plugin cache: "
            f"{', '.join(state.other_cached)} — inert, listed so the disk use is not a "
            "mystery",
        ))

    if verdict == "behind":
        drifted = probe.engine_version_drift(plugin_root, state)
        if drifted:
            findings.append(Finding(
                "NOTE", PLUGIN, "reinstall",
                "re-running an install skill now would still install the running "
                f"plugin's older payload ({', '.join(drifted)}) — update the plugin first, "
                "then re-install",
                f"/plugin update {probe.PLUGIN_NAME}, /reload-plugins, then the install skill",
            ))
    return findings


def check_discovery(install: probe.Install | None, engine: probe.Engine) -> list[Finding]:
    if install is None:
        return [Finding("NOTE", engine.name, "discovery", "not installed in this repo")]
    dirname = install.dirname
    if install.found_by == "dir":
        return [Finding(
            "ERROR", engine.name, "discovery",
            f"{dirname}/ is installed but not wired — no hook in .claude/settings.json "
            f"names it, so it never fires",
            _install_fix(engine),
        )]
    if install.found_by == "hook":
        return [Finding(
            "ERROR", engine.name, "discovery",
            f"orphaned hook — .claude/settings.json runs {dirname}/ but the install is "
            "missing or incomplete, so it fails at every session start",
            f"{_install_fix(engine)}, or remove the hook from .claude/settings.json",
        )]
    return [Finding(
        "OK", engine.name, "discovery", f"{dirname}/ (hook and directory signature agree)"
    )]


def check_wiring(install: probe.Install, engine: probe.Engine) -> list[Finding]:
    if not install.missing_events:
        return [Finding(
            "OK", engine.name, "wiring",
            f"all {plural(len(engine.hooks), 'hook')} registered "
            f"({', '.join(sorted(engine.hooks))})",
        )]
    return [Finding(
        "ERROR", engine.name, "wiring",
        f"hooks missing at {', '.join(install.missing_events)} — that part of the engine "
        "never runs",
        _install_fix(engine),
    )]


def check_version(
    repo_root: Path, plugin_root: Path, install: probe.Install, engine: probe.Engine
) -> list[Finding]:
    target = repo_root / str(install.dirname)
    installed = probe.read_version(target / "VERSION")
    shipped = probe.read_version(plugin_root / "engines" / engine.name / "VERSION")
    verdict = probe.compare(installed, shipped)
    if verdict == "same":
        return [Finding("OK", engine.name, "version", f"version {installed} (current)")]
    if verdict == "behind":
        return [Finding(
            "WARN", engine.name, "version",
            f"installed {installed} is behind the shipped {shipped}",
            _install_fix(engine),
        )]
    if verdict == "ahead":
        return [Finding(
            "WARN", engine.name, "version",
            f"installed {installed} is AHEAD of the shipped {shipped} — the repo carries "
            "code the plugin does not ship",
            "update the plugin, or check whether the install was edited in place",
        )]
    return [Finding(
        "WARN", engine.name, "version",
        f"cannot compare versions (installed {installed!r}, shipped {shipped!r})",
        f"check {install.dirname}/VERSION",
    )]


def check_shared(
    repo_root: Path, plugin_root: Path, install: probe.Install, engine: probe.Engine
) -> list[Finding]:
    """`engines/_shared/` is the single source of truth; every install refreshes it."""
    target = repo_root / str(install.dirname) / "_shared"
    drifted: list[str] = []
    for name in probe.shared_files(plugin_root):
        source = plugin_root / "engines" / "_shared" / name
        copy = target / name
        try:
            if not copy.exists() or copy.read_bytes() != source.read_bytes():
                drifted.append(name)
        except OSError:
            drifted.append(name)
    if not drifted:
        return [Finding("OK", engine.name, "shared", "_shared/ matches the plugin")]
    # NOT _install_fix: `_shared/` is deliberately absent from every `payload/` (the
    # installer copies it straight from engines/_shared/), so telling an installer-less
    # engine to "mirror the payload" would name files that are not there.
    fix = _install_fix(engine) if engine.install_skill else (
        f"copy plugins/neurawork-cc-harness/engines/_shared/*.py over "
        f"{install.dirname}/_shared/"
    )
    return [Finding(
        "WARN", engine.name, "shared",
        f"_shared/ has drifted from the plugin: {', '.join(drifted)}",
        fix,
    )]


def check_integrity(
    repo_root: Path, plugin_root: Path, install: probe.Install, engine: probe.Engine
) -> list[Finding]:
    target = repo_root / str(install.dirname)
    findings: list[Finding] = []

    expected = probe.payload_files(plugin_root, engine.name)
    missing = [rel for rel in expected if not (target / rel).exists()]
    if missing:
        findings.append(Finding(
            "ERROR", engine.name, "integrity",
            f"{plural(len(missing), 'payload file')} missing: {', '.join(missing)}",
            _install_fix(engine),
        ))
    else:
        findings.append(Finding(
            "OK", engine.name, "integrity",
            f"all {plural(len(expected), 'payload file')} present",
        ))

    config, error = read_json(target / "config.json")
    if error:
        findings.append(Finding(
            "ERROR", engine.name, "config", f"config.json does not parse ({error})",
            f"fix the JSON in {install.dirname}/config.json",
        ))
    elif config is None:
        findings.append(Finding(
            "WARN", engine.name, "config", "config.json is missing — defaults apply",
            _install_fix(engine),
        ))

    if not (target / ".gitignore").exists():
        findings.append(Finding(
            "WARN", engine.name, "gitignore",
            ".gitignore is missing — local runtime state would be committed",
            _install_fix(engine),
        ))

    if (target / ".venv").is_dir():
        findings.append(Finding("OK", engine.name, "venv", ".venv present"))
    else:
        findings.append(Finding(
            "WARN", engine.name, "venv",
            ".venv is missing — every `uv run` hook pays a full resolve, or fails",
            f"uv sync --directory {install.dirname}",
        ))

    for rel, tracked in engine.data_dirs:
        if (target / rel).is_dir():
            findings.append(Finding("OK", engine.name, "data", f"{rel}/ present"))
        elif tracked:
            findings.append(Finding(
                "ERROR", engine.name, "data", f"{rel}/ is missing — it holds tracked output",
                _install_fix(engine),
            ))
        else:
            findings.append(Finding(
                "NOTE", engine.name, "data",
                f"{rel}/ is absent — gitignored runtime state, expected in a fresh clone "
                "or a worktree",
            ))
    return findings


def check_queue(
    queue_root: Path | None, install: probe.Install, engine: probe.Engine, now: float,
    worktree: bool,
) -> list[Finding]:
    """`queue_root` is the checkout whose queue state is authoritative — the main one, even
    when the doctor was run from a worktree. None means it could not be resolved."""
    queue = engine.queue
    if queue is None:
        return []
    if queue_root is None:
        return [Finding(
            "NOTE", engine.name, "queue",
            "the queue lives in the main checkout, which this worktree's .git file does "
            "not resolve to — it was NOT read, so this run says nothing about it",
            "re-run the doctor against the main checkout: --repo <main-checkout>",
        )]
    target = queue_root / str(install.dirname)
    if not target.is_dir():
        return [Finding(
            "NOTE", engine.name, "queue",
            f"the queue lives in {target}, which does not exist — it was NOT read, so "
            "this run says nothing about it",
            f"re-run the doctor against the checkout that holds {install.dirname}/",
        )]

    config, _ = read_json(target / "config.json")
    age_hours = queue.age_default
    if isinstance(config, dict):
        try:
            age_hours = float(config.get(queue.age_key, queue.age_default))
        except (TypeError, ValueError):
            pass
    window = age_hours * 3600

    logs = sorted((target / "daily").glob("*.md")) if (target / "daily").is_dir() else []
    state, _ = read_json(target / queue.state)
    ingested = state.get("ingested", {}) if isinstance(state, dict) else {}
    pending = [
        log for log in logs
        if not isinstance(ingested.get(log.name), dict)
        or ingested[log.name].get("hash") != file_hash(log)
    ]

    detail = f"{plural(len(pending), 'pending daily log')} of {len(logs)}"
    if not isinstance(state, dict):
        detail += f" (no {queue.state} — every log counts as pending)"
    # Say which checkout the verdict describes. Standing in a worktree, "0 pending" about
    # somewhere else is otherwise indistinguishable from "0 pending" about here.
    where = f" [read from the main checkout {queue_root}]" if worktree else ""

    # Remediation has to run where the queue IS, not where the doctor stands. From a
    # worktree a bare `uv run --directory <dir> …` resolves to the WORKTREE's own install
    # dir, whose daily/ is empty: update.py prints "Nothing to update — docs are current"
    # and exits 0, an all-clear contradicting the very finding it was offered for, while
    # the real queue is untouched. Same for the lock — the one blocking the gate lives in
    # the main checkout, so the path must be absolute.
    command = queue.command.format(dir=install.dirname)
    if worktree:
        command = f"cd {queue_root} && {command}"
    if not pending:
        return [Finding(
            "OK", engine.name, "queue",
            f"drained — 0 pending daily logs of {len(logs)}{where}",
        )]
    detail += where

    stamp_data, _ = read_json(target / queue.stamp)
    last_ts: float | None = None
    if isinstance(stamp_data, dict):
        try:
            last_ts = float(stamp_data["ts"])
        except (KeyError, TypeError, ValueError):
            last_ts = None

    lock_mtime = mtime(target / queue.lock)
    fresh_lock = lock_mtime if lock_mtime is not None and (now - lock_mtime) < window else None

    if fresh_lock is not None and (last_ts is None or last_ts < fresh_lock):
        if (now - fresh_lock) < IN_FLIGHT_GRACE:
            return [Finding(
                "NOTE", engine.name, "queue",
                f"{detail}; a run spawned at {stamp_time(fresh_lock)} is still in flight "
                "— re-run the doctor later if the lock is still here",
            )]
        return [Finding(
            "ERROR", engine.name, "queue",
            f"{detail}; a run was spawned at {stamp_time(fresh_lock)} and never completed "
            f"— the fresh lock blocks the gate until {stamp_time(fresh_lock + window)}",
            f"run it in the foreground to see the real error: {command} — then remove "
            f"{target / queue.lock}",
        )]

    # A completed run writes its ingest state BEFORE it stamps (update.py records the log
    # in state.json inside the per-log loop, and stamps only after the loop). So a stamp
    # with no state.json at all cannot have come from a run that did work — which makes
    # every stamp-based verdict below argue from a stamp that proves nothing. Checked
    # after the lock branches: a run still in flight has not written state yet either,
    # and "a run is stuck right now" is the more actionable of the two.
    if not isinstance(state, dict) and last_ts is not None:
        return [Finding(
            "WARN", engine.name, "queue",
            f"{detail}; {queue.stamp} is stamped ({stamp_time(last_ts)}) but "
            f"{queue.state} does not exist — a completed run writes its ingest state "
            "before it stamps, so either the engine failed before ingesting anything "
            "(a detached hook discards the traceback) or the stamp came from seed.py, "
            "which stamps without ingesting",
            f"run it in the foreground and read the error: {command}",
        )]

    # The gate's OWN first input, computed the way the hooks compute it: newest daily
    # mtime vs the completion stamp (session-start.py:87, cl-session-start.py:57). It is
    # NOT the same question as `pending`, which asks whether the work was done. When a run
    # stamped completion without ingesting the logs, the stamp out-dates every log and the
    # gate stops firing — the queue never drains and nothing ever spawns again. Reported
    # as "eligible" or "reopens at X" that reads as self-healing, which is the exact
    # "harness went quiet" state this command exists to surface.
    newest = max((m for m in (mtime(log) for log in logs) if m is not None), default=None)
    has_new_daily = newest is not None and (last_ts is None or newest > last_ts)
    if not has_new_daily:
        return [Finding(
            "WARN", engine.name, "queue",
            f"{detail}; the completion stamp is newer than every daily log, so the "
            "SessionStart gate will NOT spawn on its own — the queue cannot drain "
            "until capture next writes a log",
            f"run it now: {command}",
        )]

    if fresh_lock is None and (last_ts is None or (now - last_ts) >= window):
        last = f"last completed {stamp_time(last_ts)}" if last_ts else "never completed"
        return [Finding(
            "WARN", engine.name, "queue",
            f"{detail}; the gate is eligible and will spawn at the next session start "
            f"({last})",
            f"run it now: {command}",
        )]

    reopen = stamp_time((last_ts or now) + window)
    return [Finding(
        "NOTE", engine.name, "queue", f"{detail}; the gate reopens at {reopen}",
        f"run it now: {command}",
    )]


def check_catalog(repo_root: Path, install: probe.Install, engine: probe.Engine) -> list[Finding]:
    """Presence and parseability only — `stack.py gaps()` owns the deep answer."""
    target = repo_root / str(install.dirname)
    config, _ = read_json(target / "config.json")
    frameworks = config.get("frameworks", []) if isinstance(config, dict) else []
    expected = [f"{name}.json" for name in frameworks] + ["capabilities.json", "stack.json"]

    missing: list[str] = []
    broken: list[str] = []
    for name in expected:
        data, error = read_json(target / "catalog" / name)
        if error:
            broken.append(f"{name} ({error})")
        elif data is None:
            missing.append(name)

    findings: list[Finding] = []
    if broken:
        findings.append(Finding(
            "ERROR", engine.name, "catalog",
            f"{plural(len(broken), 'catalog file')} do not parse: {', '.join(broken)}",
            "re-run /neurawork-cc-harness:co-extract, then /neurawork-cc-harness:co-capabilities",
        ))
    if missing:
        findings.append(Finding(
            "WARN", engine.name, "catalog",
            f"{plural(len(missing), 'catalog file')} missing: {', '.join(missing)}",
            "run /neurawork-cc-harness:co-extract (constraints), then "
            "/neurawork-cc-harness:co-capabilities (capabilities + stack scaffold)",
        ))
    if not findings:
        findings.append(Finding(
            "OK", engine.name, "catalog",
            f"all {plural(len(expected), 'catalog file')} present and parsing",
        ))
        findings.append(Finding(
            "NOTE", engine.name, "catalog",
            "mandatory-unchosen capabilities and chosen_from drift are not checked here",
            f"uv run --directory {install.dirname} python scripts/stack.py",
        ))
    return findings


def check_prp_store(
    repo_root: Path, settings: dict, installs: dict, worktree: bool
) -> list[Finding]:
    """How prp-core's artifact store is wired, and whether a worktree split one.

    Only runs when a gate that reads the store is installed: a repo with neither
    engine has no store to wire, and a warning there would be noise.

    The two wirings are a symlink at ``<prp_home>/<key>`` into the repo (one store per
    repo, reached identically from every worktree) and a relative ``PRP_HOME`` in
    settings (per-checkout stores, one segment deeper — which both gates read since
    the store layout was added to their path filters). Neither is an error; only
    *nothing* is, because then every document lands outside the repo.
    """
    if not any(name in installs for name in ("compliance-compiler", "stack-compiler")):
        return []

    main_root = (main_checkout_root(repo_root) or repo_root) if worktree else repo_root
    target = (main_root / STORE_SUBPATH).resolve()
    link = link_path(main_root.resolve())
    env_value = (settings.get("env") or {}).get("PRP_HOME") if isinstance(
        settings.get("env"), dict) else None

    linked = os.path.islink(link) and Path(os.path.realpath(link)) == target
    fix = ("re-run /neurawork-cc-harness:stack-compiler or "
           ":compliance-compiler (ADOPT — non-destructive)")

    findings: list[Finding] = []
    if linked and env_value is None:
        findings.append(Finding(
            "OK", REPO, "prp-store", f"store linked: {link} -> {target}"))
    elif linked:
        findings.append(Finding(
            "NOTE", REPO, "prp-store",
            f"store linked ({link}) AND env.PRP_HOME={env_value!r} is set — PRP_HOME wins "
            "and the link is inert; documents land in a per-checkout store",
            "remove env.PRP_HOME from .claude/settings.json to use the shared store",
        ))
    elif env_value is not None:
        findings.append(Finding(
            "NOTE", REPO, "prp-store",
            f"store wired by env.PRP_HOME={env_value!r} — the older wiring: documents land "
            "one <slug>-<hash8> segment deeper, and each checkout keeps its own store",
            fix + " to replace it with a shared symlinked store",
        ))
    elif os.path.lexists(link):
        findings.append(Finding(
            "WARN", REPO, "prp-store",
            f"{link} does not point at this repo's store: it resolves to "
            f"{os.path.realpath(link)}, not {target}",
            f"move or remove {link}, then {fix}",
        ))
    else:
        findings.append(Finding(
            "WARN", REPO, "prp-store",
            f"store neither linked ({link} is absent) nor wired by env.PRP_HOME — every "
            "PRD and plan lands outside the repo, where no gate sees it",
            fix,
        ))

    if worktree:
        findings.extend(_check_split_store(repo_root, main_root))
    return findings


def _check_split_store(repo_root: Path, main_root: Path) -> list[Finding]:
    """A worktree that grew its own physical store holds documents nobody else sees."""
    local = repo_root / STORE_SUBPATH
    if main_root == repo_root or not local.is_dir():
        return []
    only_here = sorted(
        p.relative_to(local).as_posix()
        for p in local.rglob("*.md") if not (main_root / STORE_SUBPATH / p.relative_to(local)).exists()
    )
    if not only_here:
        return []
    return [Finding(
        "WARN", REPO, "prp-store",
        f"split store: {plural(len(only_here), 'document')} exist only in this worktree's "
        f"{local} (first: {only_here[0]})",
        f"move them into {main_root / STORE_SUBPATH} — the store the gates and every other "
        "checkout read",
    )]


def run_checks(repo_root: Path, plugin_root: Path, now: float) -> list[Finding]:
    """Every check, in report order. Never raises: a broken input is a finding."""
    repo_root = Path(repo_root)
    plugin_root = Path(plugin_root)
    settings, settings_error = probe.load_settings(repo_root)
    worktree = in_worktree(repo_root)
    # Code and wiring are checked where the doctor stands; the QUEUE is checked where the
    # capture hooks actually write it, which from a worktree is the main checkout.
    queue_root = main_checkout_root(repo_root) if worktree else repo_root

    findings = check_environment(repo_root, settings_error, worktree)
    findings.extend(check_plugin(plugin_root))
    installs = {i.engine: i for i in probe.discover(repo_root, settings)}
    findings.extend(check_prp_store(repo_root, settings, installs, worktree))

    for name, engine in probe.ENGINES.items():
        install = installs.get(name)
        findings.extend(check_discovery(install, engine))
        if install is None or not install.signature_ok:
            continue
        if install.found_by == "both":
            findings.extend(check_wiring(install, engine))
        findings.extend(check_version(repo_root, plugin_root, install, engine))
        findings.extend(check_shared(repo_root, plugin_root, install, engine))
        findings.extend(check_integrity(repo_root, plugin_root, install, engine))
        findings.extend(check_queue(queue_root, install, engine, now, worktree))
        if name == "compliance-compiler":
            findings.extend(check_catalog(repo_root, install, engine))
    return findings


# ── Report ─────────────────────────────────────────────────────────────

def render_text(repo_root: Path, plugin_root: Path, findings: list[Finding]) -> str:
    lines = [f"harness doctor — {repo_root}", f"plugin: {plugin_root}", ""]
    for engine in dict.fromkeys(f.engine for f in findings):
        lines.append("repo" if engine == REPO else engine)
        for finding in (f for f in findings if f.engine == engine):
            lines.append(f"  {finding.severity:<5} {finding.check:<10} {finding.message}")
            if finding.fix and finding.severity in ("WARN", "ERROR", "NOTE"):
                lines.append(f"        fix: {finding.fix}")
        lines.append("")

    counts = {name: sum(1 for f in findings if f.severity == name) for name in SEVERITIES}
    summary = ", ".join(f"{counts[name]} {name}" for name in SEVERITIES if counts[name])
    lines.append(f"{len(findings)} checks: {summary or '0'} — worst: {worst(findings)}")
    return "\n".join(lines)


def render_json(repo_root: Path, plugin_root: Path, findings: list[Finding]) -> str:
    return json.dumps({
        "repo": str(repo_root),
        "plugin": str(plugin_root),
        "findings": [asdict(f) for f in findings],
        "worst": worst(findings),
    }, indent=2)


def main(argv: list[str] | None = None) -> int:
    import time

    parser = argparse.ArgumentParser(description="Diagnose this repo's harness installs")
    parser.add_argument("--repo", help="Repo to inspect (default: CLAUDE_PROJECT_DIR or cwd)")
    parser.add_argument("--json", action="store_true", help="Emit the findings as JSON")
    args = parser.parse_args(argv)

    start = Path(args.repo or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    repo_root = repo_root_from(start)
    if repo_root is None:
        print(f"NOT_A_GIT_REPO — {start} is not inside a git repository")
        return 2

    plugin_root = Path(
        os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent
    )
    findings = run_checks(repo_root, plugin_root, now=time.time())
    render = render_json if args.json else render_text
    print(render(repo_root, plugin_root, findings))
    return exit_code(findings)


if __name__ == "__main__":
    raise SystemExit(main())
