"""Shared engine registry and install discovery for the harness plugin.

Runs FROM the plugin (the installed engine copies inside a target repo have no
CLAUDE_PLUGIN_ROOT and no shipped VERSION to compare against), stdlib-only, under
system python3 — half the states this exists to diagnose (`uv` missing, no `.venv`)
would stop a `uv run`-based probe from starting at all.

``scripts/doctor.py`` (the on-demand health report) imports this registry directly.
The quiet SessionStart staleness nudge cannot: ``hooks/version-check.js`` is Node, so
it keeps a transcription of the engine → hook-marker map. Before this module existed
that map lived ONLY in the nudge and had already fallen behind reality — it still
listed three engines after the fourth shipped, which is why
``tests/test_version_check_registry.py`` now fails the build when the two disagree.
Register a new engine here first; the guard will point at the other side.

Discovery deliberately merges TWO sources, because their disagreement is the
finding: a hook command in ``.claude/settings.json`` says where an engine was
wired, and a signature-file scan says where one is actually installed. A dir with
no hook never fires; a hook with no dir errors at every session start.

Nothing here raises. Unreadable input yields ``None`` or an empty result and the
caller turns that into a finding.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN_NAME = "neurawork-cc-harness"


@dataclass
class Queue:
    """Where a queued engine keeps the four inputs of its SessionStart gate.

    Mirrors ``should_compile`` / ``should_update`` (the payload ``scripts/utils.py``
    of the knowledge-compiler and the claudemd-lerner): new daily content, not in a
    worktree, no fresh lock, last run at least ``age_hours`` old.
    """

    state: str
    stamp: str
    lock: str
    age_key: str
    age_default: float
    command: str  # `{dir}`-templated foreground command that drains the queue


@dataclass
class Engine:
    """One harness engine, as shipped under ``<plugin>/engines/<name>/``."""

    name: str
    default_dir: str
    # event -> a unique substring of that engine's installed hook command. Install
    # dirs are user-chosen, so the dir is always read BACK out of the command.
    hooks: dict[str, str] = field(default_factory=dict)
    # Two files, both required: a partial copy must not count as an install.
    signature: tuple[str, ...] = ()
    # (relative path, tracked) — an untracked data dir is legitimately absent in a
    # fresh clone or a worktree, so its absence is a note, not a fault.
    data_dirs: tuple[tuple[str, bool], ...] = ()
    queue: Queue | None = None
    # The slash command that (re-)installs it, or None when it has no installer.
    install_skill: str | None = None


ENGINES: dict[str, Engine] = {
    "knowledge-compiler": Engine(
        name="knowledge-compiler",
        default_dir="knowledge-base",
        hooks={
            "SessionStart": "hooks/session-start.py",
            "PreCompact": "hooks/pre-compact.py",
            "SessionEnd": "hooks/session-end.py",
            "UserPromptSubmit": "hooks/user-prompt-submit.py",
            "PreToolUse": "hooks/pre-skill.py",
        },
        signature=("hooks/session-end.py", "scripts/flush.py"),
        data_dirs=(("knowledge", True), ("daily", False)),
        queue=Queue(
            state="scripts/state.json",
            stamp="scripts/last-compile.json",
            lock="scripts/kc-compile.lock",
            age_key="compile_age_hours",
            age_default=6.0,
            command='uv run --directory {dir} python scripts/compile.py',
        ),
        install_skill="knowledge-compiler",
    ),
    "claudemd-lerner": Engine(
        name="claudemd-lerner",
        default_dir="claudemd-lerner",
        hooks={
            "SessionStart": "hooks/cl-session-start.py",
            "PreCompact": "hooks/cl-pre-compact.py",
            "SessionEnd": "hooks/cl-session-end.py",
        },
        signature=("hooks/cl-session-end.py", "scripts/flush.py"),
        # The learner's outputs are the repo-root CLAUDE.md + docs/; its own dir
        # holds machinery and the untracked capture queue only.
        data_dirs=(("daily", False),),
        queue=Queue(
            state="scripts/state.json",
            stamp="scripts/last-update.json",
            lock="scripts/cl-update.lock",
            age_key="update_age_hours",
            age_default=6.0,
            command='uv run --directory {dir} python scripts/update.py',
        ),
        install_skill="claudemd-lerner",
    ),
    "compliance-compiler": Engine(
        name="compliance-compiler",
        default_dir="compliance-base",
        hooks={"PostToolUse": "hooks/co-post-tooluse.py"},
        signature=("hooks/co-post-tooluse.py", "scripts/extract.py"),
        data_dirs=(("catalog", True),),
        queue=None,  # rebuilt on demand by co-extract; no SessionStart gate
        install_skill="compliance-compiler",
    ),
    "stack-compiler": Engine(
        name="stack-compiler",
        default_dir="stack-base",
        hooks={"PostToolUse": "hooks/st-post-tooluse.py"},
        signature=("scripts/scope.py", "scripts/rank.py"),
        data_dirs=(),  # owns no data artifact — it writes into compliance-base
        queue=None,
        install_skill="stack-compiler",
    ),
}


@dataclass
class Install:
    """One engine as found in a repo, and how it was found."""

    engine: str
    dirname: str | None
    found_by: str  # "hook" | "dir" | "both"
    missing_events: list[str]
    signature_ok: bool


_DIR_RE = re.compile(r"\$CLAUDE_PROJECT_DIR/([^\"'\s]+)")


def installed_dir_for(settings: dict, marker: str) -> str | None:
    """Return the install dir segment for the hook command containing `marker`."""
    hooks_obj = settings.get("hooks")
    if not isinstance(hooks_obj, dict):
        return None
    for groups in hooks_obj.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            for hook in group.get("hooks", []):
                command = str(hook.get("command", ""))
                if marker in command:
                    m = _DIR_RE.search(command)
                    if m:
                        return m.group(1)
    return None


def read_version(path: Path) -> str | None:
    """Return the stripped VERSION file content, or None (never raises)."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def is_behind(installed: str, shipped: str) -> bool:
    """True if the installed version is older than the shipped version."""
    try:
        return int(installed) < int(shipped)
    except ValueError:
        return installed != shipped


