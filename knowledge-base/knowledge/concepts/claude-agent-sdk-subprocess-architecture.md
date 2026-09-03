---
title: "Claude Agent SDK Spawns Claude Code CLI as a Subprocess"
aliases: [agent-sdk-subprocess, claude-code-cli-subprocess, fat-image]
tags: [claude-agent-sdk, claude-code, python, deployment]
sources:
  - "daily/2026-08-13.md"
  - "daily/2026-09-02.md"
created: 2026-08-20
updated: 2026-09-03
---

# Claude Agent SDK Spawns Claude Code CLI as a Subprocess

The Python Claude Agent SDK does not talk to the API directly; it wraps the
Claude Code CLI and spawns it as a subprocess. As a consequence, a backend
container that uses the SDK must ship Node and the `@anthropic-ai/claude-code`
package alongside Python — a "fat image" carrying two runtimes.

## Key Points

- The Python Agent SDK is a wrapper over the Claude Code CLI, invoked as a child
  process — not a thin HTTP client.
- The backend Docker image therefore needs Node + `@anthropic-ai/claude-code` in
  addition to the Python runtime.
- In GrillMe this SDK drives a vendored, customized `grilling` skill that must be
  changed to output a spec + tickets, not just an interview.
- A license check is required before vendoring third-party skill text (the
  `mattpocock-skills` `grilling` skill) into the repo.
- The spawned CLI does its own credential discovery, so an unset
  `ANTHROPIC_API_KEY` does not prevent it from running or reaching the network
  (see [[concepts/withholding-api-key-does-not-stop-egress]]).

## Details

Because the SDK shells out to the CLI, the deployment unit is heavier than a
pure-Python service: both language runtimes and the CLI package must be present
in the same container. This is a concrete packaging constraint for any
Docker-based deployment that embeds the Agent SDK, and it shaped GrillMe's
backend image.

The engine runs a vendored copy of a third-party `grilling` skill rather than the
stock skill, so it can emit the exportable Markdown spec and derived tickets that
the app needs. Vendoring third-party skill text raises a licensing question that
must be resolved before the text lands in the repository.

## Related Concepts

- [[concepts/grillme-app]] — the app whose grill engine is built on this SDK
- [[concepts/postgres-source-of-truth-replayed-sessions]] — the disposable sessions this subprocess model runs
- [[concepts/api-key-vs-subscription-for-account-apps]] — how the wrapped CLI must authenticate here
- [[concepts/withholding-api-key-does-not-stop-egress]] — the containment consequence of the same subprocess boundary
- [[connections/subprocess-auth-inheritance-compliance-and-containment]] — one mechanism, two opposite failures

## Sources

- [[daily/2026-08-13.md]] — SDK wraps the CLI as a subprocess; backend needs Node + Python
- [[daily/2026-09-02.md]] — the spawned CLI picks up subscription credentials, so withholding a key does not stop it
