"""Read-only install recon for the stack-compiler skill.

Prints a human summary, then emits a RECON_JSON blob the install skill parses to
drive its AskUserQuestion prompts. Detects an existing install (ADOPT), the sibling
compliance-compiler install it reads/writes through, and how far the stack decisions
in that sibling's ``catalog/stack.json`` have got.

Run:  python3 engines/stack-compiler/recon.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # engines/ for _shared

from _shared.recon import emit_recon_json, git_root_or_none

HOOK_EVENTS = {
    "PostToolUse": "st-post-tooluse.py",
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


def _find_existing_dir(root: Path) -> str | None:
    """A top-level dir that already looks like an installed stack-compiler.

    The same dual-file signature install.py's ``_is_adopt`` uses, so mode detection
    and dir discovery cannot disagree.
    """
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "hooks" / "st-post-tooluse.py").exists() and \
           (child / "scripts" / "scope.py").exists():
            return child.name
    return None


def _find_compliance_dir(root: Path) -> str | None:
    """A top-level dir holding the schema owner and the capability catalog to read."""
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "scripts" / "stack.py").exists() and \
           (child / "catalog" / "capabilities.json").exists():
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


def _stack_state(root: Path, cdir: str | None) -> dict:
    """How far the recorded decisions have got. Defensive — ``{}`` on any error."""
    if not cdir:
        return {"exists": False}
    path = root / cdir / "catalog" / "stack.json"
    if not path.exists():
        return {"exists": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        choices = data.get("choices") or {}
        if not isinstance(choices, dict):
            return {"exists": True}
        return {
            "exists": True,
            "total": len(choices),
            # `scoped_from`, not `applicable`: the scaffold in stack.py writes
            # `applicable: True` for every entry before the scope pass has ever run, so
            # an `applicable is not None` count reports "fully scoped" on a repo where
            # nothing was scoped. `scoped_from` is stamped by the pass itself.
            "scoped": sum(1 for e in choices.values()
                          if isinstance(e, dict) and e.get("scoped_from")),
            "chosen": sum(1 for e in choices.values()
                          if isinstance(e, dict) and e.get("chosen")),
        }
    except (json.JSONDecodeError, OSError, AttributeError):
        return {"exists": True}


def main() -> int:
    root_str = git_root_or_none()
    if not root_str:
        print("NOT_A_GIT_REPO")
        emit_recon_json({"status": "NOT_A_GIT_REPO"})
        return 1

    root = Path(root_str)
    branch, clean = _branch_and_clean(root_str)
    existing_dir = _find_existing_dir(root)
    compliance_dir = _find_compliance_dir(root)
    existing_hooks = _existing_hooks(root)
    stack_state = _stack_state(root, compliance_dir)
    tz = datetime.now(timezone.utc).astimezone().strftime("%Z%z")

    info = {
        "status": "OK",
        "repo_root": root_str,
        "branch": branch,
        "clean": clean,
        "existing_dir": existing_dir,
        "compliance_dir": compliance_dir,
        "existing_hooks": existing_hooks,
        "stack_state": stack_state,
        "timezone": tz,
    }

    print(f"Repo: {root_str}")
    print(f"Branch: {branch} ({'clean' if clean else 'dirty'})")
    print(f"Existing install: {existing_dir or '(none — FRESH)'}")
    print(f"Compliance install: {compliance_dir or '(none — passes have nothing to read)'}")
    print(f"Hooks present: {', '.join(e for e, v in existing_hooks.items() if v) or '(none)'}")
    print(f"Stack decisions: {stack_state}")
    print(f"Timezone: {tz}")
    emit_recon_json(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
