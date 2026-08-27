# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-doctor-currency/.claude/PRPs/plans/doctor-plugin-currency-and-silent-engine-failure.plan.md`
**Branch:** `feature/doctor-currency`
**Status:** `COMPLETE`

## Outcome

`claudemd-lerner` runs again, and `/nw-doctor` now answers the two questions that made
its all-clear false.

The learner's `update.py` died at import on every invocation
(`ModuleNotFoundError: No module named '_shared'`) because it was the one payload script
without the `sys.path` bootstrap its siblings carry. Its `SessionStart` hook spawned it
detached with both streams at `/dev/null`, so the crash produced zero `CLAUDE.md` updates
and left no trace. Three changes close that: the import fix (in both byte-identical
copies), a stamp that only advances when at least one log actually ingested, and a hook
that appends the detached child's output to `scripts/update.log` instead of discarding it.

The doctor gained a `plugin` section that compares the installed plugin against the
marketplace clone already on disk — offline, read-only, no `git` process — plus notes for a
running plugin root that differs from the installed path, leftover cache versions, and the
"re-installing now would still install the older engine" cross-check. Its queue check now
gives a completion stamp with no ingest state its own WARN, and its credentials finding is
three-state instead of asserting "compile / update / extract cannot run" on a machine where
they demonstrably do.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s claudemd-lerner/tests` | passed | `Ran 37 tests ... OK` (was 30; 7 new in `test_update_runtime.py`) |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | passed | `Ran 102 tests ... OK` (was 78; 24 new in `test_doctor_plugin.py`) |
| `... discover -s _shared/tests` | passed | `Ran 56 tests ... OK` |
| `... discover -s knowledge-compiler/tests` | passed | `Ran 36 tests ... OK` |
| `... discover -s compliance-compiler/tests` | passed | `Ran 163 tests ... OK` |
| `... discover -s stack-compiler/tests` | passed | `Ran 198 tests ... OK` |
| New regression test against the unfixed `update.py` | failed as required | reverting the bootstrap line reproduces `ModuleNotFoundError` in `test_update_runs_without_the_install_dir_on_pythonpath` |
| AC1 live: `python3 scripts/update.py --dry-run` against the real queue (`LERNER_ROOT` = main checkout, plain `python3`, nothing on `PYTHONPATH`) | passed | `[DRY RUN] Logs to apply (6):` and the six log names — no traceback, exit 0. The same command against the **unfixed** main checkout still raises `ModuleNotFoundError`, which is the before/after pair. |
| AC4 live: `python3 plugins/neurawork-cc-harness/scripts/doctor.py --repo <main checkout>` | passed | `WARN queue … scripts/last-update.json is stamped (2026-08-27 12:30) but scripts/state.json does not exist …`, fix `uv run --directory claudemd-lerner python scripts/update.py` |
| AC5 live, `same` path | passed | `OK currency installed 0.5.1 matches the neurawork-harness marketplace`; `NOTE running` (doctor loaded from the worktree checkout, not the cache); `NOTE cache 6 other versions …` |
| AC5 live, `behind` path | passed | With `CLAUDE_CONFIG_DIR` pointed at a scratch copy of the real registry pinned to `0.5.0`: `WARN currency installed 0.5.0 is behind the neurawork-harness marketplace's 0.5.1`, fix `/plugin update neurawork-cc-harness, then /reload-plugins`, plus `NOTE reinstall … (claudemd-lerner)` |
| AC7 live: `--json` | passed | parses; `worst WARN`, 39 findings, the three `plugin` findings carry the same `Finding` fields; exit code `1` |
| AC7: read-only | passed | `test_a_run_leaves_the_repo_byte_identical` plus the new `test_reading_the_plugins_dir_changes_nothing_in_it`; the banned-token grep is clean on `doctor.py` and now also asserted on `harness_probe.py` |
| `uvx ruff check` from the repo root | not clean, and was not clean before | 296 findings repo-wide on ruff 0.16.4, whose default rule set is far wider than when the gate was written (`LOG015`, `BLE001`, `S110`, `UP017`, `I001` across untouched files). Of the files this change touches, the only **new** finding was `SIM115` on the hook's `open()`, silenced with an explanatory `# noqa: SIM115` — the handle must outlive the block because `Popen` dups it, and the `OSError` fallback rules out a `with`. Every changed line is within `line-length = 100`. |

## Deviations and Decisions

- **The new queue WARN sits *after* the lock branches, not ahead of them** (the plan said
  "ahead of the existing stamp/lock branches"). A run still in flight has not written
  `state.json` either, so an earlier placement would report every live compile as "this
  engine never ran" and would replace the more actionable stall ERROR. The stamp-based
  branches it does precede are the ones whose reasoning it invalidates.
  `test_a_run_still_in_flight_outranks_the_never_ran_verdict` pins this.
- **`probe.compare()` had to be extended, not merely reused.** The plan describes it as
  "already int-tuple aware"; the live code called bare `int()`, so `compare("0.5.0",
  "0.5.1")` returned `unknown` and no currency verdict was possible. It now parses dotted
  numeric versions into a tuple (engine `VERSION` files are a one-element case), pads to
  equal width, and treats `0.5` and `0.5.0` as the same release. `is_behind`, which the
  `SessionStart` nudge uses, is untouched.
- **`installed_plugins.json` has a nested schema.** The plan assumed a top-level keyed
  dict; the live file is `{"version": 2, "plugins": {"<plugin>@<marketplace>": [entry, …]}}`
  — a *list* of entries per key, one per scope. `_installed_entry` handles both a list and
  a bare dict and prefers `scope == "user"`.
- **Two existing queue fixtures gained a `state.json`.** `test_an_eligible_gate_warns…` and
  `test_a_stamp_newer_than_every_log…` had a stamp and no ingest state, which is precisely
  the new WARN. Each now records an earlier ingested log so it still isolates the gate
  condition it was written for.
- **No `.gitignore` change was needed for `update.log`** — the install's ignore list
  already carries `scripts/*.log`, beside `flush.log`.
- **The live "behind" state named in the plan no longer exists**: the operator ran
  `/plugin update` between planning and implementation, so the machine now reads
  `0.5.1 == 0.5.1`. That path was proved against a scratch copy of the real registry rather
  than by mutating the operator's own state, which the doctor's contract forbids.
- **The real `update.py` was not run against this repo's six pending logs**, per the plan's
  Agent Notes: it costs money and rewrites tracked docs. That is the operator's call once
  this ships.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` (Tasks 1–7)
- **Acceptance criteria satisfied:** `Yes` (AC1–AC7)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The learner import/stamp/logging fix in both copies, the two new doctor checks plus the
credentials three-state, the probe's plugin-currency reader and semver-aware `compare`,
their tests, and the release metadata (`nw-doctor.md`, `claudemd-lerner/VERSION` 4 → 5,
plugin `0.5.1` → `0.6.0`, CHANGELOG). Nothing else.

## Delivery

- **Commits:** `Pending — /nw-ship-pr`
- **Pull Request:** `Pending — /nw-ship-pr`
- **Base / Head:** `main <- feature/doctor-currency`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
