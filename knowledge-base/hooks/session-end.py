"""SessionEnd hook — capture the transcript and spawn flush.py in the background.

Fast, local-only (no API calls): parse stdin, extract recent turns via the shared
helper, write them to a context file, then Popen flush.py. Worktree-aware — output
is redirected into the main checkout so it survives `git worktree remove`.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))

from _shared.hookio import recursion_guard, read_hook_input, child_env

recursion_guard()

from _shared.transcript import extract_turns
from _shared.gitctx import in_worktree, main_checkout_root

MIN_TURNS_TO_FLUSH = 1
CONTEXT_PREFIX = "session-flush-"
LOG_TAG = "[session-end]"


def effective_root() -> Path:
    """Where to write output: main checkout's kdir if in a worktree, else here."""
    if in_worktree(str(KDIR)):
        main_root = main_checkout_root(str(KDIR))
        if main_root is not None:
            return main_root / KDIR.name
    return KDIR


def main() -> None:
    data = read_hook_input()
    session_id = data.get("session_id", "unknown")
    transcript_path = data.get("transcript_path", "")
    if not transcript_path or not isinstance(transcript_path, str):
        return
    if not Path(transcript_path).exists():
        return

    context = extract_turns(transcript_path)
    if not context.strip() or context.count("\n**") + 1 < MIN_TURNS_TO_FLUSH:
        return

    root = effective_root()
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    context_file = scripts_dir / f"{CONTEXT_PREFIX}{session_id}-{stamp}.md"
    context_file.write_text(context, encoding="utf-8")

    cmd = ["uv", "run", "--directory", str(root), "python", "scripts/flush.py",
           str(context_file), session_id]
    env = {**child_env(), "KNOWLEDGE_ROOT": str(root)}
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    except OSError as e:
        sys.stderr.write(f"{LOG_TAG} failed to spawn flush.py: {e}\n")


if __name__ == "__main__":
    main()
