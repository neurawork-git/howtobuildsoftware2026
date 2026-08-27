# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/stack-compiler-wire-document.plan.md`
**Branch:** `feature/stack-compiler-wire-document`
**Status:** `COMPLETE`

## Outcome

`stack-compiler` is the fourth installable skill. `engines/stack-compiler/install.py` +
`recon.py` install the product-scoping engine into any git repo the same way the other three
install (recon → ask → ADOPT-safe execute), driven by the new
`/neurawork-cc-harness:stack-compiler` skill, with `/st-scope`, `/st-rank`, `/st-select` and
`/st-validate` covering its four passes. The installer seeds no `product.md` (`scope.py` owns
that template) and owns no data artifact — every write still goes through
`compliance-base/scripts/stack.py`.

Running it against this repo turned the hand install into installer output: `stack-base/_shared/`
is refreshed (`settings.py` now byte-identical to the engine copy — the pre-matcher stale copy is
gone), `stack-base/_shared/tests/` arrived, and the `st-` `PostToolUse` hook **moved** out of the
catch-all `matcher: ""` group into `Write|Edit|MultiEdit` next to compliance's `co-` hook, so no
tool call spawns a `uv run` subprocess only to exit. `.claude/BACKLOG.md`'s stale-`_shared` item
is closed. The staleness nudge now covers `stack-base/` (`install_skill` set in the shared engine
registry), and every prose surface says four installable skills; plugin `0.5.0` with a matching
CHANGELOG section.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s stack-compiler/tests` | passed | Ran 198 tests — OK (includes the new 9-case `test_install_recon.py`) |
| `… -s _shared/tests` | passed | Ran 56 tests — OK (new `test_stale_stack_compiler_detected`, `test_manifest` on `0.5.0`) |
| `… -s knowledge-compiler/tests` | passed | Ran 36 tests — OK |
| `… -s claudemd-lerner/tests` | passed | Ran 30 tests — OK |
| `… -s compliance-compiler/tests` | passed | Ran 163 tests — OK |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | passed | Ran 73 tests — OK (new skill↔ENGINES assertion; two pre-existing tests updated, see Deviations) |
| `cd plugins/neurawork-cc-harness/engines/stack-compiler && uvx ruff check` | 9 findings, baseline parity | Same three classes the shipped `compliance-compiler` engine reports (50 findings there): `I001` + `BLE001` in `install.py`, `PLW1510` in `recon.py`/tests. The new modules introduce no finding class the precedent does not already carry |
| Self-host migration: installer at repo root, then `git diff --stat` | passed | Exactly `.claude/settings.json`, `stack-base/_shared/settings.py`, plus new `stack-base/_shared/tests/` — `config.json`, `product.md`, `VERSION`, `scripts/`, `hooks/` and `compliance-base/catalog/` untouched (AC6, AC8) |
| `.claude/settings.json` `PostToolUse` readback | passed | One group, `matcher: "Write|Edit|MultiEdit"`, holding the `co-` and `st-` hooks; the empty `matcher: ""` group is gone |
| `cmp stack-base/_shared/settings.py engines/_shared/settings.py` | passed | identical (AC6) |
| `grep -rn "not yet installable\|installed by hand\|three independently installable" plugins/ docs/ CLAUDE.md stack-base/CLAUDE.md .claude-plugin/` | passed | no hits (AC7) |
| `python3 plugins/neurawork-cc-harness/scripts/doctor.py` | passed | `stack-compiler`: discovery / wiring / version / shared / integrity all OK; the two `venv` WARNs are the gitignored `.venv` absent in a fresh worktree |
| `python3 engines/stack-compiler/recon.py` (this repo) | passed | `existing_dir: stack-base`, `compliance_dir: compliance-base`, `stack_state: {total 68, scoped 68, chosen 3}` |

Not run: the plan's optional end-to-end scratch-repo run of the three passes (needs
`ANTHROPIC_API_KEY` and ~30 paid agents). The install/ADOPT/migration half of that signal is
covered by the temp-repo suite and by the self-host migration above.

## Deviations and Decisions

- **Task 5 was smaller than the plan expected.** The plan targets `hooks/version-check.py`'s
  `ENGINES` map, but PR #41 lifted that registry into `scripts/harness_probe.py`, where a
  `stack-compiler` entry already existed with `install_skill=None`. The change is therefore one
  field (`install_skill="stack-compiler"`) plus the two comments that named the missing installer,
  not a fourth map entry.
- **Two existing tests pinned the old world and were updated, not deleted.**
  `tests/test_harness_probe.py::test_only_engines_with_an_install_skill_are_nudged` asserted
  `stack-compiler` is *not* nudgeable; it is now
  `test_every_engine_that_ships_an_installer_is_nudgeable`, deriving the expectation from whether
  `engines/<name>/install.py` exists — the same invariant, stated so it survives the next engine.
  `tests/test_doctor.py::test_the_shared_fix_never_points_at_a_payload` reached the installer-less
  branch through `stack-compiler`; it now reaches it through a synthetic `install_skill=None`
  engine, and a second case asserts the installable path names `/neurawork-cc-harness:stack-compiler`.
- **Two surfaces beyond the plan's six were false and were corrected:** `commands/nw-doctor.md`
  carried a paragraph saying `stack-compiler` ships no installer and its fixes are manual (deleted),
  and `engines/_shared/__init__.py`'s docstring said "Both skills (knowledge-compiler,
  claudemd-lerner)". The latter is copied into every install, so the corrected file was propagated
  into all four self-hosts (`knowledge-base/`, `claudemd-lerner/`, `compliance-base/`, `stack-base/`)
  — exactly what each installer would have written. `scripts/doctor.py`'s generic
  "ships no installer" fallback is left in place: it is the guard for the next engine that arrives
  before its `install.py`, and it names no engine.
- **No `_prune_removed`, no `product.md` seeding, no engine `VERSION` bump** — as the plan
  specifies. `engines/stack-compiler/VERSION` stays `2` and matches `stack-base/VERSION`.
- **Ruff findings are baseline parity, not new debt.** `install.py`'s `I001` and `BLE001` and
  `recon.py`'s `PLW1510` are the same findings the shipped `compliance-compiler` installer
  produces from the identical code shape; matching the precedent was chosen over diverging from it.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` (Task 7's PRD phase row is written by `/prp-prd-update implemented`
  after the PR exists; the harness PRD registry row is already `shipped`)
