"""Install (or adopt) the compliance-compiler into the current repo.

Copies the payload + the shared helpers into ``<repo>/<catalog_dir>/``, scaffolds
the catalog/ and reports/ trees, writes .gitignore, and merges the SessionStart +
PostToolUse hooks into .claude/settings.json. ADOPT mode refreshes code without
clobbering an existing catalog.

The hook filenames are ``co-``-prefixed and the PostToolUse event is untouched by
the other harness engines, so all three coexist in one .claude/settings.json.

Run:
    python3 engines/compliance-compiler/install.py [--catalog-dir NAME] [--extract]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PAYLOAD = ENGINE_DIR / "payload"
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
scripts/co-extract.lock
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


def _hooks(cdir: str) -> list[tuple[str, str, int, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{cdir}" python'
    return [
        ("SessionStart", f"{base} hooks/co-session-start.py", 15, "hooks/co-session-start.py"),
        ("PostToolUse", f"{base} hooks/co-post-tooluse.py", 15, "hooks/co-post-tooluse.py"),
    ]


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

    try:
        changed = merge_hooks(root, _hooks(cdir))
        print(f"Hooks {'merged' if changed else 'already present'} in .claude/settings.json")
    except Exception as e:
        print(f"Hook merge failed: {e}")
        return 1

    print("\nNext steps:")
    print(f"  uv sync --directory {cdir}")
    print(f"  git add {cdir} .claude/settings.json && git commit -m 'Add compliance-compiler'")

    if args.extract:
        print("\nExtracting catalog (requires ANTHROPIC_API_KEY)...")
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
