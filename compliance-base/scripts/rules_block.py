"""Reader for the `neurawork-cc-harness:rules` block in a repo's root ``CLAUDE.md``.

`/neurawork-cc-harness:nw-rules-init` writes one marker-delimited block whose
Evaluation-first bullet ends with ``Run:`` and is followed by a fenced code block —
one test command per line::

    <!-- neurawork-cc-harness:rules BEGIN (auto-managed — ...) -->
    ...
    - **Evaluation first** — ... Run:

    ```sh
    python3 -m unittest discover -s tests
    ```
    <!-- neurawork-cc-harness:rules END -->

That fence is the repo's single authoring place for its test command. This module is
the only Python parser of it; ``/nw-ship-pr``'s Phase 4.5 reads the same fence with
``sed`` for its validation gate.

Pure stdlib, no I/O beyond one file read, and nothing here raises: it runs on the
PostToolUse hook path, where a crash costs more than a missing signal.

The marker regexes MIRROR ``claudemd-lerner/payload/scripts/markers.py`` rather than
importing it — the two live in different installs, so neither is on the other's
``sys.path`` in a target repo. Change one, change the twin; the marker id is pinned
from both sides by ``plugins/neurawork-cc-harness/tests/test_skill_assets.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

MARKER_ID = "neurawork-cc-harness:rules"

_BEGIN_RE = re.compile(
    r"<!--\s*" + re.escape(MARKER_ID) + r"\s+BEGIN\b.*?-->", re.DOTALL
)
_END_RE = re.compile(r"<!--\s*" + re.escape(MARKER_ID) + r"\s+END\b.*?-->", re.DOTALL)
# A fence opener: three-or-more backticks plus an optional language tag, nothing else.
_FENCE_RE = re.compile(r"^\s*(?P<ticks>`{3,})[A-Za-z0-9_+-]*\s*$")


def find_block(text: str) -> str | None:
    """The text between the BEGIN and END markers, or ``None`` when there is no span.

    Like the learner's guard, a BEGIN whose END is missing is not a span: guessing its
    extent could swallow the rest of the file. The FIRST well-formed span wins — the
    skill's "never write a second block" rule makes a second one a repair job, not
    something to resolve here.
    """
    begin = _BEGIN_RE.search(text)
    if begin is None:
        return None
    end = _END_RE.search(text, begin.end())
    if end is None:
        return None
    return text[begin.end():end.start()]


def test_commands(claudemd_text: str) -> list[str]:
    """The command lines of the FIRST fenced block inside the rules span, in order.

    No span, no fence, or an empty fence → ``[]``. An absent fence is a legitimate
    state: the skill ships the Evaluation-first bullet without one when it could not
    detect a runner and the user declined to name it.
    """
    block = find_block(claudemd_text)
    if block is None:
        return []
    commands: list[str] = []
    closing: str | None = None
    for line in block.splitlines():
        if closing is None:
            m = _FENCE_RE.match(line)
            if m:
                closing = m.group("ticks")
            continue
        if line.strip().startswith(closing):
            break
        stripped = line.strip()
        if stripped:
            commands.append(stripped)
    return commands


def read(repo_root: Path | str) -> list[str]:
    """``test_commands`` of ``<repo_root>/CLAUDE.md`` — ``[]`` when it cannot be read."""
    try:
        text = (Path(repo_root) / "CLAUDE.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return test_commands(text)