- **Acceptance criteria satisfied:** `Yes` — AC1/AC2/AC4/AC5 by the new temp-repo suite, AC3 by the
  skill + four command files and the prompt-asset suite, AC6/AC8 by the self-host diff and the
  untouched payload, AC7 by the grep, the four-entry registry, `0.5.0` and its CHANGELOG section
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The fourth installable skill and every surface that describes it: `engines/stack-compiler/`
`install.py` + `recon.py` + `tests/test_install_recon.py`, `skills/stack-compiler/SKILL.md`, the
four `commands/st-*.md`, the `harness_probe` registry field and its test, the two updated
plugin-asset tests, the self-host migration (`stack-base/_shared/**`, `.claude/settings.json`), the
`_shared/__init__.py` docstring propagated into all four installs, the six prose surfaces plus both
manifests and the `0.5.0` CHANGELOG section, the corrected `test_payload_drift.py` docstring, the
closed backlog item, and the harness PRD registry row.

## Delivery

- **Commits:** `Not created`
- **Pull Request:** `Not opened`
- **Base / Head:** `main <- feature/stack-compiler-wire-document`
- **Source PRD:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/prds/stack-compiler.prd.md` — Phase 5, pending `/prp-prd-update implemented`
- **Tracked follow-ups:** `None`
