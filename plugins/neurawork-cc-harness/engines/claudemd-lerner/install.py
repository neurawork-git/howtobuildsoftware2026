"""Install (or adopt) the claudemd-lerner into the current repo.

Copies the payload + the shared helpers into ``<repo>/<ldir>/``, scaffolds the
daily/ and scripts/ dirs, writes .gitignore, and merges the three cl- hooks into
.claude/settings.json. ADOPT mode refreshes code without clobbering existing data.

The learner's OUTPUTS (CLAUDE.md files + docs/) live at the repo ROOT — this
installer never scaffolds them; seed.py / update.py write them. The cl- hook
filenames give markers that never collide with the knowledge-compiler skill, so
both skills can be installed in one repo.

Run:
    python3 engines/claudemd-lerner/install.py [--lerner-dir NAME] [--seed]
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
from _shared.settings import merge_gitignore, merge_hooks, prune_gitignore
from _shared.repo_guard import assert_in_repo_not_dotclaude, WriteGuardError
from _shared_install import refresh_shared

GITIGNORE = """\
# claudemd-lerner runtime (CLAUDE.md + docs/ live at the repo root and are tracked;
# everything below is local machinery)
daily/
scripts/state.json
scripts/last-update.json
scripts/last-flush.json
scripts/cl-update.lock
scripts/*.log
scripts/session-flush-*.md
scripts/flush-context-*.md
__pycache__/
*.pyc
.venv/
"""

# Rules this engine USED to ship in GITIGNORE and no longer does. Pruned on every
# install so the line an earlier release wrote is removed from installs that already
# exist — merge_gitignore only ever appends. uv.lock is TRACKED now: a committed lock
# file removes the dependency resolve from a hook's cold start in a fresh checkout.
REMOVED_GITIGNORE_RULES = ("uv.lock",)


def _is_adopt(target: Path) -> bool:
    return (target / "hooks" / "cl-session-end.py").exists() and \
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
    # _shared refreshed every install (single source of truth), minus the tests that
    # only make sense inside the plugin — see engines/_shared_install.py.
    refresh_shared(SHARED_SRC, target)


def _scaffold(target: Path, ldir: str) -> None:
    """Create data dirs/files only if absent (never clobber). No knowledge/ tree —
    the learner's outputs (CLAUDE.md + docs/) live at the repo root."""
    (target / "daily").mkdir(parents=True, exist_ok=True)
    (target / "scripts").mkdir(parents=True, exist_ok=True)

    config = target / "config.json"
    if not config.exists():
        defaults = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
        defaults["lerner_dir"] = ldir
        config.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")

    # Merge, never create-if-absent: a rule added to GITIGNORE in a later release has to
    # reach the installs that already exist, and only the missing lines are appended so a
    # user's own rules keep their place.
    prune_gitignore(target, REMOVED_GITIGNORE_RULES)
    merge_gitignore(target, GITIGNORE)

    shutil.copy2(VERSION_FILE, target / "VERSION")


def _hooks(ldir: str) -> list[tuple[str, str, int, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{ldir}" python'
    # All three register in the catch-all group deliberately: none of these events
    # carries a tool name, so there is nothing for a matcher to select on.
    return [
        ("SessionStart", f"{base} hooks/cl-session-start.py", 60, "hooks/cl-session-start.py"),
        ("PreCompact", f"{base} hooks/cl-pre-compact.py", 60, "hooks/cl-pre-compact.py"),
        ("SessionEnd", f"{base} hooks/cl-session-end.py", 60, "hooks/cl-session-end.py"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the claudemd-lerner")
    parser.add_argument("--lerner-dir", default="claudemd-lerner", help="Lerner dir name")
    parser.add_argument("--seed", action="store_true", help="Seed from the repo after install")
    args = parser.parse_args()

    root_str = git_root_or_none()
    if not root_str:
        print("NOT_A_GIT_REPO — install refused. Run inside a git repository.")
        return 1
    root = Path(root_str)

    ldir = args.lerner_dir.strip("/").strip()
    target = root / ldir
    try:
        assert_in_repo_not_dotclaude(target, root)
    except WriteGuardError as e:
        print(f"Invalid lerner dir: {e}")
        return 1

    mode = "ADOPT" if _is_adopt(target) else "FRESH"
    print(f"{mode} install of claudemd-lerner into {target}")

    _copy_code(target)
    _scaffold(target, ldir)

    try:
        changed = merge_hooks(root, _hooks(ldir))
        print(f"Hooks {'merged' if changed else 'already present'} in .claude/settings.json")
    except Exception as e:
        print(f"Hook merge failed: {e}")
        return 1

    print("\nNext steps:")
    print(f"  uv sync --directory {ldir}")
    print(f"  git add {ldir} .claude/settings.json && git commit -m 'Add claudemd-lerner'")

    if args.seed:
        print("\nSeeding (requires ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN)...")
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
