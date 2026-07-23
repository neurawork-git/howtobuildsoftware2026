---
title: "Knowledge Compile Idempotency"
aliases: [compile-skip-processed, idempotent-compile]
tags: [knowledge-base, compiler, idempotency]
sources:
  - "daily/2026-07-02.md"
created: 2026-07-23
updated: 2026-07-23
---

# Knowledge Compile Idempotency

The knowledge compiler skips daily logs whose concepts already appear in the
index, so re-running a compile does not reprocess or duplicate earlier work.
When `2026-07-02.md` was compiled, `2026-06-25.md` was left untouched because its
concepts were already present in `index.md`; only the new log was compiled.

## Key Points

- Already-processed daily logs are skipped on subsequent compile runs.
- The `index.md` catalog is the signal for what has already been compiled.
- A manual compile of `2026-07-02.md` produced 3 articles at a cost of $0.21.
- Idempotency keeps the base current without re-spending on prior logs.

## Details

The compiler reads `index.md` before doing work, and treats a daily log as done
when its concepts are already catalogued there. This makes compilation
idempotent: pointing the compiler at the whole `daily/` directory only advances
the frontier of unprocessed logs rather than rebuilding existing articles. In
the 2026-07-02 session, this is exactly what happened — `2026-06-25.md` was
recognized as already compiled (its plugin/README concepts were in the index)
and skipped, while `2026-07-02.md` was compiled fresh into 3 articles.

This property is what lets the session-capture pipeline run automatically: each
new day's log is captured by the `SessionEnd` hook, and a later compile picks up
only the new material. The cost figure ($0.21 for one log → 3 articles) reflects
that only the incremental log was processed.

## Related Concepts

- [[concepts/sessionend-hook-triggers]] — the hook that captures the daily logs this compile consumes
- [[concepts/session-end-reason-ignored]] — the capture implementation feeding the compiler

## Sources

- [[daily/2026-07-02.md]] — 2026-06-25.md skipped as already-processed; only 2026-07-02.md compiled
