---
title: "A Tracked Generator Artifact That Lags Its Generator Poisons No-Op Checks"
aliases: [stale-stack-json, regenerate-in-own-commit, semantic-diff-verification]
tags: [generators, git, verification, compliance-compiler, convention]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# A Tracked Generator Artifact That Lags Its Generator Poisons No-Op Checks

When a committed artifact falls behind the code that produces it, every later
"did this change anything?" check is contaminated: the next regeneration shows
churn that has to be re-adjudicated before any real difference can be read. The
stale `compliance-base/catalog/stack.json` had already made AC5 in PR #53 hard to
read, and was regenerated in a commit of its own (`ca30509`) so that 137 lines of
churn could not be mistaken for a behaviour change.

## Key Points

- Regeneration went into a dedicated commit, isolating mechanical churn from
  functional change in the history.
- The closing proof was a fresh `--scaffold` on `main` producing a zero diff —
  artifact and generator demonstrably agree again.
- For pure field-order diffs, semantic verification beats a line diff: parse both
  blobs as JSON and compare key sets, values and field sets. Here that showed 68
  entries, 0 value changes, and `generated` as the only scalar change.
- The same staleness appears one level up in planning artifacts: two agent notes
  in the plan (an outdated knowledge index, untracked test files) were already
  moot by the time they were actioned — plan notes need checking against current
  state before being implemented.
- Deliberately left outside the backlog: the LLM-free re-render of
  `capabilities.md`, a workaround step from Issue #46 that the plan explicitly
  excluded, pending a decision from the user.

## Details

A generated file under version control makes two claims at once — what the
generator produces, and what the repository believes it produces. While those
agree, a zero diff is meaningful evidence; once they drift, no regeneration can
be read cleanly, because the reviewer must first separate accumulated backlog
from the change under review. That is precisely how the stale `stack.json`
degraded an acceptance criterion in a prior PR, which is a good illustration that
the cost of staleness is paid by later work rather than by whoever let it drift.

The verification technique matters as much as the sequencing. A 137-line diff
consisting mostly of reordered fields is not reviewable by eye, and reviewing it
that way invites both false alarms and missed changes; parsing both versions and
comparing structurally reduces the question to one a reviewer can actually answer
— which is how "0 value changes, only `generated` differs" became a confirmed
statement rather than an assertion. This is the same discipline as
[[concepts/verify-generated-artifacts-before-commit]], applied to structured data
instead of prose.

## Related Concepts

- [[concepts/verify-generated-artifacts-before-commit]] — the same verify-generated-output discipline for docs
- [[concepts/catalog-filter-destroys-carried-forward-decisions]] — the generator whose tracked output this is
- [[concepts/disabled-frameworks-sibling-map]] — the change whose acceptance check the staleness obscured

## Sources

- [[daily/2026-09-02.md]] — stale `compliance-base/catalog/stack.json` regenerated in its own commit `ca30509`; zero-diff `--scaffold` on `main` as closing proof