def _version_key(value: str) -> tuple[int, ...] | None:
    """`"0.5.1"` -> `(0, 5, 1)`, `"4"` -> `(4,)`, anything else -> None.

    Engine VERSIONs are single integers and plugin versions are dotted semver; one
    key covers both, so `compare` stays the only ordering primitive.
    """
    try:
        return tuple(int(part) for part in value.strip().split("."))
    except ValueError:
        return None


def compare(installed: str | None, shipped: str | None) -> str:
    """`behind` / `ahead` / `same` / `unknown`.

    Wider than ``is_behind``: an install that is AHEAD of the plugin (a local edit,
    or a plugin rolled back) is a real divergence the nudge silently ignores.
    """
    if installed is None or shipped is None:
        return "unknown"
    if installed == shipped:
        return "same"
    left, right = _version_key(installed), _version_key(shipped)
    if left is None or right is None:
        return "unknown"  # differing and unorderable
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    if left == right:
        return "same"  # "0.5" and "0.5.0" name the same release
    return "behind" if left < right else "ahead"


def load_settings(repo_root: Path) -> tuple[dict, str | None]:
    """``(settings, error)``. An absent file is not an error — an unparsable one is."""
    path = repo_root / ".claude" / "settings.json"
    if not path.exists():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, str(exc)
    if not isinstance(data, dict):
        return {}, "settings.json is not a JSON object"
    return data, None


def has_signature(repo_root: Path, dirname: str, engine: Engine) -> bool:
    """Whether every signature file of `engine` exists under `<repo>/<dirname>`."""
    if not dirname:
        return False
    target = repo_root / dirname
    return all((target / rel).exists() for rel in engine.signature)


def scan_for(repo_root: Path, engine: Engine) -> str | None:
    """The first top-level dir carrying the engine's full signature."""
    try:
        children = sorted(repo_root.iterdir())
    except OSError:
        return None
    for child in children:
        if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
            continue
        if has_signature(repo_root, child.name, engine):
            return child.name
    return None


def discover(repo_root: Path, settings: dict) -> list[Install]:
    """Every harness engine found in `repo_root`, by hook marker and by signature.

    The hook wins when the two disagree: it is what Claude Code actually executes,
    so an orphaned hook must be reported against the dir it names, not silently
    re-pointed at whatever the scan happened to find.
    """
    repo_root = Path(repo_root)
    found: list[Install] = []
    for engine in ENGINES.values():
        wired = {
            event: installed_dir_for(settings, marker)
            for event, marker in engine.hooks.items()
        }
        hook_dir = next((d for d in wired.values() if d), None)
        missing = sorted(e for e, d in wired.items() if not d)
        if hook_dir:
            signature_ok = has_signature(repo_root, hook_dir, engine)
            found.append(Install(
                engine=engine.name,
                dirname=hook_dir,
                found_by="both" if signature_ok else "hook",
                missing_events=missing,
                signature_ok=signature_ok,
            ))
            continue
        scanned = scan_for(repo_root, engine)
        if scanned:
            found.append(Install(
                engine=engine.name,
                dirname=scanned,
                found_by="dir",
                missing_events=missing,
                signature_ok=True,
            ))
    return found


