---
title: "Patch Bump for a Reporting-Only Change"
aliases: [semver-patch-decision, reporting-only-patch, patch-vs-minor]
tags: [versioning, semver, convention, plugin]
sources:
  - "daily/2026-08-27.md"
created: 2026-08-27
updated: 2026-08-27
---

# Patch Bump for a Reporting-Only Change

The `neurawork-cc-harness` plugin was bumped `0.3.0` → `0.3.1` (a patch) because
the shipped change altered only what `recon` *reports*, not what any component
*decides* or how the payload/engine/install behaves. The governing rule: a fix
that changes observed output without changing behavior is patch-level.

## Key Points

- `0.3.0` → `0.3.1` was chosen as a patch, committed as `04e4ba1` on `main`.
- Rationale: the recon fix (`ed1f45e`) only affects recon's report; it does not
  decide anything, and payload/engine/install behavior was unchanged.
- The distinction applied is behavior-change vs report-change — the latter is
  patch-worthy, not minor.

## Details

Semantic-versioning judgement here turned on a specific question: does the change
alter behavior or merely the description of behavior? Recon's job is to report
the harness's hooks; the fix made that report accurate (five hooks instead of
three) without changing any hook, decision path, or install surface. That places
it squarely in patch territory rather than a minor feature bump.

The bump was not cosmetic despite being reporting-only: without *any* version
increment the fix would never reach installed caches (see
[[concepts/plugin-version-bump-propagates-cache]]). So the smallest correct bump —
a patch — was both semantically accurate and operationally necessary.

## Related Concepts

- [[concepts/plugin-version-bump-propagates-cache]] — why even a reporting-only fix needs a version increment to ship
- [[concepts/plugin-marketplace-install]] — the versioned plugin these numbers belong to

## Sources

- [[daily/2026-08-27.md]] — bumped 0.3.0 → 0.3.1 as patch because recon fix only affects what recon reports
