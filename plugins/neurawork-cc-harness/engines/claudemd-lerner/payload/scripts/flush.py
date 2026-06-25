"""Distil one session's context into today's daily log (background process).

Spawned by the SessionEnd / PreCompact hooks with a pre-extracted context file.
Uses the Claude Agent SDK (text-only, no tools) to decide what is worth keeping
for the docs, then appends the result to ``daily/<date>.md``. Does NOT trigger an
update — that is handled by the manual command and the SessionStart 6h gate.

Usage:
    uv run python scripts/flush.py <context_file.md> <session_id>
"""

from __future__ import annotations

# Recursion guard: mark any nested Claude Code spawned by the SDK so its hooks
# bail out. Must be set BEFORE importing the SDK.
import os

os.environ["CLAUDE_INVOKED_BY"] = "neurawork_cc_harness"

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # <ldir> for _shared

from config import DAILY_DIR, SCRIPTS_DIR, ROOT_DIR, load_cfg
from _shared.gitctx import repo_root
from _shared.repo_guard import assert_in_repo_not_dotclaude, WriteGuardError

DEDUP_FILE = SCRIPTS_DIR / "last-flush.json"
LOG_FILE = SCRIPTS_DIR / "flush.log"
DEDUP_WINDOW_SECONDS = 60

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROMPT = """Review the session context below and return a concise daily-log entry
capturing only what should eventually land in the project's CLAUDE.md or docs/.
Do NOT use any tools — return plain text.

Focus on durable, doc-relevant signal. Use these sections, omitting any that
would be empty:

**Context:** one line on what was being worked on.

**Conventions / Architecture:**
- a naming/structure/style rule or an architectural fact established this session

**Decisions Made:**
- decision with its rationale

**Commands:**
- a build/test/lint/run command worth recording

**Lessons Learned:**
- gotcha, pattern, or insight worth keeping in the docs

Skip routine tool calls, file reads, trivial back-and-forth, and anything that
does not belong in long-lived project documentation. If nothing is worth saving,
respond with exactly: FLUSH_OK

## Session Context

{context}"""


def _load_dedup() -> dict:
    if DEDUP_FILE.exists():
        try:
            return json.loads(DEDUP_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_dedup(state: dict) -> None:
    DEDUP_FILE.write_text(json.dumps(state), encoding="utf-8")


def append_to_daily(content: str, section: str) -> None:
    """Append an entry to today's daily log, guarded to stay in-repo."""
    today = datetime.now(timezone.utc).astimezone()
    log_path = DAILY_DIR / f"{today.strftime('%Y-%m-%d')}.md"

    try:
        assert_in_repo_not_dotclaude(log_path, repo_root(str(ROOT_DIR)) or ROOT_DIR)
    except WriteGuardError as e:
        logging.error("Refusing daily write: %s", e)
        return

    if not log_path.exists():
        DAILY_DIR.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"# Daily Log: {today.strftime('%Y-%m-%d')}\n\n## Sessions\n\n",
            encoding="utf-8",
        )

    entry = f"### {section} ({today.strftime('%H:%M')})\n\n{content}\n\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


async def run_flush(context: str) -> str:
    """Text-only SDK call returning the distilled entry (or FLUSH_OK/FLUSH_ERROR)."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    cfg = load_cfg()
    response = ""
    try:
        async for message in query(
            prompt=PROMPT.format(context=context),
            options=ClaudeAgentOptions(
                cwd=str(ROOT_DIR),
                allowed_tools=[],
                max_turns=2,
                setting_sources=[],
                strict_mcp_config=True,
                model=(cfg.get("model") or None),
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response += block.text
            elif isinstance(message, ResultMessage):
                cost = message.total_cost_usd or 0.0
                logging.info("Flush cost: $%.4f", cost)
    except Exception as e:
        import traceback

        logging.error("SDK error: %s\n%s", e, traceback.format_exc())
        return f"FLUSH_ERROR: {type(e).__name__}: {e}"

    return response


def main() -> None:
    if len(sys.argv) < 3:
        logging.error("Usage: flush.py <context_file.md> <session_id>")
        sys.exit(1)

    context_file = Path(sys.argv[1])
    session_id = sys.argv[2]
    logging.info("flush.py start: session=%s context=%s", session_id, context_file)

    if not context_file.exists():
        logging.error("Context file missing: %s", context_file)
        return

    dedup = _load_dedup()
    if (
        dedup.get("session_id") == session_id
        and time.time() - dedup.get("timestamp", 0) < DEDUP_WINDOW_SECONDS
    ):
        logging.info("Skip duplicate flush for session %s", session_id)
        context_file.unlink(missing_ok=True)
        return

    context = context_file.read_text(encoding="utf-8").strip()
    if not context:
        logging.info("Empty context, skipping")
        context_file.unlink(missing_ok=True)
        return

    response = asyncio.run(run_flush(context))

    if "FLUSH_ERROR" in response:
        logging.error("Result: %s", response)
        append_to_daily(response, "Memory Flush")
    elif "FLUSH_OK" in response or not response.strip():
        logging.info("Result: FLUSH_OK")
    else:
        logging.info("Result: saved (%d chars)", len(response))
        append_to_daily(response, "Session")

    _save_dedup({"session_id": session_id, "timestamp": time.time()})
    context_file.unlink(missing_ok=True)
    logging.info("flush.py done: session=%s", session_id)


if __name__ == "__main__":
    main()
