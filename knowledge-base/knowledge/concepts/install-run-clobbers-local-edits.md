---
title: "Install-Run-Only Side Effects on Local Edits"
aliases: [installer-side-effects, clobbered-hand-edits, prp-home-rewrite]
tags: [installer, side-effects, self-hosting, harness, gotcha]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-02
updated: 2026-09-02
---

# Install-Run-Only Side Effects on Local Edits

Re-running the harness installer overwrites some local edits, and it does so only
at install time — no other event triggers it. Three such effects were identified:
hand-edited hook timeouts below 60 are raised, a self-written `uv.lock` line in
`<install>/.gitignore` is deleted, and the compliance installer re-writes
`env.PRP_HOME`, which this repository's root `CLAUDE.md` forbids.

## Key Points

- Hand-edited hook timeouts **under** 60 are overwritten by the shipped floor;
  values above 60 survive.
- A user-added `uv.lock` rule in the installed `.gitignore` is removed by the new
  prune step, which cannot distinguish the harness's stale rule from a
  deliberately identical user rule.
- A re-run of the compliance installer writes `env.PRP_HOME` into this repo
  again, contradicting the root `CLAUDE.md`; it was stripped by hand in the
  self-host commit.
- All three fire only during an install run, which makes them easy to miss when
  reviewing a diff produced by any other workflow.

## Details

These are the cost side of making the installer repair existing installations
(see [[concepts/installer-merge-repairs-existing-installs]]). A merge that can
raise a value can overwrite an intentional lower one, and a prune that can retract
an obsolete rule can delete an identical rule a user added for their own reasons.
Neither is a bug in the merge logic; both are the unavoidable consequence of
giving the installer write authority over files it shares with the operator.

The `env.PRP_HOME` case is the self-hosting variant of the same problem: this
repository both ships the harness and installs it into itself, so generated
installer output can reintroduce configuration the repository's own rules
prohibit. Because the installer regenerates it on every run, manual stripping is a
recurring cleanup step rather than a one-time fix — the drift returns with the
next install. Separately, `env.PRP_HOME` was left unpersisted here because it
belongs to the `prp-store-symlink-wiring-and-stack-gate-blindness` plan in a
neighbouring worktree, keeping plan boundaries intact across concurrent work.

## Related Concepts

- [[concepts/installer-merge-repairs-existing-installs]] — the repair mechanisms whose side effects these are
- [[concepts/verify-generated-artifacts-before-commit]] — the same discipline of checking generated output before it lands
- [[connections/installer-repair-and-clobber]] — the shared mechanism behind repair and clobber

## Sources

- [[daily/2026-09-02.md]] — two install-run-only side effects; compliance installer re-writes forbidden `env.PRP_HOME`, stripped manually

