---
title: "SessionEnd Hook Trigger Reasons"
aliases: [session-end-hook, sessionend-reasons]
tags: [claude-code, hooks, session-capture]
sources:
  - "daily/2026-07-02.md"
created: 2026-07-23
updated: 2026-07-23
---

# SessionEnd Hook Trigger Reasons

The Claude Code `SessionEnd` hook fires when a session ends and carries a
`reason` field describing why. The four reasons are `clear` (`/clear`),
`logout`, `prompt_input_exit` (Ctrl+C / Ctrl+D at the prompt), and `other`
(terminal close, pipe end). It does **not** fire on context compaction or on
login.

## Key Points

- `reason` takes one of four values: `clear`, `logout`, `prompt_input_exit`,
  `other`.
- Compaction is covered by the separate `PreCompact` hook, **not** `SessionEnd`.
- `/login` triggers `SessionStart` (with source `startup|resume|clear|compact`),
  not `SessionEnd`.
- The hook is the capture point that turns a finished session into a daily log
  entry.

## Details

`SessionEnd` is the terminal event in a Claude Code session lifecycle. Its
`reason` field distinguishes deliberate resets (`clear`, `logout`), an explicit
exit at the prompt (`prompt_input_exit`), and everything else (`other`, which
covers a closed terminal or a broken pipe). Knowing which reasons are and are
not covered matters because compaction and login are handled by different hooks
(`PreCompact` and `SessionStart` respectively) — assuming `SessionEnd` fires on
those events would miss or double-count captures.

In this repository the hook is the entry point of the session-capture pipeline:
when it fires, the session is written into a `daily/` log, which the compiler
later turns into knowledge articles. How the hook's script actually treats the
`reason` field is a separate implementation choice — see
[[concepts/session-end-reason-ignored]].

## Related Concepts

- [[concepts/session-end-reason-ignored]] — how `session-end.py` handles (or ignores) this field
- [[concepts/knowledge-compile-idempotency]] — the compile step that consumes the captured daily log

## Sources

- [[daily/2026-07-02.md]] — clarified when the SessionEnd hook fires and its four reasons
