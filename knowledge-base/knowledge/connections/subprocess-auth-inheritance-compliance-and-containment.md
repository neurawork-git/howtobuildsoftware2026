---
title: "Connection: Subprocess Credential Inheritance as Compliance Bar and Containment Failure"
connects:
  - "concepts/claude-agent-sdk-subprocess-architecture"
  - "concepts/withholding-api-key-does-not-stop-egress"
sources:
  - "daily/2026-08-13.md"
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# Connection: Subprocess Credential Inheritance as Compliance Bar and Containment Failure

## The Connection

One mechanism — the Agent SDK spawns the Claude Code CLI, and that CLI performs
its own credential discovery — surfaced in two unrelated projects with opposite
signs. GrillMe must actively avoid the inherited subscription login, because an
app with its own accounts may not authenticate that way. The compliance engine
*cannot* avoid it: withholding `ANTHROPIC_API_KEY` fails to stop egress precisely
because the child finds credentials on its own.

## Key Insight

Credential inheritance cannot be declined by omission. Removing a key from the
environment is the intuitive off switch, and for a direct API client it would
work — no key, no request. A spawned CLI breaks that intuition, because the
absence of one credential is not the absence of credentials; it is a fallback to
a different one. GrillMe's rule and Issue #18's failed escape hatch are the same
fact read from opposite ends: the path GrillMe must take care not to use is
exactly the path #18 could not shut off.

The design consequence is that egress control has to attach to the spawn, not to
the environment. Both failed attempts in the compliance case sit downstream of
the process launch — the missing key would have been consumed by the child, and
`validate_mode: warn` governs only the block decision (`pc["catalog_built"]`),
not whether `validate.py` runs. A knob placed after the expensive step cannot
decide whether the expensive step happens, which is why the remedy became an
inline-only config switch: something that prevents the launch rather than
softening its outcome.

## Evidence

From 2026-08-13: the Python Agent SDK spawns the Claude Code CLI as a subprocess,
and subscription/OAuth login is "not sanctioned for an app with accounts, even
self-hosted — must use API key," resolved with a shared `ANTHROPIC_API_KEY` plus
an optional per-user column. From 2026-09-02 triage: "#18's escape hatch doesn't
exist: withholding `ANTHROPIC_API_KEY` doesn't stop egress, because `validate.py`
runs under the `claude_code` preset and the SDK starts the CLI, picking up
subscription credentials." Two projects, two teams' worth of context, one
subprocess boundary.

## Related Concepts

- [[concepts/claude-agent-sdk-subprocess-architecture]]
- [[concepts/withholding-api-key-does-not-stop-egress]]
- [[concepts/api-key-vs-subscription-for-account-apps]] — the compliance-side rule this mechanism forces
- [[connections/sdk-subprocess-forces-api-key]] — the GrillMe-only reading of the same coupling
