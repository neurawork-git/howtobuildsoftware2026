---
title: "Verify Generated Artifacts Against Reality Before Committing"
aliases: [verify-llm-docs, claudemd-lerner-verification, verify-before-commit]
tags: [convention, verification, documentation, claudemd-lerner]
sources:
  - "daily/2026-08-27.md"
  - "daily/2026-09-02.md"
created: 2026-08-27
updated: 2026-09-03
---

# Verify Generated Artifacts Against Reality Before Committing

Machine-generated documentation is checked against the repository before it is
committed, not trusted on sight. When `claudemd-lerner` auto-generated three doc
files (`CLAUDE.md`, `docs/ARCHITECTURE.md`, and a new `stack-base/CLAUDE.md`),
each factual claim was confirmed against actual files and config before the
commit `910b0f9` landed.

## Key Points

- Three auto-generated docs were verified before commit `910b0f9`, not trusted
  because they looked plausible.
- Checks were concrete: confirmed `stack-base/scripts/validate.py` and
  `hooks/st-post-tooluse.py` exist, and that `validate_mode` default
  `{"prd": "warn", "plan": "warn"}` is a real key in `config.json` / `config.py`.
- Also confirmed the protected `neurawork-cc-harness:rules` marker block stayed
  intact — exactly one BEGIN/END pair, not duplicated or dropped.
- The safeguard targets LLM-produced prose the same way opaque identifiers are
  checked against manifests: plausible ≠ correct.
- For generated *data*, the equivalent check is semantic rather than textual:
  a 137-line field-order diff in `compliance-base/catalog/stack.json` was
  verified by parsing both blobs as JSON and comparing key sets, values and field
  sets — 68 entries, 0 value changes, `generated` the only scalar difference.

## Details

LLM-generated docs read fluently whether or not they are accurate, so fluency is
no signal of correctness. The verification here was specific rather than a glance:
existence of referenced files, the actual default value of a config key, and the
integrity of a protected marker block that tooling relies on. Any of these could
have been silently wrong in generated text.

This is the same verify-before-trust discipline applied to plugin/marketplace
identifiers in [[concepts/plugin-manifest-name-verification]] — the source of a
claim (a human copy, an LLM, or memory) is treated as untrusted until checked
against an authoritative artifact in the repo. Both cases happened around the
same `0.3.1` bump round (see
[[concepts/plugin-version-bump-propagates-cache]]).

## Related Concepts

- [[concepts/plugin-manifest-name-verification]] — the same verify-against-ground-truth discipline for identifiers
- [[concepts/plugin-version-bump-propagates-cache]] — the bump round these doc commits accompanied
- [[concepts/timing-evidence-vs-observed-behavior]] — the same verify-against-reality discipline applied to a claimed runtime symptom
- [[concepts/install-run-clobbers-local-edits]] — generated installer output checked (and stripped) before it lands
- [[concepts/stale-generator-artifact-poisons-noop-checks]] — the structured-data case, where a stale tracked artifact defeats the check entirely
- [[concepts/drift-guard-scope-and-falsifiable-meta-tests]] — the automated form of the same discipline

## Sources

- [[daily/2026-08-27.md]] — LLM-generated docs verified against real files/config and intact marker block before commit
- [[daily/2026-09-02.md]] — semantic JSON comparison used instead of a line diff for a pure field-order change
