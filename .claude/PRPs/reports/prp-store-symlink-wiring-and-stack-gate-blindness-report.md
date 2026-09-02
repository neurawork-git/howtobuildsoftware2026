# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/prp-store-symlink-wiring-and-stack-gate-blindness.plan.md`
**Branch:** `feature/prp-store-symlink-and-stack-gate` (merged; worktree removed)
**Status:** `COMPLETE`

## Outcome

The stack gate now classifies the documents prp-core actually writes, and a repo gets one
artifact store instead of one per checkout.

- **The filter half came from `main`, not from this plan.** While the branch was open, PR #48
  made `document_kind` read subpath *lists* with a `*` segment (`.claude/PRPs/*/plans` as a
  shipped default) plus configurable suffixes and archive segments — strictly more general
  than this plan's one-inserted-segment fix, and already pinned by
  `test_star_segment_matches_exactly_one_segment`. The merge therefore took main's
  `gate_lib.py` (payload + `stack-base`) and `test_gate_lib.py` wholesale and dropped this
  branch's version and its five unit cases. Task 1 of the plan is satisfied, by other code.
- New `engines/_shared/prp_store.py` owns store identity and wiring: `key_for_root` (git's
  blob id from `hashlib`, verified byte-identical to `git hash-object`), `store_key`
  (worktree-invariant via the main checkout), `link_path`/`store_link` (the single place
  composing prefix and key), `link_prp_store` (`linked` / `already` / `conflict` /
  `unsupported`, never replacing an occupied target) and `wire_store`, the one
  implementation both installers call — symlink first, relative `PRP_HOME` as the reported
  fallback. Only an **absolute** `$PRP_HOME` counts as a link prefix, and an `env.PRP_HOME`
  still in `settings.json` is reported as winning over the new link.
- Both gate hooks classify against the main checkout as well as their own, via new
  `_shared/gitctx.checkout_roots`. Without it the link itself reintroduced the silent gate
  for every worktree session: the document lives in the main checkout, so
  `relative_to(<worktree>)` finds nothing.
- `/nw-doctor` gained a repo-scoped `prp-store` check: linked (`OK`), `PRP_HOME` only
  (`NOTE`, the older wiring), both (`NOTE`, `PRP_HOME` wins and the link is inert), a link
  resolving elsewhere (`WARN`), neither (`WARN` — documents land outside the repo). It runs
  only where a gate-owning engine is installed and stays read-only. The split-store count is
  scoped to the `PRP_HOME` wiring: only a relative prefix gives a worktree a second physical
  store, and `.claude/PRPs` being tracked means a feature branch legitimately holds a plan
  `<base>` lacks — running the check for real in this repo's own worktree is what showed the
  first version warning on ordinary workflow.
