---
title: "Withholding `ANTHROPIC_API_KEY` Is Not an Egress Kill Switch"
aliases: [no-key-still-spawns, validate-mode-warn-gates-decision-only, issue-18-escape-hatch]
tags: [compliance-compiler, claude-agent-sdk, credentials, egress, gotcha]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# Withholding `ANTHROPIC_API_KEY` Is Not an Egress Kill Switch

Issue #18 assumed an operator could stop the compliance hook from talking to the
network by simply not supplying `ANTHROPIC_API_KEY`. That escape hatch does not
exist: `validate.py` runs under the `claude_code` preset, and the SDK starts the
CLI, which picks up subscription credentials of its own. The absence of a key is
not the absence of credentials.

## Key Points

- Omitting the API key does not prevent egress — the spawned CLI supplies its own
  subscription credentials.
- `validate_mode: warn` is not a second line of defence: it gates only the block
  decision (`pc["catalog_built"]`), not the spawn.
- The planned remedy is an inline-only config switch, plus documentation of what
  the hook still guarantees without deep validation.
- The degraded mode must be visible, because silently doing nothing would repeat
  the Issue #50 blind-gate failure.
- Issue #18 was ranked last in triage as design-heavy work, behind
  plugin-load-path and gate-correctness fixes (#19, #50) and the cost bug (#46) —
  prioritisation by blast radius rather than size.

## Details

The mistake is to reason about the SDK as if it were a direct API client, where
no key means no request. It is not: it launches a full Claude Code CLI as a child
process, and that CLI performs its own credential discovery. Removing one
credential from the environment therefore does not close the path; it just
changes which credential gets used. Any control that genuinely bounds egress has
to bound the process — whether it spawns at all — rather than a variable the
child can route around (see
[[connections/subprocess-auth-inheritance-compliance-and-containment]]).

`validate_mode: warn` fails for the analogous reason at a different layer. It
governs what the hook *does with* a validation result, not whether the validation
is performed, so switching it to `warn` leaves the network call fully intact and
only softens the consequence. Both misreadings assume a knob positioned after the
expensive step controls whether the expensive step happens.

## Related Concepts

- [[concepts/claude-agent-sdk-subprocess-architecture]] — the SDK-spawns-CLI mechanism behind this
- [[concepts/api-key-vs-subscription-for-account-apps]] — the same credential inheritance seen as a compliance bar
- [[concepts/blind-gate-silent-pass]] — why the degraded mode must announce itself
- [[connections/subprocess-auth-inheritance-compliance-and-containment]] — the two-sided reading of one mechanism

## Sources

- [[daily/2026-09-02.md]] — #18's escape hatch doesn't exist; `validate.py` runs under the `claude_code` preset and the SDK starts the CLI
