---
title: "Filtering a Generator's Input Destroys Decisions It Only Carries Forward"
aliases: [filter-not-prune, scaffold-decision-loss, empty-universe-guard]
tags: [compliance-compiler, data-loss, generators, stack-json, gotcha]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# Filtering a Generator's Input Destroys Decisions It Only Carries Forward

`stack.py --scaffold` preserves prior decision fields only for keys that appear
in the *current* `stack.json` (`stack.py:185,193`). A framework filtered out of
the catalog therefore loses `chosen`, `rationale`, `scoped_from` and `ranked` in
a single run, and re-enabling it plus re-scaffolding brings the key back empty.
This was verified live; the lost values are recoverable only out-of-band through
git.

## Key Points

- Carry-forward is keyed on the current output file, so removing a key from the
  input silently drops everything the generator would have copied for it.
- One `--scaffold` run is enough to lose four decision fields; the round trip
  (disable → re-enable → re-scaffold) returns an empty key rather than the
  original decision.
- The intended semantics are therefore a **filter, not a prune**:
  `capabilities.json` retains every derived framework so re-enabling is free,
  while `config["frameworks"]` selects only what gets processed.
- An empty framework set wipes `stack.json` entirely and exits **0** ("0 of 0,
  nothing to report") — `scope.py:394` has an empty-universe guard and `stack.py`
  has none; the plan closes that asymmetry.
- All-clear on a related worry: `capabilities_hash` is
  `file_hash(CAPABILITIES_JSON)` (`stack.py:640`), computed over file bytes and
  so decoupled from the in-memory filter — filtering cannot reopen a settled
  decision.

## Details

The hazard is structural rather than incidental. A generator that rewrites its
whole output each run has to reconstruct anything it wants to keep, and it can
only reconstruct what it can still see. Decision fields are expensive, human- and
LLM-derived state living in the generator's *output*, while the filter acts on
its *input* — so narrowing the input quietly narrows what survives the rewrite.
Nothing in the code path signals loss, because from the generator's point of view
it faithfully produced a complete file for the universe it was given.

The empty-universe case is the same failure at full scale, and it is worse for
exiting successfully: a configuration that selects no frameworks destroys the
file and reports "0 of 0, nothing to report" with status 0, which reads as a
clean run (see [[concepts/blind-gate-silent-pass]]). That `scope.py` already
guards this and `stack.py` does not is a reminder that a safety check written
into one engine does not propagate to its sibling on its own. The whole finding
is what forced the relocate-don't-remove representation in
[[concepts/disabled-frameworks-sibling-map]]. Reproducing it cost nothing:
`COMPLIANCE_ROOT` allows a fully network- and LLM-free end-to-end run in a
temporary directory, since `--scaffold`'s call graph is stdlib-only.

## Related Concepts

- [[concepts/disabled-frameworks-sibling-map]] — the representation chosen because of this hazard
- [[concepts/blind-gate-silent-pass]] — the exit-0 wipe as an instance of silent failure
- [[concepts/stale-generator-artifact-poisons-noop-checks]] — the other way this generator's tracked output misleads

## Sources

- [[daily/2026-09-02.md]] — `scaffold()` carries decision fields only for keys in the current `stack.json`; empty framework set wipes the file and exits 0
