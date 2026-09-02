---
title: "Connection: Installer Repair Power and Clobber Power Are the Same Mechanism"
connects:
  - "concepts/installer-merge-repairs-existing-installs"
  - "concepts/install-run-clobbers-local-edits"
sources:
  - "daily/2026-09-02.md"
created: 2026-09-02
updated: 2026-09-02
---

# Connection: Installer Repair Power and Clobber Power Are the Same Mechanism

## The Connection

The two installer decisions of this session — a monotonic timeout floor and a new
gitignore prune — were made to repair installations that already exist. The two
documented side effects — hand-edited timeouts being raised, a user's `uv.lock`
line being deleted — are not separate defects introduced alongside them. They are
the same two writes, seen from the operator's side.

## Key Insight

Reach into a user-owned file and the capability is symmetric: any merge strong
enough to correct a stale value is strong enough to overwrite an intentional one,
and any prune able to retract an obsolete rule is able to delete an identical rule
the user wrote. The design question is therefore not "repair or don't repair" but
*where to put the asymmetry* — and the monotonic floor is exactly such an
asymmetry, chosen so the capability points in one direction only. It repairs
values below 60 while declining to touch values above it, converting a symmetric
write into a directional one. `prune_gitignore` has no equivalent guard, which is
precisely why its side effect is the sharper of the two: a line is either present
or absent, with no ordering to exploit.

A second consequence follows from the timing. Both the repair and the clobber
fire only during an install run, so they never appear in a diff produced by
ordinary work; an operator sees a working install silently change only at the
moment they re-run the installer. This is what makes the self-hosting case
recurring rather than one-off — the compliance installer re-writes `env.PRP_HOME`
on every run, so stripping it is maintenance, not a fix.

## Evidence

From the 2026-09-02 session: `merge_hooks` was defined as a monotonic floor
specifically so the shipped 60 s "repairs existing installs on the next run
instead of only fresh ones," and in the same log the corresponding side effect is
recorded as "hand-edited hook timeouts under 60 are overwritten."
`prune_gitignore` was introduced "so the `uv.lock` rule disappears from old
installs," and its side effect is that "a self-set `uv.lock` line in
`<install>/.gitignore` is deleted." Both pairs are one behavior described twice.
The third instance is the self-host case: re-running the compliance installer
writes `env.PRP_HOME` again, which the root `CLAUDE.md` forbids, and it had to be
stripped by hand in the self-host commit.

## Related Concepts

- [[concepts/installer-merge-repairs-existing-installs]]
- [[concepts/install-run-clobbers-local-edits]]
- [[concepts/hook-timeout-sixty-second-budget]] — the 60 s value that both the floor and the clobber act on
- [[concepts/plugin-version-bump-propagates-cache]] — the same "installs change only at a defined propagation event" structure

