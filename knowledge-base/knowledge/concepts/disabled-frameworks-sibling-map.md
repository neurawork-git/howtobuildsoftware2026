---
title: "Sibling `disabled` Map Instead of a Per-Entry `enabled` Flag"
aliases: [disabled-map, mark-dont-omit, stack-choices-working-universe]
tags: [compliance-compiler, data-modelling, config, stack-json, design-decision]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# Sibling `disabled` Map Instead of a Per-Entry `enabled` Flag

Frameworks switched off by configuration move, with all eight decision fields
intact, into a sibling `disabled` map inside the same `stack.json` — rather than
staying in `choices` carrying an `enabled: false` flag. The deciding argument was
a read-site count: fifteen readers across both engines treat `stack["choices"]`
as the working universe, and moving entries out of that key leaves all fifteen
correct without touching any of them.

## Key Points

- Disabled frameworks are relocated, not deleted: all eight decision fields
  travel with them into a `disabled` map in the same file.
- A per-entry `enabled: false` flag was rejected because each of the fifteen
  readers would have to honour it, and the one site that forgot would reproduce
  precisely the bug being fixed (Issue #46 — `stack.py` never calls `load_cfg()`,
  `stack.py:76`).
- `main()` partitions the catalog once at load time by `cfg["frameworks"]`;
  re-enabling costs one config line plus a `--scaffold` run, with no LLM call.
- Precedent for the pattern already existed in the same file: `applicable: false`
  plus `applicability_reason` — mark rather than omit.
- The user's design constraint framed the choice: delete nothing, keep one
  complete file, let config switch things on and off.

## Details

The two candidate representations are behaviourally equivalent only if every
consumer is updated. A flag makes correctness depend on discipline distributed
across fifteen call sites, indefinitely into the future; relocating the entries
makes correctness a property of the data shape, so consumers that were written
before the feature existed remain right by construction. Choosing the
representation that keeps existing readers correct without modification is the
cheaper and more durable option, particularly when the defect under repair is
itself an omitted read (`load_cfg()` was never called at all).

Diagnosis also narrowed where the fix belonged. Two of the three locations the
issue suspected were falsified: `merge_preserving` is correct as written, and
`scope_lib` is only a propagation path, not a decision point. Keeping the
disabled entries in the same file rather than dropping them is what makes
re-enabling free — the decision fields are still on disk to be moved back, which
is exactly the property a naive catalog filter would have destroyed (see
[[concepts/catalog-filter-destroys-carried-forward-decisions]]).

## Related Concepts

- [[concepts/catalog-filter-destroys-carried-forward-decisions]] — the data loss this representation avoids
- [[concepts/blind-gate-silent-pass]] — the silent failure mode a forgotten flag site would produce
- [[concepts/stale-generator-artifact-poisons-noop-checks]] — the tracked `stack.json` this scheme writes

## Sources

- [[daily/2026-09-02.md]] — disabled frameworks move to a sibling map because 15 readers treat `stack["choices"]` as the working universe
