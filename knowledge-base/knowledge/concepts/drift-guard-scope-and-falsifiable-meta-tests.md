---
title: "Drift Guards: Registry Walk Scope and Falsifiable Meta-Tests"
aliases: [registry-walk-guard, errors-must-be-asserted, tracked-filter-blind-spot]
tags: [testing, meta-tests, drift, plugin, convention]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# Drift Guards: Registry Walk Scope and Falsifiable Meta-Tests

PR #52 replaced two per-engine drift guards with a single shared registry walk.
The old guards compared a strict subset of the payload — `*.py` only — so a
divergence in `seed_prompt.txt` could never be pinned, which is exactly the bug
PR #47 shipped; two of the four engines had no guard at all. The new walk's skip
tests additionally assert `result.errors == []`, because a meta-test that checks
only `skipped` and `failures` passes green when the walk itself crashes.

## Key Points

- The retired per-engine guards covered only `*.py`, a strict subset of what the
  registry walk covers — deleting them lost no coverage, and their narrow scope
  is why the `seed_prompt.txt` drift in PR #47 went unpinned.
- A meta-test asserting only `skipped`/`failures` is unfalsifiable against
  crashes: a missing `git` binary or a subprocess error outside a repository
  produced a green run. `errors` belongs in the assertion.
- Known blind spot, now recorded in the docstring rather than only in review
  conversation: an **untracked** file in the self-host stays invisible to the
  `git ls-files` filter — which is the guard's own definition, "untracked = not
  part of the install." The reverse case, a payload file gitignored in the
  self-host, fails loudly.
- Accepted costs of the new walk: it skips when `git` is absent from `PATH`, and
  it assumes the `<repo>/plugins/<plugin>` layout.
- A review mis-finding was corrected rather than carried: compliance's
  `catalog-seed` was never unprotected — `test_catalog_seed.py` has pinned its
  six files all along.

## Details

Both defects here are about the scope of a check being narrower than the claim it
appears to make. A guard named for drift that only compares Python files reads
like full coverage while leaving prompt text unguarded, and a meta-test that
reports on skips and failures reads like a verdict on the walk while being blind
to the walk not completing. In each case the check produced a green result for a
condition it had never examined — the same shape as
[[concepts/blind-gate-silent-pass]], one layer up in the test suite.

Consolidating four engines behind one walk also changes where coverage gaps can
hide. Previously the gaps were per-engine and invisible in aggregate (two engines
simply had nothing); now there is a single implementation whose limits can be
stated once, which is why the tracked-filter blind spot was written into the
docstring. Writing an accepted limitation down converts it from a defect a future
reviewer will rediscover into a documented boundary. The same session's decision
to name a piggybacking 315-line plan in the PR body as "published, not
implemented" rather than letting it ride along silently follows the same
principle.

## Related Concepts

- [[concepts/blind-gate-silent-pass]] — the same green-for-an-unexamined-condition failure in the gate
- [[concepts/timing-evidence-vs-observed-behavior]] — a review result that also overstated what had been checked
- [[concepts/verify-generated-artifacts-before-commit]] — the verify-against-reality discipline these guards automate
- [[connections/silence-read-as-success]] — the pattern uniting the three instances

## Sources

- [[daily/2026-09-02.md]] — PR #52 registry walk replacing `*.py`-only per-engine guards; skip tests now assert `result.errors == []`
