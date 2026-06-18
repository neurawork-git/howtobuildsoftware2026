"""Read-only install recon for the knowledge-compiler skill.

Prints a human summary, then emits a RECON_JSON blob the install skill parses to
drive its AskUserQuestion prompts. Detects an existing install (ADOPT) and whether
a brownfield seed is worth offering.

Run:  python3 engines/knowledge-compiler/recon.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # engines/ for _shared

from _shared.recon import git_root_or_none, emit_recon_json

HOOK_EVENTS = {
    "SessionStart": "session-start.py",
    "PreCompact": "pre-compact.py",
    "SessionEnd": "session-end.py",
}


def _branch_and_clean(root: str) -> tuple[str, bool]:
    def _run(args):
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True,
                                  text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
    branch = "unknown"
    b = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    if b and b.returncode == 0:
        branch = b.stdout.strip()
    st = _run(["status", "--porcelain"])
    clean = bool(st and st.returncode == 0 and not st.stdout.strip())
    return branch, clean


def _find_existing_kdir(root: Path) -> str | None:
    """A top-level dir that already looks like an installed knowledge base."""
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "hooks" / "session-end.py").exists() and \
           (child / "scripts" / "flush.py").exists():
            return child.name
    return None


def _existing_hooks(root: Path) -> dict:
    settings = root / ".claude" / "settings.json"
    found = {e: False for e in HOOK_EVENTS}
    if not settings.exists():
        return found
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return found
    hooks = data.get("hooks", {}) if isinstance(data, dict) else {}
    for event, marker in HOOK_EVENTS.items():
        for group in hooks.get(event, []):
            for h in group.get("hooks", []):
                if marker in str(h.get("command", "")):
                    found[event] = True
    return found


def main() -> int:
    root_str = git_root_or_none()
    if not root_str:
        print("NOT_A_GIT_REPO")
        emit_recon_json({"status": "NOT_A_GIT_REPO"})
        return 1

    root = Path(root_str)
    branch, clean = _branch_and_clean(root_str)
    existing_kdir = _find_existing_kdir(root)
    existing_hooks = _existing_hooks(root)
    tz = datetime.now(timezone.utc).astimezone().strftime("%Z%z")
    has_readme = any((root / n).exists() for n in ("README.md", "README.rst", "README.txt"))
    has_docs = (root / "docs").is_dir()
    seed_recommended = existing_kdir is None and (has_readme or has_docs)

    info = {
        "status": "OK",
        "repo_root": root_str,
        "branch": branch,
        "clean": clean,
        "existing_kdir": existing_kdir,
        "existing_hooks": existing_hooks,
        "timezone": tz,
        "has_readme": has_readme,
        "has_docs": has_docs,
        "seed_recommended": seed_recommended,
    }

    print(f"Repo: {root_str}")
    print(f"Branch: {branch} ({'clean' if clean else 'dirty'})")
    print(f"Existing install: {existing_kdir or '(none — FRESH)'}")
    print(f"Hooks present: {', '.join(e for e, v in existing_hooks.items() if v) or '(none)'}")
    print(f"Timezone: {tz}")
    print(f"Seed recommended: {seed_recommended}")
    emit_recon_json(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
