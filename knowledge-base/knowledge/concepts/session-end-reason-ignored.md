---
title: "session-end.py Ignores the reason Field"
aliases: [reason-field-unread, uniform-session-capture]
tags: [claude-code, hooks, session-capture, implementation]
sources:
  - "daily/2026-07-02.md"
created: 2026-07-23
updated: 2026-07-23
---

# session-end.py Ignores the reason Field

The `session-end.py` hook script does not read the `SessionEnd` hook's `reason`
field. As a result all four reasons — `clear`, `logout`, `prompt_input_exit`,
and `other` — trigger the same capture behavior: the session is written into the
daily log identically regardless of why it ended.

## Key Points

- `session-end.py` never branches on `reason`; the field is present but unread.
- Every end reason produces the same outcome: session → daily log capture.
- Capture is therefore uniform and reason-agnostic by design.

## Details

Although the `SessionEnd` hook exposes a `reason` field with four possible
values (see [[concepts/sessionend-hook-triggers]]), the implementation chooses
not to differentiate them. Whether a session ended via `/clear`, a logout, an
explicit `prompt_input_exit`, or a terminal-close `other`, the script runs the
same capture path and appends the session to the current day's log.

This means the value of `reason` is informational at the contract level but has
no effect on behavior in this repository. Anyone expecting reason-specific
handling (for example, skipping capture on `logout`) would need to add that
branching explicitly — it is not present today.

## Related Concepts

- [[concepts/sessionend-hook-triggers]] — the hook contract and the four reason values this script ignores
- [[concepts/knowledge-compile-idempotency]] — the downstream compile step that consumes the captured log

## Sources

- [[daily/2026-07-02.md]] — noted that session-end.py does not read the reason field
