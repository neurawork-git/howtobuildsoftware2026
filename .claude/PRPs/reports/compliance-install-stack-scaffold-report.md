# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-compliance-install-scaffold/.claude/PRPs/plans/compliance-install-stack-scaffold.plan.md`
**Branch:** `feature/compliance-install-scaffold`
**Status:** `COMPLETE`

## Outcome

A fresh `compliance-compiler` install now lands in a state where both shipped features
actually work.

- `install.py` derives `catalog/stack.json` from the seeded capability catalog by running the
  target's own `scripts/stack.py --scaffold` under `sys.executable` — deterministic, no API key,
  no `uv`. Create-if-absent, so an existing stack.json with human choices, scope or ranking is
  never touched, and a target with no `capabilities.json` gets a printed skip instead of a file.
- `install.py` sets `env.PRP_HOME = ".claude/PRPs"` in the repo's tracked
  `.claude/settings.json` through the new `_shared.settings.set_env_default()`, so `prp-core`
  writes plans inside the repo instead of `~/.prp`. A differing existing value is reported and
  left alone.
- `precheck.is_plan_path()` accepts the store layout that setting produces
  (`.claude/PRPs/<repo>-<hash>/plans/*.plan.md`) alongside the canonical
  `.claude/PRPs/plans/*.plan.md`. Exactly one store segment; `completed/` still excluded in both.

Without both halves the validator stays silent: the plan location and the path filter only meet
when they are changed together.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests -t plugins/neurawork-cc-harness/engines/compliance-compiler` | `passed` | Ran 131 tests, OK (was 125 before; 6 new) |
| `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/_shared/tests -t plugins/neurawork-cc-harness/engines/_shared` | `passed` | Ran 39 tests, OK (5 new for `set_env_default`) |
| `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/knowledge-compiler/tests -t …` | `passed` | Ran 15 tests, OK |
| `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/claudemd-lerner/tests -t …` | `passed` | Ran 13 tests, OK |
| `python3 -m unittest discover -s plugins/neurawork-cc-harness/tests -t plugins/neurawork-cc-harness` | `passed` | Ran 9 tests, OK |
| `uvx ruff check <the 7 changed python files>` | `passed for changed lines` | 5 findings remain, all on lines this change did not touch (`install.py:258` BLE001 on the pre-existing hook-merge catch; `test_install_recon.py` RUF100 line 22 and PLW1510 lines 41/222/232). The two findings my own new lines produced (BLE001, FURB192) were fixed. The engines tree has 146 pre-existing findings overall — the repo's convention (commit `73cc078`) is per-PR scope. |
| Self-host ADOPT: `python3 plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | `passed` | `ADOPT install …` / `Hooks already present` / `PRP_HOME set to .claude/PRPs …`; `compliance-base/VERSION` → 3; `git diff --stat compliance-base/catalog/` empty — catalog and `stack.json` untouched |
| Runtime, installed copy: `is_plan_path()` from `compliance-base/scripts/` against both layouts | `passed` | `store layout : True`, `canonical : True` (throwaway file created and removed) |

The hook's detached `validate.py` spawn was deliberately **not** exercised — it costs an LLM
call and that code path is unchanged by this work. What changed is the path filter in front of
it, proven above against the refreshed self-host copy.

## Deviations and Decisions

- **One extra fix, in scope by consequence:** running the ADOPT install (Task 6) copied
  `_shared/tests/test_manifest.py` and `test_version_check.py` into `compliance-base/`, where
  they fail — they assert plugin-level facts (`<plugin>/hooks/version-check.py`) that no
  installed copy has. `_copy_code` copies `_shared/` wholesale, and those two tests were added
  to `_shared/tests/` after the last install, so this ADOPT was the first to surface it. Fixed
  in `compliance-compiler/install.py` by excluding them from the copy and unlinking stale copies
  an older install left behind (`PLUGIN_ONLY_SHARED_TESTS`), with assertions in the fresh-install
  test. Without this, the plan's own Task 6 would have committed two failing tests into the
  self-host.
- **`knowledge-compiler` and `claudemd-lerner` still ship those two tests** on their next ADOPT
  — same `_copy_code` pattern, `install.py:77` and `install.py:73`. Not fixed here (out of this
  plan's scope, and neither engine is otherwise touched). Their current installs are clean
  because they were installed before those tests existed. Needs a follow-up; see below.
- **`merge_hooks` now shares the new `_load()` helper** rather than keeping its own inline
  parse — same behavior, one implementation of the parse-or-`SettingsError` contract that
  `set_env_default` also needs.
- **`PLANS_SUBPATH` kept** in `config.py` although `precheck` now reads `PRP_SUBPATH`: it still
  documents the canonical location, and harness PRD Phase 7 (`co-` hook on PRD writes) will need
  the same pair of constants for `prds/`.
- **`test_seeding_is_atomic` needed one added line** (`stack.json` unlinked with the capability
  files) — after Task 1 the first install produces a stack.json, so the "no capability layer ⇒
  no scaffold" assertion is only meaningful once that file is gone too.
- **`PRP_HOME` takes effect at the next session start**, not in the session that wrote it; the
  settings `env` block is read at startup. This report therefore still lands in the global store.

## Completion Gate

- **Plan tasks complete:** `Yes` (Tasks 1–6)
- **Acceptance criteria satisfied:** `Yes` (AC1–AC7)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The install-completeness change and nothing else: `install.py` (`_seed_stack`, `PRP_HOME`,
plugin-only test exclusion), `_shared/settings.py` (`set_env_default` + shared `_load`), the
widened `is_plan_path` in `payload/scripts/{config,precheck}.py`, their tests, the engine
VERSION bump, the refreshed self-host copies under `compliance-base/`, `.claude/settings.json`
(the `PRP_HOME` entry the installer wrote), the four documentation surfaces, and the plan file
itself at `.claude/PRPs/plans/`.

## Delivery

- **Commits:** `95f10ab feat(compliance-compiler): a fresh install now lands ready to validate plans`
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/34
- **Base / Head:** `main <- feature/compliance-install-scaffold` (open, ready for review)
- **Source PRD:** `None`
- **Tracked follow-ups:** https://github.com/neurawork-git/howtobuildsoftware2026/issues/33 — the same plugin-only `_shared` test exclusion is still missing in the `knowledge-compiler` and `claudemd-lerner` installers.
