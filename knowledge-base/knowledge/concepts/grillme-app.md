---
title: "GrillMe Requirements-Interview App"
aliases: [grillme, grill-me-app]
tags: [project, requirements, architecture]
sources:
  - "daily/2026-08-13.md"
created: 2026-08-20
updated: 2026-08-20
---

# GrillMe Requirements-Interview App

GrillMe is a local, self-hostable tool where a logged-in user starts a session
and is interviewed — a design-tree, round-based questioning flow — that refines a
raw idea into structured requirements. Inputs are multi-modal (text, microphone,
image); the primary output is an exportable Markdown spec, from which 1..n
tickets per session are derived.

## Key Points

- Round-based "grilling" interview refines a raw idea into requirements via a
  persisted design tree.
- Inputs: text, microphone (speech-to-text), and image.
- Primary artifact is an exportable Markdown spec; tickets (1..n per session)
  are derived from it, with GitHub Issues integration as a clean second step.
- Frontend is Next.js + React; backend is Python with a proper Postgres
  database; deployment is local Docker Compose.
- Single-user for v1 but built to extend to self-hosted teams — all data is
  scoped by `user_id` from day 1.
- Gamification ("Grillung"): titles like *Grillmeister* and stickers, counted on
  session completion with answered-question depth as a second metric.

## Details

The app is deliberately built single-user-now, multi-user-later: even in v1 with
one user, every row is scoped by `user_id` and the schema carries an optional
per-user `anthropic_api_key` column, so extending to a self-hosted team requires
no migration of the ownership model. Auth is email + password (Argon2) plus a
session cookie, with no public signup — users are created via CLI.

The interview engine is the Claude Agent SDK driving a vendored, customized
`grilling` skill (see
[[concepts/claude-agent-sdk-subprocess-architecture]]). The design tree is
persisted as JSON in Postgres, which is the single source of truth for session
state (see [[concepts/postgres-source-of-truth-replayed-sessions]]). Swappable
`Transcriber` and `Storage` interfaces keep speech-to-text and image storage
vendor-neutral (see [[concepts/swappable-backend-interfaces]]).

## Related Concepts

- [[concepts/claude-agent-sdk-subprocess-architecture]] — the grill engine and its container requirements
- [[concepts/postgres-source-of-truth-replayed-sessions]] — how session state survives restarts and resumes
- [[concepts/swappable-backend-interfaces]] — the Transcriber and Storage abstractions
- [[concepts/editable-transcript-before-send]] — protecting the design tree from dictation errors
- [[concepts/api-key-vs-subscription-for-account-apps]] — why the grill engine authenticates with an API key

## Sources

- [[daily/2026-08-13.md]] — the grilling/requirements session that scoped the app
