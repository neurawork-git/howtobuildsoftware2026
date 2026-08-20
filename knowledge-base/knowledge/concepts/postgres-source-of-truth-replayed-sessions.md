---
title: "Postgres as Source of Truth with Replayed Disposable Sessions"
aliases: [replayed-sessions, disposable-sdk-session, postgres-source-of-truth]
tags: [architecture, state-management, postgres, claude-agent-sdk]
sources:
  - "daily/2026-08-13.md"
created: 2026-08-20
updated: 2026-08-20
---

# Postgres as Source of Truth with Replayed Disposable Sessions

In GrillMe, Postgres is the single source of truth for interview state; the
Claude Agent SDK holds no durable state of its own. Each interview round spins up
a fresh, disposable SDK session that replays the persisted design-tree state plus
history, then is discarded. This makes sessions survive process restarts, support
multi-day resume, and extend cleanly to multiple users.

## Key Points

- The design tree is persisted as JSON in Postgres; the SDK session is
  ephemeral.
- Every round rebuilds context by replaying tree-state + history into a new
  session rather than keeping a long-lived agent alive.
- Statelessness of the agent is what enables restart-survival, multi-day resume,
  and future multi-tenancy.
- Token usage is logged per session; data is scoped by `user_id` from day 1.

## Details

Treating the persisted tree as authoritative and the agent session as disposable
decouples correctness from process lifetime: nothing important lives in memory,
so a crashed or restarted backend loses no progress. This pairs naturally with
the subprocess model of the SDK (see
[[concepts/claude-agent-sdk-subprocess-architecture]]) — a short-lived subprocess
per round is cheap to throw away when all state is reconstructed from Postgres.

The same design is what makes the single-user v1 forward-compatible with teams:
because state is keyed and replayed per session (and per `user_id`), adding users
does not change the ownership or resume model.

## Related Concepts

- [[concepts/grillme-app]] — the app whose session state this pattern governs
- [[concepts/claude-agent-sdk-subprocess-architecture]] — the disposable subprocess sessions being replayed into
- [[concepts/swappable-backend-interfaces]] — image paths persisted in Postgres alongside tree state

## Sources

- [[daily/2026-08-13.md]] — Postgres is source of truth; fresh disposable session replays tree-state + history each round
