---
title: "A Gate Whose Failure Mode Is Silence Cannot Be Told From One That Passed"
aliases: [blind-gate, silent-failure-pattern, degraded-mode-must-be-visible]
tags: [compliance-compiler, hooks, failure-modes, verification, gotcha]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# A Gate Whose Failure Mode Is Silence Cannot Be Told From One That Passed

Several independent findings in the compliance engine share one shape: a check
that never really ran emitted exactly what a check that ran and passed would
emit. In Issue #50, `gate_lib.document_kind` compared against a single subpath
prefix, so prp-core documents classified as neither PRD nor plan and
`st-post-tooluse.py` returned before reaching its only `print` — output
indistinguishable from a clean gate.

## Key Points

- #50's root cause sat one level up: installers wrote a **relative** `PRP_HOME`,
  so each worktree resolved its own physical store and documents landed outside
  the prefix the classifier recognised.
- A second instance in `gate_lib`: after a narrowing, a component with no
  surviving owner drops to status `orphaned` (`gate_lib.py:249`), while
  `verdict()` (`:338`) inspects only `off_stack` and `violations` — so a
  previously `off_stack` violation passes the gate silently. License violations
  are unaffected.
- A third: `stack.py` given an empty framework set wipes `stack.json` and exits
  0, reporting "0 of 0, nothing to report".
- The remedy adopted for Issue #18 is to make the degraded mode visible, on the
  explicit grounds that silently doing nothing would repeat the #50 failure mode.
- The `orphaned` path is so far established by source inspection only; it has not
  been executed live.

## Details

What makes this class of defect expensive is that the evidence of failure is the
absence of evidence. A gate that runs and finds nothing prints nothing; a gate
that never classified its input also prints nothing. No log line, exit code, or
diff distinguishes them, so the defect survives exactly as long as nobody
independently asks whether the check fired at all. Both #50 and the `orphaned`
path were found by reading code, not by observing behaviour — which is what one
would expect of a failure with no observable signature.

The structural fix is not a stricter check but a louder one: a degraded or
skipped mode has to emit something that a successful run would not. Issue #18's
plan therefore pairs the inline-only config switch with documentation of what the
hook still guarantees without deep validation, so the reduced mode is legible
rather than merely safe. The relative-`PRP_HOME` root cause also connects this to
installer behaviour — a value written by the installer determined whether a gate
in a different subsystem could see its own inputs (see
[[concepts/install-run-clobbers-local-edits]]).

## Related Concepts

- [[concepts/timing-evidence-vs-observed-behavior]] — the same absence-read-as-success error in a review
- [[concepts/catalog-filter-destroys-carried-forward-decisions]] — the exit-0 file wipe listed here
- [[concepts/install-run-clobbers-local-edits]] — the installer-written `PRP_HOME` behind #50
- [[connections/silence-read-as-success]] — the general pattern across three subsystems

## Sources

- [[daily/2026-09-02.md]] — #50's blind gate, the `orphaned` verdict gap, and #18's visible-degraded-mode remedy
