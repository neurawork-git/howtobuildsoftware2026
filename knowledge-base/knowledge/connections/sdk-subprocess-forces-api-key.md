---
title: "Connection: SDK Subprocess Model and the API-Key Requirement"
connects:
  - "concepts/claude-agent-sdk-subprocess-architecture"
  - "concepts/api-key-vs-subscription-for-account-apps"
sources:
  - "daily/2026-08-13.md"
created: 2026-08-20
updated: 2026-08-20
---

# Connection: SDK Subprocess Model and the API-Key Requirement

## The Connection

The Claude Agent SDK authenticates by spawning the Claude Code CLI, and the CLI
natively supports a personal subscription/OAuth login. Yet GrillMe — an app with
its own accounts — is barred from that login path and must feed the wrapped CLI
an explicit API key instead.

## Key Insight

The non-obvious part is that the SDK's convenience (reusing the CLI's existing
auth) is exactly what you must *not* use here. Because the SDK is a thin wrapper
over the CLI, it inherits the CLI's OAuth-login capability for free — but the
moment the software exposes accounts to end users, that inherited path becomes
non-compliant, and the shared/per-user API key must be injected instead. The
packaging decision (ship the CLI in the container) and the credentials decision
(API key, not OAuth) are therefore coupled: the same subprocess that makes the
CLI's login available is the one that must be pointed at a key.

## Evidence

The 2026-08-13 session recorded both facts together: the backend needs Node +
`@anthropic-ai/claude-code` because the SDK spawns the CLI as a subprocess, and —
as a distinct lesson — subscription/OAuth login is "not sanctioned for an app
with accounts, even self-hosted — must use API key." GrillMe resolves this with a
single shared `ANTHROPIC_API_KEY` in `.env` for v1 and an optional per-user
`anthropic_api_key` column for later.

## Related Concepts

- [[concepts/claude-agent-sdk-subprocess-architecture]]
- [[concepts/api-key-vs-subscription-for-account-apps]]
- [[concepts/connection-articles-enable-backward-retrieval]] — this article is probe #3's target: the non-obvious link a forward-only agent would miss