def payload_files(plugin_root: Path, engine_name: str) -> list[str]:
    """The code files an install of `engine_name` must carry.

    Read from the shipped payload rather than a hand-kept list — it is exactly what
    every ``install.py`` ``_copy_code`` copies, so a new script cannot enter the
    payload and quietly stay out of the integrity check.
    """
    payload = Path(plugin_root) / "engines" / engine_name / "payload"
    if not payload.is_dir():
        return []
    files: list[str] = []
    for sub in ("hooks", "scripts"):
        directory = payload / sub
        if not directory.is_dir():
            continue
        for src in sorted(directory.iterdir()):
            if src.suffix in (".py", ".txt"):
                files.append(f"{sub}/{src.name}")
    for flat in ("pyproject.toml", "AGENTS.md"):
        if (payload / flat).exists():
            files.append(flat)
    return files


def shared_files(plugin_root: Path) -> list[str]:
    """The `_shared/` modules every install refreshes (the single source of truth).

    Top level only: ``compliance-compiler``'s installer deliberately withholds two
    plugin-only tests, so comparing ``_shared/tests/`` would report drift that the
    installer itself creates.
    """
    shared = Path(plugin_root) / "engines" / "_shared"
    if not shared.is_dir():
        return []
    return sorted(p.name for p in shared.glob("*.py"))


def find_stale(repo_root: Path, plugin_root: Path, settings: dict) -> list[dict]:
    """List engines whose installed VERSION is behind the shipped VERSION.

    Only engines with an installer: the nudge's whole payload is "re-run
    /neurawork-cc-harness:<engine>", and naming a slash command that does not exist
    is worse than staying quiet. All four engines have one; an engine added without
    an installer surfaces in the doctor instead.
    """
    stale = []
    for engine in ENGINES.values():
        if not engine.install_skill:
            continue
        dirname = None
        for marker in engine.hooks.values():
            dirname = installed_dir_for(settings, marker)
            if dirname:
                break
        if not dirname:
            continue
        installed = read_version(Path(repo_root) / dirname / "VERSION")
        shipped = read_version(Path(plugin_root) / "engines" / engine.name / "VERSION")
        if installed is None or shipped is None:
            continue
        if is_behind(installed, shipped):
            stale.append({
                "engine": engine.name,
                "dir": dirname,
                "installed": installed,
                "shipped": shipped,
            })
    return stale


# ── Plugin currency ────────────────────────────────────────────────────
#
# Whether the INSTALLED plugin is the newest one available is a different question
# from whether an engine install matches the plugin, and until now nothing answered
# it: a fix stays stranded in a cache until a version bump plus `/plugin update`
# (knowledge/concepts/plugin-version-bump-propagates-cache.md). The answer is on
# disk — Claude Code keeps a local clone of every known marketplace — so it needs
# neither the network nor a `git` process, both of which the doctor's contract bans.
# Every artifact is optional: a CI checkout has none of them and must still get a
# full report, so each absence becomes a note, never an exception.


@dataclass
class PluginState:
    """What the four on-disk plugin artifacts say, or None where one was unreadable."""

    plugins_dir: Path | None = None
    installed_version: str | None = None
    install_path: Path | None = None
    marketplace: str | None = None
    marketplace_location: Path | None = None
    available_version: str | None = None
    running_version: str | None = None
    # Sibling version dirs beside `install_path`, excluding the installed one.
    other_cached: list[str] = field(default_factory=list)
    # Why a field is None, in the operator's terms. Empty when everything resolved.
    notes: list[str] = field(default_factory=list)


