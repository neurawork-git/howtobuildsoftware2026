"""Install (or adopt) the compliance-compiler into the current repo.

Copies the payload + the shared helpers into ``<repo>/<catalog_dir>/``, scaffolds
the catalog/ and reports/ trees, writes .gitignore, and merges the PostToolUse
plan-validator hook into .claude/settings.json. ADOPT mode refreshes code without
clobbering an existing catalog. The catalog is built at install time (``--extract``)
and rebuilt on demand via ``/neurawork-cc-harness:co-extract`` — there is no
SessionStart bootstrap.

The hook filename is ``co-``-prefixed and the PostToolUse event is untouched by
the other harness engines, so all three coexist in one .claude/settings.json.

Run:
    python3 engines/compliance-compiler/install.py [--catalog-dir NAME] [--extract]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PAYLOAD = ENGINE_DIR / "payload"
SEED_DIR = PAYLOAD / "catalog-seed"
SHARED_SRC = ENGINE_DIR.parent / "_shared"
DEFAULTS_FILE = ENGINE_DIR / "config.default.json"
VERSION_FILE = ENGINE_DIR / "VERSION"

sys.path.insert(0, str(ENGINE_DIR.parent))  # engines/ for _shared

from _shared.recon import git_root_or_none
from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude
from _shared.settings import merge_hooks

GITIGNORE = """\
# compliance-compiler runtime (catalog/*.json + catalog/index.md are tracked;
# everything below is local machinery)
catalog/.shards/
reports/
scripts/state.json
scripts/last-extract.json
scripts/*.log
__pycache__/
*.pyc
.venv/
uv.lock
"""


def _is_adopt(target: Path) -> bool:
    return (target / "hooks" / "co-post-tooluse.py").exists() and \
           (target / "scripts" / "extract.py").exists()


def _copy_code(target: Path) -> None:
    """Copy/refresh the code payload (always overwrites code, never data)."""
    (target / "hooks").mkdir(parents=True, exist_ok=True)
    (target / "scripts").mkdir(parents=True, exist_ok=True)
    for src in (PAYLOAD / "hooks").glob("*.py"):
        shutil.copy2(src, target / "hooks" / src.name)
    for src in (PAYLOAD / "scripts").iterdir():
        if src.suffix in (".py", ".txt"):
            shutil.copy2(src, target / "scripts" / src.name)
    shutil.copy2(PAYLOAD / "pyproject.toml", target / "pyproject.toml")
    shutil.copy2(PAYLOAD / "AGENTS.md", target / "AGENTS.md")
    # _shared refreshed every install (single source of truth).
    shutil.copytree(SHARED_SRC, target / "_shared",
                    ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)


def _scaffold(target: Path, cdir: str) -> None:
    """Create data dirs/files only if absent (never clobber)."""
    for sub in ("catalog/.shards", "reports"):
        (target / sub).mkdir(parents=True, exist_ok=True)

    config = target / "config.json"
    if not config.exists():
        defaults = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
        defaults["catalog_dir"] = cdir
        config.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")

    gitignore = target / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE, encoding="utf-8")

    shutil.copy2(VERSION_FILE, target / "VERSION")


def _seed_catalog(target: Path) -> None:
    """Copy the shipped prebuilt catalog into a target that has none of its own, so a
    fresh install has a working catalog with no LLM run.

    Atomic: if the target already holds any constraint catalog (a ``<framework>.json``,
    e.g. from a prior ``extract.py``) the whole seed is skipped — the shipped
    capabilities.json is never mixed into a repo's own extraction (which would send the
    next ``capabilities.py`` run down a bogus constraint-delta path). ADOPT over an
    already-built catalog is therefore left untouched."""
    if not SEED_DIR.is_dir():
        return
    seed_files = [f for f in SEED_DIR.iterdir() if f.suffix in (".json", ".md")]
    constraint_jsons = [f.name for f in seed_files
                        if f.suffix == ".json" and f.name != "capabilities.json"]
    catalog = target / "catalog"
    if any((catalog / name).exists() for name in constraint_jsons):
        return  # repo has its own constraint catalog — never partial-seed over it
    catalog.mkdir(parents=True, exist_ok=True)
    for src in seed_files:
        dst = catalog / src.name
        if not dst.exists():
            shutil.copy2(src, dst)


def _hooks(cdir: str) -> list[tuple[str, str, int, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{cdir}" python'
    return [
        ("PostToolUse", f"{base} hooks/co-post-tooluse.py", 15, "hooks/co-post-tooluse.py"),
    ]


# Files/hooks this engine USED to install but no longer ships. Pruned on every
# install so an ADOPT upgrade cleans up after itself (merge_hooks only ever adds).
REMOVED_TARGET_FILES = ("hooks/co-session-start.py", "scripts/co-extract.lock")
REMOVED_HOOK_MARKERS = ("hooks/co-session-start.py",)


def _prune_removed(target: Path, root: Path) -> None:
    """Delete files this engine no longer ships and prune their settings.json hooks.

    Makes upgrades clean: a repo installed before the SessionStart hook was dropped
    loses the stale ``co-session-start.py`` file and its ``.claude/settings.json``
    entry on the next (re)install. No-op on a fresh install.
    """
    for rel in REMOVED_TARGET_FILES:
        p = target / rel
        if p.exists():
            p.unlink()
            print(f"Removed stale {rel}")

    settings_path = root / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    hooks_obj = data.get("hooks")
    if not isinstance(hooks_obj, dict):
        return

    changed = False
    for event in list(hooks_obj):
        groups = hooks_obj.get(event)
        if not isinstance(groups, list):
            continue
        for g in groups:
            hooks = g.get("hooks")
            if not isinstance(hooks, list):
                continue
            kept = [h for h in hooks
                    if not any(m in str(h.get("command", "")) for m in REMOVED_HOOK_MARKERS)]
            if len(kept) != len(hooks):
                g["hooks"] = kept
                changed = True
        non_empty = [g for g in groups if g.get("hooks")]
        if not non_empty:
            del hooks_obj[event]
            changed = True
        elif len(non_empty) != len(groups):
            hooks_obj[event] = non_empty
            changed = True

    if changed:
        tmp = settings_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, settings_path)
        print("Pruned stale SessionStart hook from .claude/settings.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the compliance-compiler")
    parser.add_argument("--catalog-dir", default="compliance-base", help="Catalog dir name")
    parser.add_argument("--extract", action="store_true", help="Run extraction after install")
    args = parser.parse_args()

    root_str = git_root_or_none()
    if not root_str:
        print("NOT_A_GIT_REPO — install refused. Run inside a git repository.")
        return 1
    root = Path(root_str)

    cdir = args.catalog_dir.strip("/").strip()
    target = root / cdir
    try:
        assert_in_repo_not_dotclaude(target, root)
    except WriteGuardError as e:
        print(f"Invalid catalog dir: {e}")
        return 1

    mode = "ADOPT" if _is_adopt(target) else "FRESH"
    print(f"{mode} install of compliance-compiler into {target}")

    _copy_code(target)
    _scaffold(target, cdir)
    _seed_catalog(target)

    try:
        changed = merge_hooks(root, _hooks(cdir))
        print(f"Hooks {'merged' if changed else 'already present'} in .claude/settings.json")
    except Exception as e:
        print(f"Hook merge failed: {e}")
        return 1

    _prune_removed(target, root)

    print("\nNext steps:")
    print(f"  uv sync --directory {cdir}")
    print(f"  git add {cdir} .claude/settings.json && git commit -m 'Add compliance-compiler'")

    if args.extract:
        print("\nExtracting catalog (requires ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN)...")
        subprocess.run(["uv", "sync", "--directory", str(target)], check=False)
        rc = subprocess.run(
            ["uv", "run", "--directory", str(target), "python", "scripts/extract.py"],
            check=False,
        ).returncode
        if rc != 0:
            print("Extraction did not complete cleanly — see output above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
