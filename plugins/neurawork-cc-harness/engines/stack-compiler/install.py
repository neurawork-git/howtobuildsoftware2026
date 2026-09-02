"""Install (or adopt) the stack-compiler into the current repo.

Copies the payload + the shared helpers into ``<repo>/<stack_dir>/``, scaffolds
reports/, writes config.json and .gitignore, and merges the PostToolUse PRD/plan
gate into .claude/settings.json. ADOPT mode refreshes code without clobbering an
existing config.json, product.md, or any recorded stack decisions.

This engine owns no data artifact: every write goes through
``<compliance_dir>/scripts/stack.py``, the single schema owner for
``catalog/stack.json``. The installer therefore seeds nothing — ``scripts/scope.py``
carries the ``product.md`` template and writes it on its first run.

The hook filename is ``st-``-prefixed and registers under the same
``Write|Edit|MultiEdit`` PostToolUse matcher as the compliance gate, so all four
harness engines coexist in one .claude/settings.json.

Run:
    python3 engines/stack-compiler/install.py [--stack-dir NAME] [--compliance-dir NAME]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PAYLOAD = ENGINE_DIR / "payload"
SHARED_SRC = ENGINE_DIR.parent / "_shared"
DEFAULTS_FILE = ENGINE_DIR / "config.default.json"
VERSION_FILE = ENGINE_DIR / "VERSION"

sys.path.insert(0, str(ENGINE_DIR.parent))  # engines/ for _shared

from _shared.prp_store import wire_store
from _shared.recon import git_root_or_none
from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude
from _shared.settings import SettingsError, merge_gitignore, merge_hooks, prune_gitignore
from _shared_install import refresh_shared

GITIGNORE = """\
# stack-compiler runtime (product.md is TRACKED — it is the scoping input of
# record; everything below is local machinery)
.shards/
reports/
scripts/state.json
scripts/*.log
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
    return (target / "hooks" / "st-post-tooluse.py").exists() and \
           (target / "scripts" / "scope.py").exists()


def _copy_code(target: Path) -> None:
    """Copy/refresh the code payload (always overwrites code, never data)."""
    (target / "hooks").mkdir(parents=True, exist_ok=True)
    (target / "scripts").mkdir(parents=True, exist_ok=True)
    for src in (PAYLOAD / "hooks").glob("*.py"):
        shutil.copy2(src, target / "hooks" / src.name)
    for src in (PAYLOAD / "scripts").glob("*.py"):
        shutil.copy2(src, target / "scripts" / src.name)
    shutil.copy2(PAYLOAD / "pyproject.toml", target / "pyproject.toml")
    shutil.copy2(PAYLOAD / "AGENTS.md", target / "AGENTS.md")
    # _shared refreshed every install (single source of truth), minus the tests that
    # only make sense inside the plugin — see engines/_shared_install.py.
    refresh_shared(SHARED_SRC, target)


def _scaffold(target: Path, sdir: str, cdir: str) -> None:
    """Create data dirs/files only if absent (never clobber)."""
    (target / "reports").mkdir(parents=True, exist_ok=True)

    config = target / "config.json"
    if not config.exists():
        defaults = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
        defaults["stack_dir"] = sdir
        defaults["compliance_dir"] = cdir
        config.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")

    # Merge, never create-if-absent: a rule added in a later release has to reach the
    # installs that already exist, and only the missing lines are appended — a user's
    # own rules keep their place.
    prune_gitignore(target, REMOVED_GITIGNORE_RULES)
    merge_gitignore(target, GITIGNORE)

    shutil.copy2(VERSION_FILE, target / "VERSION")


def _hooks(sdir: str) -> list[tuple[str, str, int, str, str]]:
    base = f'uv run --directory "$CLAUDE_PROJECT_DIR/{sdir}" python'
    # The matcher is the registration, not a hand-edit: without it the hook is in the
    # catch-all group and every tool call in every session pays for a `uv run` subprocess
    # that reads stdin and exits. The hook keeps its own WRITE_TOOLS check — a matcher is
    # an optimisation, and a settings.json someone edited by hand must still be safe.
    return [
        ("PostToolUse", f"{base} hooks/st-post-tooluse.py", 60,
         "hooks/st-post-tooluse.py", "Write|Edit|MultiEdit"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the stack-compiler")
    parser.add_argument("--stack-dir", default="stack-base", help="Stack dir name")
    parser.add_argument("--compliance-dir", default="compliance-base",
                        help="Compliance-compiler install dir it reads/writes through")
    args = parser.parse_args()

    root_str = git_root_or_none()
    if not root_str:
        print("NOT_A_GIT_REPO — install refused. Run inside a git repository.")
        return 1
    root = Path(root_str)

    sdir = args.stack_dir.strip("/").strip()
    cdir = args.compliance_dir.strip("/").strip()
    target = root / sdir
    try:
        assert_in_repo_not_dotclaude(target, root)
    except WriteGuardError as e:
        print(f"Invalid stack dir: {e}")
        return 1

    mode = "ADOPT" if _is_adopt(target) else "FRESH"
    print(f"{mode} install of stack-compiler into {target}")

    _copy_code(target)
    _scaffold(target, sdir, cdir)

    try:
        changed = merge_hooks(root, _hooks(sdir))
        print(f"Hooks {'merged' if changed else 'already present'} in .claude/settings.json")
    except Exception as e:
        print(f"Hook merge failed: {e}")
        return 1

    try:
        _, lines = wire_store(root)
    except (SettingsError, OSError) as e:
        print(f"PRP store wiring failed: {e}")
        return 1
    for line in lines:
        print(line)

    # Independently installable, not independently operable: the passes read the
    # capability catalog and write through <compliance-dir>/scripts/stack.py. Warn,
    # never fail — install order must not be load-bearing.
    if not (root / cdir / "catalog" / "capabilities.json").exists():
        print(f"\nNo {cdir}/catalog/capabilities.json — the three passes and the gate have "
              "nothing to read until compliance-compiler is installed and its catalog "
              "built (/neurawork-cc-harness:compliance-compiler, then "
              "/neurawork-cc-harness:co-capabilities).")

    print("\nNext steps:")
    print(f"  uv sync --directory {sdir}")
    print(f"  write {sdir}/product.md — /neurawork-cc-harness:st-scope writes the "
          "template on its first run, then it must be filled in")
    print(f"  git add {sdir} .claude/settings.json && git commit -m 'Add stack-compiler'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
