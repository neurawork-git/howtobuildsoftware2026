---
title: "Installer Merges That Repair Existing Installs: Monotonic Floor and Prune"
aliases: [merge-hooks-floor, monotonic-floor, prune-gitignore, repair-old-installs]
tags: [installer, idempotency, settings-merge, harness, convention]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-02
updated: 2026-09-02
---

# Installer Merges That Repair Existing Installs: Monotonic Floor and Prune

The harness installer is written so that a re-run fixes installations that
already exist, not only fresh ones. Two mechanisms carry this: `merge_hooks`
applies the shipped hook timeout as a *monotonic floor* rather than a fixed
assignment, and `prune_gitignore` was added as the removing counterpart to the
append-only `merge_gitignore` so obsolete rules can actually disappear.

## Key Points

- `merge_hooks` treats the shipped 60 s timeout as a floor: values below it are
  raised, values above it (hand-edited, intentionally larger) are left alone.
- A fixed assignment would have repaired old installs only by also destroying
  deliberate local increases; a floor does one without the other.
- `merge_gitignore` is append-only and therefore cannot retract anything, so the
  stale `uv.lock` rule in old installs needed a separate `prune_gitignore` to
  remove it.
- Both mechanisms take effect on the next install run — the install is the
  propagation event for a fix to an existing installation.

## Details

An installer that merges into user-owned files has to choose, per key, between
overwrite, leave-alone, and something in between. The monotonic floor is that
middle option: it encodes the intent "at least this much" instead of "exactly
this," which is the correct semantics for a timeout whose purpose is headroom
(see [[concepts/hook-timeout-sixty-second-budget]]). The result is that an
installation carrying the old 10 s value is repaired automatically, while an
operator who raised a timeout on purpose does not silently lose that change.

The gitignore case shows the same asymmetry from the other direction. An
append-only merge is safe by construction but can only ever grow the file, so a
rule that should no longer exist persists indefinitely in older installs. Adding
an explicit prune step gives the installer a retraction path, at the cost of
being able to delete lines a user wrote themselves — the risk documented in
[[concepts/install-run-clobbers-local-edits]]. Structurally this mirrors plugin
distribution, where a fix on `main` reaches an installation only at a defined
propagation moment (see
[[concepts/plugin-version-bump-propagates-cache]]).

## Related Concepts

- [[concepts/install-run-clobbers-local-edits]] — the destructive edge of the same merge run
- [[concepts/hook-timeout-sixty-second-budget]] — the 60 s value this floor propagates
- [[concepts/plugin-version-bump-propagates-cache]] — the analogous "fix reaches installs only on a propagation event" mechanism
- [[connections/installer-repair-and-clobber]] — why repair power and clobber power are the same mechanism

## Sources

- [[daily/2026-09-02.md]] — `merge_hooks` as monotonic floor; `prune_gitignore` introduced as the removing counterpart to append-only `merge_gitignore`

