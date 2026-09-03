---
title: "Connection: Three Checks Whose Silence Was Read as Success"
connects:
  - "concepts/blind-gate-silent-pass"
  - "concepts/timing-evidence-vs-observed-behavior"
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# Connection: Three Checks Whose Silence Was Read as Success

## The Connection

A single day's work produced three checks in three unrelated subsystems whose
non-execution was indistinguishable from a pass: a gate hook that returned before
reaching its only `print`, a meta-test that asserted on `skipped` and `failures`
while the walk beneath it could crash, and a six-agent code review that returned
zero findings for a symptom nobody had actually observed.

## Key Insight

In each case an absence of negative evidence was consumed as positive evidence.
The asymmetry that hides this is intrinsic: a check that fires produces output
proportional to what it finds, so a check that finds nothing produces nothing —
which is byte-for-byte what a check that never ran produces. Reviewers are
therefore reading a null result and inferring which of two very different
histories generated it, with nothing in the artifact to tell them apart.

The three remedies converge on the same move, and it is not "strengthen the
check." `errors == []` was added so that a crashed walk becomes a distinct
outcome rather than a silent one; Issue #18's degraded mode is to be made visible
rather than merely made safe; and the cold start was rerun end-to-end in a
throwaway repository so that a real duration and exit code existed to point at.
Each manufactures a positive signal where there had only been the absence of a
negative one. Tightening the assertions inside any of the three checks would have
changed nothing, because in every instance the check was not the thing that
failed — its execution was.

## Evidence

From 2026-09-02: `gate_lib.document_kind` compared against a single subpath
prefix, so prp-core documents classified as neither PRD nor plan and
`st-post-tooluse.py` "returned before its only `print` — indistinguishable from a
gate that ran and passed" (#50), with #18's follow-up noting that "silently doing
nothing repeats the #50 blind-gate failure mode." From PR #52: "meta-tests that
only check `skipped`/`failures` are unfalsifiable against crashes — `errors`
belongs in them." From the 11:17 review: six agents, zero findings, yet the
`Hook cancelled` symptom was backed only by timing and had never been observed
because the interactive gate would not run headless. A fourth instance sits in
the same log: `stack.py` with an empty framework set wipes its output file and
exits 0.

## Related Concepts

- [[concepts/blind-gate-silent-pass]]
- [[concepts/timing-evidence-vs-observed-behavior]]
- [[concepts/drift-guard-scope-and-falsifiable-meta-tests]] — the meta-test instance and its `errors` fix
- [[concepts/catalog-filter-destroys-carried-forward-decisions]] — the exit-0 wipe as a fourth instance
