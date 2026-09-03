---
title: "60-Second Hook Timeout as the Cold-Start Budget"
aliases: [sixty-second-timeout, hook-timeout-budget, ten-second-budget-defect]
tags: [hooks, timeouts, uv, scope, claude-code]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-02
updated: 2026-09-03
---

# 60-Second Hook Timeout as the Cold-Start Budget

The harness ships a 60 s hook timeout, replacing an earlier 10 s budget that a
cold `uv` start overruns. With a measured cold start of 11.28 s the old budget
was exactly the defect (`Hook cancelled`), while 60 s leaves roughly 5x headroom.
That headroom is deliberately the single mitigation for cold-start cost — other
planned workarounds were dropped because the timeout already covers them.

## Key Points

- Old budget 10 s vs measured cold start 11.28 s — the hook was cancelled by a
  margin of about one second, not by a wide miss.
- Shipped budget is 60 s, ~5x the observed worst case.
- Issue #5 point 4 (falling back to plain `python3` for hooks when `uv` is
  absent) was deliberately **not** built and deliberately **not** tracked as a
  follow-up: the 60 s timeout makes it redundant.
- The same reasoning covers fresh installs into foreign repositories, which
  receive only `pyproject.toml` and no `uv.lock` and therefore keep paying a full
  dependency resolve.
- An independent finding reinforces dropping that fallback: naming `python3` in a
  hook command is not portable in the first place (see
  [[concepts/hook-interpreter-naming-not-portable]]).

## Details

Choosing a generous timeout rather than a faster hook is a deliberate trade: the
cost of a slow first run is bounded and one-off, whereas a `python3` fallback
path would add a second, permanently divergent execution mode to every hook. With
the real cold-start figure established (see
[[concepts/cold-start-measurement-needs-empty-uv-cache]]), 60 s absorbs both the
observed 11.28 s and a substantial safety factor, so the fallback was closed out
without leaving a follow-up ticket behind — an explicit decision that the item is
obsolete rather than deferred.

One consequence remains open rather than solved. The installer copies only
`pyproject.toml` into a target repository, not `uv.lock`, so a new install
elsewhere resolves dependencies from scratch on every cold start instead of
installing from a pinned lock. Lock tracking was scoped to this repository alone,
which leaves foreign installs relying entirely on the timeout for headroom; the
session left open whether to file that as a backlog item.

## Related Concepts

- [[concepts/cold-start-measurement-needs-empty-uv-cache]] — how the 11.28 s figure behind this budget was obtained
- [[concepts/installer-merge-repairs-existing-installs]] — how the 60 s value reaches installs that already have a lower one
- [[concepts/timing-evidence-vs-observed-behavior]] — the end-to-end run that confirmed the budget against real behavior
- [[concepts/hook-interpreter-naming-not-portable]] — why the dropped `python3` fallback was unworkable on its own terms

## Sources

- [[daily/2026-09-02.md]] — 10 s budget vs 11.28 s cold start, 60 s gives 5x headroom; Issue #5 point 4 dropped and untracked

