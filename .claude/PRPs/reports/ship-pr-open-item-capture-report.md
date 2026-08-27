# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-ship-pr-open-item-capture/.claude/PRPs/plans/ship-pr-open-item-capture.plan.md`
**Branch:** `feature/ship-pr-open-item-capture`
**Status:** `COMPLETE`

## Outcome

`/nw-ship-pr` now persists every open item a run surfaces, not only deferred review findings.

- **Phase 5** gained point **7. Open items**, the single collection point for the non-finding
  items — degraded validation (`SKIP` with its reason, or `RED`), unverified claims (the Phase 4
  null/empty mini-review fallback), and known-broken state from session knowledge — each named as
  `title` / `why` / `where`, the same shape a finding carries.
- **Phase 6.5** takes **deferred items** as its input: the union of four sources (nice-to-have
  findings, overridden blocking findings, the Phase 5 open items, and nothing else). The rendered
  backlog line is unchanged in shape, with its placeholders generalised from `<finding.*>` to
  `<item.*>` and `where` redefined as the file, path, or phase the item concerns. The zero-item
  skip is preserved verbatim in meaning. Exact-title de-dup now holds across runs because the four
  recurring mechanical items carry fixed title strings named in the command. Two named exclusions
  (deferred worktree removal; the cancel / fix-first paths) are written in as deliberate, with
  their reasons.
- **Phase 9**'s orphan bullet `- open / deferred items.` became a readback of what Phase 6.5 wrote
  plus the items it explicitly excluded, closed by the invariant that the report names no open
  item Phase 6.5 neither wrote nor excluded.
- Four section-scoped guard tests pin the properties whose loss would be silent, including the
  four fixed title strings that make de-dup work.
- `.claude/BACKLOG.md`: the entry this plan implements is ticked (one changed line).

No new phase, sink, state file, or config key. The review workflow and its schema are untouched.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | `passed` | `Ran 19 tests ... OK` (15 before, +4 new guards; the four pre-existing guards unmodified → AC8) |
| `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests` | `passed` | `Ran 41 tests ... OK` |
| `… discover -s knowledge-compiler/tests` | `passed` | `Ran 15 tests ... OK` |
| `… discover -s claudemd-lerner/tests` | `passed` | `Ran 30 tests ... OK` |
| `… discover -s compliance-compiler/tests` | `passed` | `Ran 131 tests ... OK` |
| `… discover -s stack-compiler/tests` | `passed` | `Ran 189 tests ... OK` |
| `uvx ruff check plugins/neurawork-cc-harness/tests/test_skill_assets.py` | `passed` | `All checks passed!` — the only Python file this change touches |
| `uvx ruff check` (repo root) | `pre-existing baseline` | `Found 268 errors.` — all pre-existing; `.claude/ship-pr.local.md` documents why the repo-wide run is deliberately not a gate |
| `git diff plugins/neurawork-cc-harness/commands/nw-ship-pr.md` | `passed` | Touches Phase 5, Phase 6.5 (input / item shape / de-dup / exclusions / sink placeholders), Phase 9 only. No phase ordering changed; all ten `$MAIN_ROOT` occurrences untouched |
| `git diff .claude/BACKLOG.md` | `passed` | One line per ticked entry: the implemented one in `e28442b`, the stale `validate_commands` one in `652c90c` |
| Docs staleness check (`grep -rn "nw-ship-pr" docs/ plugins/CLAUDE.md CLAUDE.md`) | `passed` | Only filename/role mentions; no phase-input description exists to go stale — matches the plan's Integration points |

Acceptance criteria: **AC8** is proven above (four pre-existing guard tests pass unmodified).
**AC1–AC7** are runtime properties of a live `/nw-ship-pr` run; the asset suite proves the prose
exists, never that the run behaves — the module docstring at `tests/test_skill_assets.py:1-11`
makes exactly that point. The runtime rows are the shipping run itself (see Deviations for what
changed in the plan's live fixture).

## Deviations and Decisions

- **The plan's live fixture for AC1 is gone.** The plan assumed `validate_commands` is still empty
  in `.claude/ship-pr.local.md`, so the shipping run's own gate would `SKIP` and produce the entry
  `the /nw-ship-pr validation gate is not configured` in its own PR. That key was seeded on
  2026-08-21 with this repo's six authoritative suites, so the gate now runs for real and AC1
  cannot be demonstrated by this run. The implementation is unaffected — the `SKIP` path and its
  fixed title are documented and tested; only the plan's intended live demonstration is no longer
  available here. AC5 (a clean run stays silent) is the observable one on this PR instead. The
  stale backlog entry "`validate_commands` is empty, so the pre-merge gate never runs" was first
  left untouched per the plan's "touch no other entry", then ticked in `652c90c` at the approval
  gate when it was called out as describing a condition that no longer exists — with a note
  recording what was seeded and why `uvx ruff check` stays out of the list.
- **Two small edits beyond the literal task text, both for internal consistency:** the
  "Why before the merge and not after" paragraph said "Both inputs of this step" and enumerated
  two — corrected to name the open items as well, or it would contradict the new input list one
  paragraph above it; and the `github-issues` / `none` sink bullets were re-worded from
  `finding` to `item` placeholders, since the dispatch's input is now items (the dispatch logic
  itself is unchanged, as the plan requires).
- **Not done, deliberately, per the plan's Not-building list:** `validate_commands` is not
  seeded here, the unresolved `$MAIN_ROOT` is not fixed, the review workflow and its
  `FINDINGS_SCHEMA` are untouched, and nothing is retroactively captured.
- **Contract to preserve:** the four fixed title strings are a contract between
  `commands/nw-ship-pr.md` (Phase 6.5) and `tests/test_skill_assets.py`
  (`test_recurring_capture_items_have_fixed_titles`). Change one and change both, or de-dup stops
  working while the suite stays green on the other three.
- **Segregation of duties (from the plan's Compliance section):** this change edits the shipping
  command and is shipped by it. Review the diff on the PR before the Phase 6 approval; do not
  self-approve on the strength of the gate alone.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` (tasks 1-5)
- **Acceptance criteria satisfied:** `Yes` for AC8 and for every prose property AC1-AC7 depend on;
  the AC1-AC7 runtime observations require live `/nw-ship-pr` runs, and AC1's fixture no longer
  exists in this repo (see Deviations)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One coherent outcome — `/nw-ship-pr` captures open items, not only review findings:

- `plugins/neurawork-cc-harness/commands/nw-ship-pr.md` — Phase 5 point 7, Phase 6.5 input /
  item shape / de-dup titles / named exclusions / sink placeholders, Phase 9 readback + invariant.
- `plugins/neurawork-cc-harness/tests/test_skill_assets.py` — four guard tests plus their
  section-slicing helper; nothing existing touched.
- `.claude/BACKLOG.md` — the implemented entry ticked; the stale `validate_commands` entry ticked
  and annotated in the follow-up commit.

## Delivery

- **Commits:** `e28442b feat(nw-ship-pr): every open item a run surfaces reaches the backlog`;
  `652c90c docs(backlog): the validation-gate entry is stale, not open` (both created by
  `/nw-ship-pr`, which owns commit → PR in this repo)
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/36
- **Base / Head:** `main <- feature/ship-pr-open-item-capture`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