- Plugin `0.7.0 -> 0.8.0`; `engines/stack-compiler/VERSION` `2 -> 3`,
  `engines/compliance-compiler/VERSION` `5 -> 6`, mirrored into the self-hosts, with a
  CHANGELOG section (without a bump no installed cache ever sees this).

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s _shared/tests` | passed | Ran 59 tests, OK |
| `python3 -m unittest discover -s stack-compiler/tests` | passed | Ran 207 tests, OK (incl. `test_payload_drift`) |
| `python3 -m unittest discover -s compliance-compiler/tests` | passed | Ran 175 tests, OK (incl. the new `test_hook_paths.py`) |
| `python3 -m unittest discover -s knowledge-compiler/tests` | passed | Ran 44 tests, OK |
| `python3 -m unittest discover -s claudemd-lerner/tests` | passed | Ran 40 tests, OK |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | passed | Ran 115 tests, OK |
| `node --test hooks/version-check.test.js` | passed | 0 cancelled, 0 skipped (main's Node suite, after the merge) |
| Regression proof: store-layout hook case vs the pre-merge `gate_lib.py` | failed as intended | `FAILED (failures=1)`; passes after |
| Regression proof: both worktree cases vs the pre-fix hooks | failed as intended | `FAILED (failures=1)` per gate; passes after |
| Regression proof: installer with a relative `PRP_HOME` | failed as intended | asserted no symlink under `.claude/PRPs` |
| Measured before the worktree fix | — | `document_kind` returned `'plan'` with the main checkout as `repo_root` and `''` with the worktree's |
| Merge resolution, mechanically | verified | `git diff origin/main HEAD` empty for `gate_lib.py` (payload + `stack-base`), `test_gate_lib.py`, both `config.py` |
| `uvx ruff check` on every touched file | passed | new files clean; the rest matches the pre-change baseline |
| `python3 plugins/neurawork-cc-harness/scripts/doctor.py` | passed | `OK prp-store store linked: /home/felix/.prp/howtobuildsoftware2026-35325a96 -> …/.claude/PRPs`, no split-store WARN |
| Installed gate, real repo: `document_kind` over four real paths | passed | `plan`/`prd` for the store layout, `''` for `completed/` and for two inserted segments |
| Installed hook end to end, off-stack component in a live plan path | passed | `Stack gate: 2 catalog component(s) named … 2 off-stack: Argo CD …` (temp document and report removed afterwards) |
| `/nw-ship-pr` validation gate | GREEN | all six commands from the `CLAUDE.md` rules block, run in the PR's own checkout |
| `grep -c 'neurawork-cc-harness:rules' CLAUDE.md` | unchanged | 3 before and after; the diff touches neither BEGIN nor END marker |

## Deviations and Decisions

- **Task 1 was withdrawn in favour of main's solution.** PR #48 landed a more general fix
  (subpath lists with a `*` segment, plus configurable suffixes and archive segments) while
  this branch was open. The merge takes main's `gate_lib.py` and `test_gate_lib.py` wholesale;
  this branch's `document_kind` branch and its five unit cases are gone, subsumed by
  `test_star_segment_matches_exactly_one_segment`. The end-to-end **hook** case is kept —
  main covers the store layout in unit tests only, and the defect was that the hook printed
  nothing at all.
- **`wire_store` lives in `_shared`, not duplicated in both installers.** The plan sketched
  the link-then-fall-back reporting inside each `install.py`; writing it twice would give one
  decision two owners.
- **`link_prp_store` resolves its prefix like prp-core does**, and only from an *absolute*
  `$PRP_HOME`. Honouring a relative value — what every pre-0.8 install wrote, and what Claude
  Code exports into the session — put the link inside the repo's own store, pointing at its
  own parent. Found by review round 1, fixed with a failing-first test at both levels.
- **The link required a second fix the plan did not foresee.** Pointing the store at the main
  checkout means a worktree session's document lives outside its own checkout, and both hooks
  classified against `KDIR.parent` alone — the same silent gate, one layer down, for the
  repo's own documented lifecycle. New `_shared/gitctx.checkout_roots` answers the working
  trees a file can live in; both hooks walk it and keep the root that matched. Found by review
  round 3, verified independently before fixing.
- **`key_for_root`/`link_path` were split out of `store_key`/`store_link`** so the doctor,
  which already resolves the main checkout from the worktree's `.git` file, composes the same
  path without a git process — keeping its documented no-subprocess property.
- **The doctor's split-store check is scoped to the `PRP_HOME` wiring.** Its first version
  warned in this repo's own worktree, because `.claude/PRPs` is tracked and a feature branch
  legitimately carries a plan `<base>` lacks. Only a relative prefix can actually split the
  store.
- **`compliance-compiler` gained its first hook CLI test** (`test_hook_paths.py`): the engine
  had none, and the worktree fix needed a per-gate proof.
- Not built, as the plan states: no artifact migration, no removal of `PRP_HOME` support,
  `PLANS_SUBPATH` left in place. The compliance payload drift guard the plan deferred is now
  built — see Tracked follow-ups.

## Review Dispositions

| ID | Disposition | Reason and evidence | Tracking |
| --- | --- | --- | --- |
| `R1` (round 1, blocking) | `FIXED` | A relative `$PRP_HOME` was taken verbatim as the link prefix, so the ordinary upgrade path wrote a recursive symlink into the repo's own store and reported it as `~/.prp/<key>`. Reproduced, then fixed in `a17acab` with a unit case and an end-to-end installer case. | Not applicable |
| `R2` (round 3, blocking) | `FIXED` | The symlinked store puts a worktree session's document in the main checkout, where both hooks' `relative_to(<worktree>)` raised and the gate printed nothing. Verified independently (`'plan'` vs `''` for the same path), fixed in `db7002c` with one end-to-end case per gate. | Not applicable |
| `R3` (round 4, non-blocking) | `FIXED` | The PR body's verification table and version numbers were stale relative to the CHANGELOG. Rewritten before the merge. | Not applicable |

Rounds 2 and 4 returned no findings.

## Completion Gate

- **Plan tasks complete:** `Yes` (tasks 1-5, plus the version bump the Risks table requires)
- **Acceptance criteria satisfied:** `Yes` — AC1 (hook test + live install), AC2 (unit tests +
  live install), AC3/AC4 (install tests, link and fallback), AC5 (doctor tests + real run),
  AC6 (compliance suite, `set_env_default`'s five cases, `test_payload_drift`)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One coherent outcome: the store wiring and the gate that reads it. `gate_lib.document_kind`
plus its tests and the `stack-base` mirror; `_shared/prp_store.py` plus tests and the four
self-host `_shared/` copies; both installers and their install tests; the doctor check and its
tests; `CLAUDE.md`, `docs/INSTALL.md`, `docs/ARCHITECTURE.md`, both SKILL.md files and
`commands/co-validate.md`; the plugin/engine version bumps and the CHANGELOG entry.

## Delivery

- **Commits:** `977f724` (store wiring + gate), `a17acab` (absolute `PRP_HOME` only),
  `5e054c4` (merge of main; main's `document_kind` wins), `f7ea07c` (doctor split-store
  scoping), `db7002c` (worktree classification in both gates)
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/50 —
  **MERGED** as `c9cefd9` on 2026-09-02. Merged with `--admin`: `main-protection` requires an
  approval a PR's own author cannot give; the operator chose the bypass at the gate. All
  checks green (Analyze python + javascript-typescript, CodeQL, GitGuardian).
- **Base / Head:** `main <- feature/prp-store-symlink-and-stack-gate` (branch deleted remote
  and local; worktree removed)
- **Source PRD:** `None`
- **Tracked follow-ups:** two drift guards this work's manual mirroring made overdue, both
  built immediately afterwards on `chore/drift-guards-and-plan-archive`:
  `engines/compliance-compiler/tests/test_payload_drift.py` (the guard `stack-compiler` had
  and compliance did not — this work edited both hook copies by hand) and
  `tests/test_selfhost_version.py` (every self-host `VERSION` against its engine's — this
  work moved four of those files by hand). Both proven to fail on an introduced drift.
