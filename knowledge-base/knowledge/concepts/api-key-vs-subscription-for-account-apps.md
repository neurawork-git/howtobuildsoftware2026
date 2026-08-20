---
title: "API Key Required for Apps with Accounts (Not Subscription OAuth)"
aliases: [api-key-not-oauth, no-subscription-login, anthropic-api-key-required]
tags: [claude-agent-sdk, authentication, credentials, licensing]
sources:
  - "daily/2026-08-13.md"
created: 2026-08-20
updated: 2026-08-20
---

# API Key Required for Apps with Accounts (Not Subscription OAuth)

Subscription/OAuth login is not sanctioned for an application that has its own
user accounts — even a self-hosted one. Such an app must authenticate to
Anthropic with an API key, not by riding a personal Claude subscription login.

## Key Points

- Apps with accounts must use an `ANTHROPIC_API_KEY`, not subscription/OAuth
  login, even when self-hosted.
- GrillMe v1 uses a single shared `ANTHROPIC_API_KEY` in `.env`, while the schema
  already carries an optional per-user `anthropic_api_key` column from day 1.
- Token usage is logged per session to attribute cost.

## Details

Although the Claude Agent SDK wraps the Claude Code CLI, which can otherwise
authenticate via a subscription OAuth login, that path is disallowed once the
software exposes its own accounts to end users. The compliant approach is an API
key, supplied via environment configuration.

GrillMe threads the needle between simplicity and future multi-tenancy: v1 runs
on one shared key in `.env`, but the database schema includes an optional
per-user `anthropic_api_key` column so individual users can later supply their
own credentials without a migration. This mirrors the app's broader
build-single-user-now, extend-to-teams-later stance.

## Related Concepts

- [[concepts/claude-agent-sdk-subprocess-architecture]] — the wrapped CLI that must authenticate this way
- [[concepts/grillme-app]] — the account-bearing app subject to this constraint

## Sources

- [[daily/2026-08-13.md]] — subscription/OAuth not sanctioned for an app with accounts; must use API key
