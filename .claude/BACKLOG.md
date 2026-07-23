# Backlog

Rolling list of not-yet-scheduled work. Newest first. Mirror significant items
into the relevant PRD under `.claude/PRPs/prds/`.

## claudemd-lerner: enforce three base docs folders + one-liner CLAUDE.md

**Date:** 2026-07-23
**Skill:** `claudemd-lerner`
**Status:** open

The learner should **always** scaffold and maintain three base `docs/` folders:

- `docs/troubleshooting/`
- `docs/patterns/`
- `docs/rules/`

These three are exactly the categories that belong in `CLAUDE.md` (rules,
patterns, troubleshooting). Fine-tune the learner so that:

- On install / update it creates the three folders if missing.
- Every **new** `CLAUDE.md` entry lands as a **one-liner only** in `CLAUDE.md`,
  with the full explanation written to the matching `docs/` folder and **linked**
  from the one-liner.
- Goal: `CLAUDE.md` stays small; detail lives in `docs/`.

Requires tuning the `claudemd-lerner` `AGENTS.md` constitution (routing rule:
category → docs folder + one-line back-link) and the seed/update engine
(folder scaffolding).
