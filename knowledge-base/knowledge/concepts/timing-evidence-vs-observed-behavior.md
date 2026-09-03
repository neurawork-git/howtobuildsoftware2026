---
title: "Timing Evidence Is Not an Observed End-to-End Symptom"
aliases: [inferred-vs-observed, headless-reproduction, review-zero-findings]
tags: [verification, code-review, evidence, testing, convention]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-02
updated: 2026-09-03
---

# Timing Evidence Is Not an Observed End-to-End Symptom

A review workflow of six agents returned zero findings but recorded one gap: the
end-to-end symptom (`Hook cancelled`) had been argued from timing numbers, never
observed, because the interactive gate would not run headless. The gap was closed
afterwards by reproducing the whole path in a disposable repository, where
`session-start.py` ran 11.28 s and exited 0.

## Key Points

- Zero findings did not mean fully verified: the review explicitly flagged
  inferred-versus-observed as its own residual risk.
- The obstacle was practical — an interactive gate that could not be driven
  headless — not a disagreement about the diagnosis.
- The follow-up ran the real path in a throwaway repo, producing an observed
  11.28 s / exit 0 that corroborates the 11.6 s in Issue #5.
- The same run doubled as acceptance evidence for a second change: no
  `test_manifest.py` or `test_version_check.py` appeared in the installed copy,
  confirming AC1 (plugin-only `_shared` tests excluded from installer copies).

## Details

Timing measurements support a causal story — the hook takes longer than the
budget, therefore it is cancelled — but they are one inferential step away from
the failure a user reports. Recording that distinction as a review outcome is
what made the missing step actionable instead of invisible; a review that had
simply passed would have shipped the same code with the same untested claim.

The reproduction was only meaningful because the environment matched the
reporter's, which required emptying the `uv` cache rather than just removing
`.venv` (see [[concepts/cold-start-measurement-needs-empty-uv-cache]]). A headless
run performed in a warm-cache environment would have produced a fast, clean exit
and been read as a disproof. Running the full install in a disposable repository
also exercised unrelated acceptance criteria in the same pass, so a single
faithful end-to-end reproduction paid for two verification debts at once.

## Related Concepts

- [[concepts/cold-start-measurement-needs-empty-uv-cache]] — the environment fidelity that made the reproduction valid
- [[concepts/hook-timeout-sixty-second-budget]] — the budget the observed run confirmed
- [[concepts/verify-generated-artifacts-before-commit]] — the same verify-against-reality discipline applied to generated docs
- [[concepts/uncommitted-changes-to-deleted-files-block-ff-pull]] — the git blocker hit while cleaning up after the same PR
- [[concepts/blind-gate-silent-pass]] — the same null-result-read-as-pass error inside the gate itself
- [[connections/silence-read-as-success]] — the three instances of this pattern from one day

## Sources

- [[daily/2026-09-02.md]] — review (6 agents, 0 findings) noted the symptom was only timing-backed; cold start later shown end-to-end, AC1 confirmed in the same install

