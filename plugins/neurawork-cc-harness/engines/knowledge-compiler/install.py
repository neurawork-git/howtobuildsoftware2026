"""Install (or adopt) the knowledge-compiler into the current repo.

Copies the payload + the shared helpers into ``<repo>/<kdir>/``, scaffolds the
daily/ and knowledge/ trees, writes .gitignore, and merges the three hooks into
.claude/settings.json. ADOPT mode refreshes code without clobbering an existing
knowledge base.

Run:
    python3 engines/knowledge-compiler/install.py [--knowledge-dir NAME] [--seed]
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
from _shared.settings import merge_hooks
from _shared.repo_guard import assert_in_repo_not_dotclaude, WriteGuardError

GITIGNORE = """\
# knowledge-compiler runtime (knowledge/ is tracked; these are local)
daily/
reports/
knowledge/log.md
scripts/state.json
scripts/last-compile.json
scripts/last-flush.json
scripts/kc-compile.lock
scripts/*.log
scripts/session-flush-*.md
scripts/flush-context-*.md
__pycache__/
*.pyc
.venv/
uv.lock
"""

INDEX_SEED = """\
# Knowledge Base Index

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
"""


def _is_adopt(target: Path) -> bool:
    return (target / "hooks" / "session-end.py").exists() and \
           (target / "scripts" / "flush.py").exists()


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


def _scaffold(target: Path, kdir: str) -> None:
    """Create data dirs/files only if absent (never clobber)."""
    for sub in ("daily", "knowledge/concepts", "knowledge/connections"):
        (target / sub).mkdir(parents=True, exist_ok=True)
    index = target / "knowledge" / "index.md"
    if not index.exists():
        index.write_text(INDEX_SEED, encoding="utf-8")

    config = target / "config.json"
    if not config.exists():
        defaults = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
        defaults["knowledge_dir"] = kdir
        config.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")

    gitignore = target / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE, encoding="utf-8")

    shutil.copy2(VERSION_FILE, target / "VERSION")


def _hooks(kdir: str) -> list[tuple[str, str, int, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{kdir}" python'
    return [
        ("SessionStart", f"{base} hooks/session-start.py", 15, "hooks/session-start.py"),
        ("PreCompact", f"{base} hooks/pre-compact.py", 10, "hooks/pre-compact.py"),
        ("SessionEnd", f"{base} hooks/session-end.py", 10, "hooks/session-end.py"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the knowledge-compiler")
    parser.add_argument("--knowledge-dir", default="knowledge-base", help="Knowledge dir name")
    parser.add_argument("--seed", action="store_true", help="Seed from the repo after install")
    args = parser.parse_args()

    root_str = git_root_or_none()
    if not root_str:
        print("NOT_A_GIT_REPO — install refused. Run inside a git repository.")
        return 1
    root = Path(root_str)

    kdir = args.knowledge_dir.strip("/").strip()
    target = root / kdir
    try:
        assert_in_repo_not_dotclaude(target, root)
    except WriteGuardError as e:
        print(f"Invalid knowledge dir: {e}")
        return 1

    mode = "ADOPT" if _is_adopt(target) else "FRESH"
    print(f"{mode} install of knowledge-compiler into {target}")

    _copy_code(target)
    _scaffold(target, kdir)

    try:
        changed = merge_hooks(root, _hooks(kdir))
        print(f"Hooks {'merged' if changed else 'already present'} in .claude/settings.json")
    except Exception as e:
        print(f"Hook merge failed: {e}")
        return 1

    print("\nNext steps:")
    print(f"  uv sync --directory {kdir}")
    print(f"  git add {kdir} .claude/settings.json && git commit -m 'Add knowledge-compiler'")

    if args.seed:
        print("\nSeeding (requires ANTHROPIC_API_KEY)...")
        subprocess.run(["uv", "sync", "--directory", str(target)], check=False)
        rc = subprocess.run(
            ["uv", "run", "--directory", str(target), "python", "scripts/seed.py"],
            check=False,
        ).returncode
        if rc != 0:
            print("Seed did not complete cleanly — see output above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