def claude_config_dir() -> Path:
    """`$CLAUDE_CONFIG_DIR` or `~/.claude` — where Claude Code keeps its own state."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


def plugins_dir() -> Path:
    return claude_config_dir() / "plugins"


def _read_json(path: Path) -> object | None:
    """Parsed JSON, or None for a missing, unreadable or invalid file. Never raises."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _installed_entry(data: object) -> tuple[str | None, dict | None]:
    """`(marketplace, entry)` for the harness in `installed_plugins.json`.

    The file is `{"version": 2, "plugins": {"<plugin>@<marketplace>": [entry, ...]}}`,
    and one plugin can be installed at several scopes — user scope is the one the
    running session loads, so it wins when both are present.
    """
    if not isinstance(data, dict):
        return None, None
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return None, None
    for key, entries in plugins.items():
        if not str(key).startswith(f"{PLUGIN_NAME}@"):
            continue
        marketplace = str(key).split("@", 1)[1] or None
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            return marketplace, None
        candidates = [e for e in entries if isinstance(e, dict)]
        if not candidates:
            return marketplace, None
        user_scoped = [e for e in candidates if e.get("scope") == "user"]
        return marketplace, (user_scoped or candidates)[0]
    return None, None


def _marketplace_source_path(location: Path) -> str | None:
    """The harness's `source.path` inside its marketplace clone."""
    data = _read_json(location / ".claude-plugin" / "marketplace.json")
    if not isinstance(data, dict):
        return None
    for entry in data.get("plugins", []):
        if isinstance(entry, dict) and entry.get("name") == PLUGIN_NAME:
            source = entry.get("source")
            if isinstance(source, dict) and source.get("path"):
                return str(source["path"])
    return None


def _plugin_version(root: Path) -> str | None:
    data = _read_json(Path(root) / ".claude-plugin" / "plugin.json")
    if isinstance(data, dict) and data.get("version"):
        return str(data["version"])
    return None


def probe_plugin(plugin_root: Path) -> PluginState:
    """Read the plugin install registry, the marketplace clone and the running root.

    `plugin_root` is where THIS process was loaded from — which is not necessarily
    the installed cache (a symlinked local checkout, or a session started before an
    update), and that difference is itself worth reporting.
    """
    state = PluginState(running_version=_plugin_version(Path(plugin_root)))

    root = plugins_dir()
    if not root.is_dir():
        state.notes.append(f"{root} does not exist")
        return state
    state.plugins_dir = root

    marketplace, entry = _installed_entry(_read_json(root / "installed_plugins.json"))
    state.marketplace = marketplace
    if entry is None:
        state.notes.append(
            f"no {PLUGIN_NAME} entry in {root / 'installed_plugins.json'}"
        )
    else:
        state.installed_version = str(entry["version"]) if entry.get("version") else None
        if entry.get("installPath"):
            state.install_path = Path(str(entry["installPath"]))

    if state.install_path is not None:
        try:
            state.other_cached = sorted(
                child.name
                for child in state.install_path.parent.iterdir()
                if child.is_dir() and child.name != state.install_path.name
            )
        except OSError:
            pass

    markets = _read_json(root / "known_marketplaces.json")
    location = None
    if isinstance(markets, dict) and marketplace:
        record = markets.get(marketplace)
        if isinstance(record, dict) and record.get("installLocation"):
            location = Path(str(record["installLocation"]))
    if location is None:
        state.notes.append(
            f"no installLocation for marketplace {marketplace!r} in "
            f"{root / 'known_marketplaces.json'}"
        )
        return state
    state.marketplace_location = location

    source_path = _marketplace_source_path(location)
    if source_path is None:
        state.notes.append(f"no {PLUGIN_NAME} source path in {location}'s marketplace.json")
        return state
    source_root = location / source_path
    state.available_version = _plugin_version(source_root)
    if state.available_version is None:
        state.notes.append(f"no version in {source_root}/.claude-plugin/plugin.json")
    return state


def engine_version_drift(plugin_root: Path, state: PluginState) -> list[str]:
    """Engines whose VERSION in the RUNNING plugin differs from the marketplace clone.

    Composed with a `behind` currency verdict this answers the operational question
    the per-engine check alone cannot: re-running an install skill right now would
    copy the running plugin's older payload, so the plugin has to be updated first.
    """
    if state.marketplace_location is None:
        return []
    source_path = _marketplace_source_path(state.marketplace_location)
    if source_path is None:
        return []
    available_root = state.marketplace_location / source_path
    drifted = []
    for engine in ENGINES.values():
        running = read_version(Path(plugin_root) / "engines" / engine.name / "VERSION")
        newest = read_version(available_root / "engines" / engine.name / "VERSION")
        if running is None or newest is None:
            continue
        if running != newest:
            drifted.append(engine.name)
    return drifted
