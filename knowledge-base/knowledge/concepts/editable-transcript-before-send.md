---
title: "Editable Transcript Before Manual Send"
aliases: [editable-transcript, stt-correction, transcript-review]
tags: [ux, speech-to-text, requirements-quality]
sources:
  - "daily/2026-08-13.md"
created: 2026-08-20
updated: 2026-08-20
---

# Editable Transcript Before Manual Send

Speech-to-text output in GrillMe is shown in the input field as editable text and
requires a manual send, rather than being auto-submitted. In a requirements tool
this is a correctness safeguard: uncorrected dictation errors would be baked into
the persisted design tree as wrong decision nodes.

## Key Points

- The transcript appears editable in the input field; the user must review and
  send it manually.
- Rationale is data quality, not convenience: the interview builds a persisted
  design tree, so a mis-heard phrase becomes a wrong requirement.
- Real errors motivated this — "Google Meet App" and "Grill Buttons" were
  dictation mishears that, unedited, would have created incorrect nodes.

## Details

The 2026-08-13 session surfaced two speech-recognition errors in the original
dictation: "Google Meet App" (no Meet integration was ever intended) and "Grill
Buttons" (actually gamification titles/stickers, not quick-reply buttons).
Because GrillMe's whole purpose is to distill spoken/typed input into structured
requirements, letting raw transcripts flow straight into the design tree would
propagate such errors downstream into the exported spec and derived tickets.

Making the transcript editable before send puts a human correction step between
the `Transcriber` output (see [[concepts/swappable-backend-interfaces]]) and the
persisted tree (see [[concepts/postgres-source-of-truth-replayed-sessions]]),
which is where accuracy actually matters.

## Related Concepts

- [[concepts/grillme-app]] — the requirements app this UX protects
- [[concepts/swappable-backend-interfaces]] — the `Transcriber` whose output is reviewed
- [[concepts/postgres-source-of-truth-replayed-sessions]] — the design tree kept free of dictation errors

## Sources

- [[daily/2026-08-13.md]] — transcript shown editable before manual send; dictation errors clarified
