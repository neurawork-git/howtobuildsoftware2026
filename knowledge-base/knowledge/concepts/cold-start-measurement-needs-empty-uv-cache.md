---
title: "Measuring Hook Cold Start Requires an Empty uv Cache"
aliases: [uv-cache-cold-start, empty-uv-cache-dir, cold-start-measurement]
tags: [hooks, uv, performance, measurement, claude-code]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-02
updated: 2026-09-02
---

# Measuring Hook Cold Start Requires an Empty uv Cache

A hook's true cold-start cost is only observable when the `uv` cache is emptied,
not merely when `.venv` is missing. Timing `session-start.py` in a worktree that
lacked `.venv` but had a populated `UV_CACHE_DIR` gave 6.95 s; the same hook run
in a throwaway repo with an *empty* `UV_CACHE_DIR` took 11.28 s. The second
number is the one that matches the condition an outside reporter actually hits.

## Key Points

- Deleting `.venv` alone does not produce a cold start — `uv` still resolves from
  its cache, so the measurement understates the real cost by roughly 40%.
- Measured spread: 6.95 s (warm cache, no `.venv`) vs 11.28 s (empty
  `UV_CACHE_DIR`), the latter matching the 11.6 s reported in Issue #5.
- The 11.28 s run exited 0, so a warm-cache measurement would not merely be
  imprecise — it would have made the defect look absent against the old 10 s
  budget.
- Reproducing a reporter's environment means reproducing every layer of caching,
  not just the most visible one.

## Details

The `session-start.py` hook installs its Python dependencies through `uv`, which
maintains two independent layers of prior work: the project virtualenv (`.venv`)
and a global package cache (`UV_CACHE_DIR`). Removing only the first leaves the
second intact, so a "cold" run still skips download and resolution and finishes
in about 7 s. Because that figure sits comfortably under the old 10 s hook
timeout, a measurement taken this way reports a healthy hook while the reported
failure is real.

Clearing both layers in a disposable repository reproduced the reporter's
condition and produced 11.28 s, which independently corroborates the 11.6 s
figure in Issue #5 and places the hook squarely over the old budget (see
[[concepts/hook-timeout-sixty-second-budget]]). The general lesson is that a
performance measurement is only evidence about the environment it actually
recreates; the caching layer that was left warm is exactly the variable under
test.

## Related Concepts

- [[concepts/hook-timeout-sixty-second-budget]] — the budget these measurements sized
- [[concepts/timing-evidence-vs-observed-behavior]] — the other half of what makes a cold-start proof valid
- [[connections/installer-repair-and-clobber]] — the install run whose behavior these hook timeouts govern

## Sources

- [[daily/2026-09-02.md]] — 6.95 s vs 11.28 s; uv cache must be emptied to hit the reporter's condition

