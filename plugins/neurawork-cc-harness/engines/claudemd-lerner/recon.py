"""Read-only install recon for the claudemd-lerner skill.

Prints a human summary, then emits a RECON_JSON blob the install skill parses to
drive its AskUserQuestion prompts. Detects an existing install (ADOPT), the
current CLAUDE.md depth and docs layout, a language hint, and whether a brownfield
seed is worth offering.

Run:  python3 engines/claudemd-lerner/recon.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # engines/ for _shared

from _shared.recon import git_root_or_none, emit_recon_json

HOOK_EVENTS = {
    "SessionStart": "cl-session-start.py",
    "PreCompact": "cl-pre-compact.py",
    "SessionEnd": "cl-session-end.py",
}

DEFAULT_EXCLUDED = ["node_modules", ".venv", "dist", "build", ".git"]


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


def _find_existing_ldir(root: Path) -> str | None:
    """A top-level dir that already looks like an installed claudemd-lerner."""
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "hooks" / "cl-session-end.py").exists() and \
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


def _claudemd_scan(root: Path) -> tuple[int, int]:
    """(count of CLAUDE.md files, max subdir depth among them, ignoring dotdirs/excluded)."""
    excl = set(DEFAULT_EXCLUDED)
    count = 0
    max_depth = 0
    for p in root.rglob("CLAUDE.md"):
        rel = p.relative_to(root)
        if any(part in excl or part.startswith(".") for part in rel.parts[:-1]):
            continue
        count += 1
        max_depth = max(max_depth, len(rel.parts) - 1)
    return count, max_depth


def _language_hint(root: Path) -> str:
    """Best-effort: 'de' if a README/CLAUDE.md looks German, else 'en'."""
    for name in ("CLAUDE.md", "README.md"):
        f = root / name
        if f.exists():
            try:
                text = f.read_text(encoding="utf-8")[:4000].lower()
            except OSError:
                continue
            de_markers = len(re.findall(r"\b(und|nicht|werden|müssen|für|mit|oder|ist)\b", text))
            if de_markers >= 5:
                return "de"
            return "en"
    return "en"


def main() -> int:
    root_str = git_root_or_none()
    if not root_str:
        print("NOT_A_GIT_REPO")
        emit_recon_json({"status": "NOT_A_GIT_REPO"})
        return 1

    root = Path(root_str)
    branch, clean = _branch_and_clean(root_str)
    existing_ldir = _find_existing_ldir(root)
    existing_hooks = _existing_hooks(root)
    tz = datetime.now(timezone.utc).astimezone().strftime("%Z%z")
    has_readme = any((root / n).exists() for n in ("README.md", "README.rst", "README.txt"))
    has_root_claudemd = (root / "CLAUDE.md").exists()
    has_docs = (root / "docs").is_dir()
    claudemd_count, claudemd_depth = _claudemd_scan(root)
    suggested_depth = max(claudemd_depth, 1)
    language = _language_hint(root)
    excluded_present = [d for d in DEFAULT_EXCLUDED if (root / d).exists()]
    seed_recommended = existing_ldir is None and (has_readme or has_docs or has_root_claudemd)

    info = {
        "status": "OK",
        "repo_root": root_str,
        "branch": branch,
        "clean": clean,
        "existing_ldir": existing_ldir,
        "existing_hooks": existing_hooks,
        "timezone": tz,
        "has_readme": has_readme,
        "has_root_claudemd": has_root_claudemd,
        "has_docs": has_docs,
        "claudemd_count": claudemd_count,
        "suggested_depth": suggested_depth,
        "language": language,
        "excluded_present": excluded_present,
        "seed_recommended": seed_recommended,
    }

    print(f"Repo: {root_str}")
    print(f"Branch: {branch} ({'clean' if clean else 'dirty'})")
    print(f"Existing install: {existing_ldir or '(none — FRESH)'}")
    print(f"Hooks present: {', '.join(e for e, v in existing_hooks.items() if v) or '(none)'}")
    print(f"CLAUDE.md files: {claudemd_count} (max subdir depth {claudemd_depth})")
    print(f"docs/: {'yes' if has_docs else 'no'} | language hint: {language}")
    print(f"Timezone: {tz}")
    print(f"Seed recommended: {seed_recommended}")
    emit_recon_json(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
