"""Marker-block guard — keep tool-owned blocks byte-identical across a learner run.

A marker block is text delimited by an HTML comment pair carrying the same
``owner:name`` id::

    <!-- neurawork-cc-harness:rules BEGIN (auto-managed — ...) -->
    ...block body...
    <!-- neurawork-cc-harness:rules END -->

Those bytes belong to the tool that wrote them, not to the learner. The learner's
SDK call runs with ``permission_mode="acceptEdits"``, so nothing can intercept an
edit before it lands — the only reliable defence is to snapshot every span before
the run and splice the original back afterwards.

Deliberately generic in the marker id: a repo carrying another tool's managed block
(e.g. ``coding-suite:coding-discipline-init``) is protected by the same pass, at no
extra cost.

Pure stdlib, no SDK import, no config import — every function here is unit-testable
without an LLM.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# `<!-- owner:name BEGIN ...anything... -->` — the trailing prose is part of the span.
_BEGIN_RE = re.compile(
    r"<!--\s*(?P<id>[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+)\s+BEGIN\b.*?-->",
    re.DOTALL,
)


def _end_re(marker_id: str) -> re.Pattern[str]:
    return re.compile(r"<!--\s*" + re.escape(marker_id) + r"\s+END\b.*?-->", re.DOTALL)


def find_spans(text: str) -> list[tuple[str, int, int]]:
    """Return ``(marker_id, start, end)`` for every well-formed block in ``text``.

    ``start``/``end`` cover the BEGIN and END comments themselves, so the markers are
    protected too — a model that keeps the body but rewrites the BEGIN comment is
    still caught. A BEGIN whose END is missing is NOT a span: guessing its extent
    could swallow real content. Callers see it through :func:`unmatched_ids`.

    A BEGIN is only paired with an END that no LATER same-id BEGIN precedes. Without
    that check, prose merely *mentioning* a marker (documentation does exactly this)
    would swallow everything up to the next real block's END, and the guard would then
    revert every legitimate edit inside that stretch.
    """
    spans: list[tuple[str, int, int]] = []
    for begin in _BEGIN_RE.finditer(text):
        marker_id = begin.group("id")
        end = _end_re(marker_id).search(text, begin.end())
        if end is None:
            continue
        next_begin = next(
            (m for m in _BEGIN_RE.finditer(text, begin.end()) if m.group("id") == marker_id),
            None,
        )
        if next_begin is not None and next_begin.start() < end.start():
            continue  # this BEGIN is orphaned — the later one owns that END
        spans.append((marker_id, begin.start(), end.end()))
    return spans


def unmatched_ids(text: str) -> list[str]:
    """Marker ids whose BEGIN never got paired with an END.

    Compared by POSITION, not by id: a documentation line that mentions a marker is an
    unmatched BEGIN even when a real block with the same id exists further down, and
    that is precisely the case worth reporting.
    """
    matched = {start for _, start, _ in find_spans(text)}
    return sorted({m.group("id") for m in _BEGIN_RE.finditer(text) if m.start() not in matched})


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def snapshot(paths) -> dict[Path, dict[str, str]]:
    """Record the exact span text of every marker block in ``paths``.

    Unreadable or missing files are skipped rather than raised: this runs around a
    background hook, where a crash is worse than an unguarded file. A duplicated
    marker id keeps its first span only — :func:`restore` reports the duplication
    instead of guessing which copy is authoritative.
    """
    snap: dict[Path, dict[str, str]] = {}
    for path in paths:
        path = Path(path)
        text = _read(path)
        if text is None:
            continue
        blocks: dict[str, str] = {}
        for marker_id, start, end in find_spans(text):
            blocks.setdefault(marker_id, text[start:end])
        if blocks:
            snap[path] = blocks
    return snap


def restore(snap: dict[Path, dict[str, str]]) -> list[str]:
    """Splice every changed marker span back to its snapshotted bytes.

    Returns one message per restoration or anomaly — the caller prints them, so a
    learner run that tried to eat a block is visible instead of silent. Text OUTSIDE
    the spans is never touched: the learner's real work must survive.
    """
    messages: list[str] = []
    for path, blocks in snap.items():
        text = _read(path)
        if text is None:
            messages.append(f"{path} disappeared during the run — cannot restore its blocks")
            continue

        original = text
        for marker_id, span_text in blocks.items():
            occurrences = [s for s in find_spans(text) if s[0] == marker_id]
            if len(occurrences) > 1:
                messages.append(
                    f"{path}: marker '{marker_id}' now appears {len(occurrences)} times — "
                    "restored the first block and left the extras; remove them by hand"
                )
            if not occurrences:
                if marker_id in unmatched_ids(text):
                    # An unpaired BEGIN with this id is still in the file — usually the
                    # block with its END comment dropped. Re-appending would duplicate
                    # the body that is still sitting there, so report instead: a loud
                    # message a human repairs beats a silent second copy.
                    messages.append(
                        f"{path}: marker block '{marker_id}' is broken — an unpaired BEGIN "
                        "remains; not re-appending (that would duplicate it). Repair by hand"
                    )
                    continue
                sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
                text = text + sep + span_text + "\n"
                messages.append(
                    f"{path}: marker block '{marker_id}' was removed — re-appended it"
                )
                continue
            _, start, end = occurrences[0]
            if text[start:end] != span_text:
                text = text[:start] + span_text + text[end:]
                messages.append(
                    f"{path}: marker block '{marker_id}' was edited — restored the original"
                )

        if text != original:
            _write_atomic(path, text)
    return messages
