---
title: "Connection: Session Capture and Compile Idempotency"
connects:
  - "concepts/sessionend-hook-triggers"
  - "concepts/knowledge-compile-idempotency"
sources:
  - "daily/2026-07-02.md"
created: 2026-07-23
updated: 2026-07-23
---

# Connection: Session Capture and Compile Idempotency

## The Connection

Two independent mechanisms compose into a single hands-off pipeline: the
`SessionEnd` hook captures each finished session into a daily log, and the
idempotent compiler later turns only the new logs into knowledge articles. The
hook is the producer; the compiler is the consumer that never reprocesses what
it has already catalogued.

## Key Insight

The pipeline stays correct precisely because the two halves make no assumptions
about each other. The capture side writes every session uniformly — it does not
even branch on the hook's `reason` field (see
[[concepts/session-end-reason-ignored]]) — so it may append the same day's log
repeatedly. The compile side absorbs that safely because idempotency keys off
`index.md`, not off how many times capture ran. Neither side needs to coordinate
state; the index is the sole source of truth for "what is already knowledge."

## Evidence

In the 2026-07-02 session, a manual compile skipped `2026-06-25.md` (its
concepts were already in the index) and processed only `2026-07-02.md` into 3
articles for $0.21. This demonstrates the consumer side ignoring already-captured
logs while advancing on new ones — the exact behavior that lets the `SessionEnd`
capture run on every session end without causing duplicate compilation.

## Related Concepts

- [[concepts/sessionend-hook-triggers]]
- [[concepts/knowledge-compile-idempotency]]
- [[concepts/session-end-reason-ignored]]
