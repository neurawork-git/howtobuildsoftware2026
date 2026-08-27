---
title: "Version Bump Propagates Engine Fixes to the Installed Plugin Cache"
aliases: [version-bump-propagation, plugin-cache-vs-engine-source, marketplace-pulls-on-version]
tags: [plugin, distribution, versioning, claude-code]
sources:
  - "daily/2026-08-27.md"
created: 2026-08-27
updated: 2026-08-27
---

# Version Bump Propagates Engine Fixes to the Installed Plugin Cache

Engine/payload source lives on `main`, but every installation runs from a
separate copy in the plugin cache. The marketplace only pulls a new copy when
the plugin's version number changes, so a source fix stays stranded in the repo —
never reaching an installed cache — until a version bump propagates it. A fix to
engine source therefore has no observable effect (including in `recon` output)
until the bump lands and the user runs `/plugin update` + `/reload-plugins`.

## Key Points

- The plugin cache is a distinct copy from the engine source on `main`; recon
  reports what the *cache* contains, not what `main` contains.
- The marketplace pulls only on a new version number — a payload/engine change
  without a bump never reaches installed caches.
- Concretely: the recon fix `ed1f45e` sat unused until the `0.3.0` → `0.3.1`
  bump (`04e4ba1`); after the bump plus `/plugin update` and `/reload-plugins`,
  recon correctly reported all **five** hooks (previously only three).
- The propagation path is: bump version → `/plugin update` → `/reload-plugins`.

## Details

Because installed plugins run from a cached copy rather than from repository
source, there are two places a change can live: committed to `main` and
propagated to the cache. Only the version number gates that propagation, so
committing an engine fix is necessary but not sufficient for users to see it.
This is why the `0.3.1` round existed at all — an earlier recon fix was already
on `main` but invisible in practice.

The bump was chosen as a patch precisely because the recon fix changed only what
recon *reports*, not any decision or payload behavior (see
[[concepts/semver-patch-for-reporting-only-change]]). This is the mechanism side
of the same marketplace distribution model documented for install commands in
[[concepts/plugin-marketplace-install]].

## Related Concepts

- [[concepts/plugin-marketplace-install]] — the marketplace distribution path this propagation rides on
- [[concepts/semver-patch-for-reporting-only-change]] — why this particular propagation was a patch bump
- [[concepts/verify-generated-artifacts-before-commit]] — the doc-verification done in the same bump round

## Sources

- [[daily/2026-08-27.md]] — engine source on main vs separate cache copy; marketplace pulls only on new version; recon reported five hooks after 0.3.1
