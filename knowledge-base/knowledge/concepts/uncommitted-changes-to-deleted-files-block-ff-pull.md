---
title: "Uncommitted Changes to Upstream-Deleted Files Block a Fast-Forward Pull"
aliases: [ff-only-blocked, deleted-upstream-dirty-file, pull-ff-only-gotcha]
tags: [git, workflow, gotcha, worktree]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-02
updated: 2026-09-02
---

# Uncommitted Changes to Upstream-Deleted Files Block a Fast-Forward Pull

`git pull --ff-only` refuses to advance when the working tree has uncommitted
modifications to a file that upstream has deleted, because applying the deletion
would discard those changes. The case occurred at
`knowledge-base/_shared/tests/test_version_check.py`, which two independent
changes had removed upstream: the #19 port to `node:test` and PR #49.

## Key Points

- The blocker is a local dirty file that no longer exists upstream — a fast
  forward would silently drop the edits, so git stops instead.
- The file was deleted twice over, by the `node:test` port (#19) and by PR #49's
  exclusion of plugin-only `_shared` tests from installer copies.
- Resolution requires an explicit decision about the local work: commit it
  elsewhere, discard it, or save it outside the tree.
- Here the local version (+18 lines, a stack-compiler stale test) was backed up
  to a scratchpad path under `/tmp`, with the note that if it is still wanted it
  belongs ported to `hooks/version-check.test.js`.

## Details

The failure mode is easy to misread as a merge conflict, but nothing conflicts in
the history — the conflict is between the incoming deletion and unsaved local
state. It is more likely during periods when a file is being migrated, since a
migration deletes the old location while ongoing local work still targets it. Two
separate upstream deletions converging on the same path made this particularly
likely.

The durable part of the incident is what happened to the stranded content rather
than the git mechanics: a local test that had value was preserved out-of-tree
instead of being dropped with the deletion, and its intended destination was
recorded. A `/tmp` scratchpad is not durable storage, so an item like this stays
an open follow-up until the test is either ported to the new `node:test` location
or explicitly abandoned.

## Related Concepts

- [[concepts/timing-evidence-vs-observed-behavior]] — the same PR whose test-exclusion change deleted this file
- [[concepts/install-run-clobbers-local-edits]] — the other way local work was at risk of being overwritten in this session

## Sources

- [[daily/2026-09-02.md]] — `pull --ff-only` blocked by dirty `test_version_check.py`, deleted by both the #19 `node:test` port and #49; local test backed up to a scratchpad

