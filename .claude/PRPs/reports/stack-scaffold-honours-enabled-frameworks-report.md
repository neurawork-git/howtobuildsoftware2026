# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/stack-scaffold-honours-enabled-frameworks.plan.md`
**Branch:** `feature/stack-scaffold-honours-enabled-frameworks`
**Status:** `COMPLETE`

## Outcome

`compliance-base/scripts/stack.py` now reads `config.json` and treats `frameworks` as the
enabled set for the stack pipeline, not only for extraction. `main()` calls `load_cfg()`,
intersects the configured list with `capabilities.json`, and passes the narrowed catalog to
`gaps()`, `render_gap_report()` and `apply_selection()`; `scaffold()` still receives the full
catalog and partitions it internally.

A framework switched off is retained, not deleted: its entries move into a sibling `disabled`
map in `stack.json` with all eight decision fields (`chosen`, `rationale`, `chosen_from`,
`applicable`, `applicability_reason`, `scoped_from`, `ranked`, `ranked_from`) verbatim, and
move back into `choices` — machine-owned fields refreshed from the current catalog — when the
framework is re-enabled. `choices` keeps its existing meaning as the working universe, so none
of the fifteen downstream read sites across `compliance-base/scripts/` and `stack-base/scripts/`
changed; `grep` confirms `stack.py` is the only reader of `disabled`. The key is omitted when
no framework is disabled, so an unnarrowed repo writes byte-identical output to before.

An enabled set that intersects the catalog in nothing is now refused in every mode with a line
naming the configured frameworks, the catalog's frameworks and the `config.json` path, exiting
1 and writing nothing — previously it produced an empty `choices`, a "0 of 0" gap report and
exit 0.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest compliance-compiler.tests.test_stack` (from `engines/`) | `passed` | `Ran 88 tests ... OK` (was 67; 21 added — 18 for the feature, 3 for review finding R1) |
| Same suite against `git show HEAD:...stack.py` (both copies reverted) | `failed as required` | `FAILED (failures=6, errors=11)` — 17 of the new tests fail pre-fix, e.g. `choices` holding `iso27001/asset-inventory` and `soc2/access-reviews`; the report run printing `3 of 3` instead of `1 of 1` |
| `python3 -m unittest discover -s compliance-compiler/tests` | `passed` | `Ran 196 tests ... OK` — includes `test_payload_drift.py` (AC7) |
| `python3 -m unittest discover -s stack-compiler/tests` | `passed` | `OK` — AC6, no `stack-base/` change needed |
| `discover -s _shared/tests` | `passed` | `Ran 59 tests ... OK` — manifest/CHANGELOG rule |
| `discover -s tests` (plugin root) | `passed` | `Ran 116 tests ... OK` — `test_selfhost_version.py` VERSION pairing |
| `discover -s knowledge-compiler/tests`, `-s claudemd-lerner/tests` | `passed` | `OK` each |
| `node --test plugins/neurawork-cc-harness/hooks/version-check.test.js` | `passed` | `# pass 19 / # fail 0` |
| `uvx ruff check` on the three touched Python files | `passed` | `All checks passed!` (a repo-wide `ruff check` reports 166 pre-existing errors in untouched files) |
| Self-host no-op (AC5) | `passed` | `uv run --directory compliance-base python scripts/stack.py --scaffold` with pre-fix vs post-fix `stack.py`: the two outputs are `diff -q` **identical**, carry no `disabled` key, and both print `68 capabilities (3 choice(s) carried, 0 new)` |
| `diff -q payload/scripts/stack.py compliance-base/scripts/stack.py` | `passed` | identical (AC7) |

Acceptance mapping: AC1 — `test_narrowed_config_scaffolds_only_its_frameworks` (CLI) and
`test_only_enabled_frameworks_reach_choices`. AC2 — `test_disabled_entry_keeps_all_eight_decision_fields`.
AC3 — `test_re_enabling_restores_the_decisions_verbatim`,
`test_retained_entry_refreshes_its_machine_owned_fields` and the CLI round trip
`test_narrow_then_widen_round_trips_a_recorded_decision`. AC4 —
`test_empty_frameworks_is_refused_and_writes_nothing`,
`test_frameworks_naming_nothing_in_the_catalog_is_refused`,
`test_a_refused_run_leaves_an_existing_stack_json_untouched`. AC5 —
`test_enabled_none_is_todays_behaviour_and_writes_no_disabled_key`,
`test_unnarrowed_config_writes_no_disabled_key` and the self-host comparison above. AC6 — the
stack-compiler suite plus the `disabled`-reader grep. AC7 — `test_payload_drift.py`,
`test_selfhost_version.py`, `test_manifest.py`.

## Deviations and Decisions

- **`split_by_framework` preserves the non-`frameworks` top-level keys on *both* halves**, not
  only the enabled one as the plan wrote. A half is still a catalog and the symmetry costs
  nothing; only the enabled half is used by `main()`.
- **The empty-set guard is worded `Refusing to run:`**, not `Refusing to scaffold:`, because it
  runs before every mode rather than only `--scaffold`.
- **Version bump is 7 → 8 for the engine/self-host pair and 0.9.0 → 0.10.0 for the plugin**
  (minor, per `plugins/CLAUDE.md`: a payload *behavior* change is not a patch).
- **Both test files the plan asked to `git add` are already tracked** — PR #51 landed
  `engines/compliance-compiler/tests/test_payload_drift.py` and `tests/test_selfhost_version.py`
  before this work started. Nothing to add.
- **`AGENTS.md` (both copies) untouched** — checked as the plan instructed: neither describes the
  `frameworks` key nor the `stack.json` schema.
- **Test fixture `_constraints()` now uses `mkdir(exist_ok=True)`** so the new
  `_multi_constraints()` can extend the same catalog dir. Behavior-neutral for existing callers.
- **Pre-existing drift in the tracked `compliance-base/catalog/stack.json`, deliberately not
  committed:** re-running `--scaffold` rewrites `generated` (2026-08-13 → today) and moves
  `chosen_from` ahead of `applicable` in every entry (the tracked file predates that key being
  emitted by `scaffold()` rather than appended by `apply_selection()`). The pre-fix code produces
  exactly the same diff, so this change does not cause it; the file was restored with
  `git checkout` and the drift is out of scope.
- **This report is written into the worktree's `.claude/PRPs/reports/`**, not the main
  checkout's, because the session is worktree-isolated and cannot write outside it. Reports are
  tracked in this repo (precedent `d1dbb6b`), so it travels with the branch and merges into the
  store on PR merge.

## Review Dispositions

| ID | Disposition | Reason and evidence | Tracking |
| --- | --- | --- | --- |
| `R1` — plain report run after narrowing mislabels the disabled frameworks' keys as orphaned (`stack.py:813`, nice-to-have, correctness) | `FIXED` | Confirmed and reproduced: between a config narrowing and the next `--scaffold`, `stack.json.choices` still holds the switched-off keys, and the post-run `gaps(in_play, …)` computed `orphaned` against the narrowed catalog, so the gap report claimed they were "removed upstream". `gaps()` gained a `full_catalog` parameter (defaulting to `catalog`, so every other caller is unchanged) and `main()` passes the unnarrowed catalog for that one membership question — the same split the `--scaffold` branch already made. Three regression tests added (`TestGapsOrphanedIsACatalogQuestion` ×2, plus a CLI run asserting the report has no "Orphaned keys" section); all three fail against the pre-fix commit `d1bb45a` (`FAILED (failures=1, errors=2)`) and pass after. | `Not applicable` |

## Completion Gate

- **Plan tasks complete:** `Yes` (tasks 1-6)
- **Acceptance criteria satisfied:** `Yes` (AC1-AC7, mapped above)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One commit: `stack.py` honours `config.json`'s `frameworks` and retains the frameworks it
switches off. Both copies of `stack.py`, the 18 new tests in the compliance-compiler suite, the
`compliance-base/CLAUDE.md` config-key correction, both `VERSION` files (7 → 8), the plugin
manifest version (0.10.0) with its CHANGELOG section, and this report. No `stack-base/` change,
no `catalog/` change, no `reports/` artifact.

## Delivery

- **Commits:** `d1bb45a` fix(compliance): stack.py honours config.json's enabled frameworks; `<R1 fix>` fix(compliance): orphaned is a catalog question, not a config one
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/53
- **Base / Head:** `main <- feature/stack-scaffold-honours-enabled-frameworks`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
