# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/harness-install-hygiene-and-hook-cold-start.plan.md`
**Branch:** `feature/harness-install-hygiene`
**Status:** `COMPLETE`

## Outcome

Harness hooks now survive a cold checkout, and an installed engine's `_shared/tests/`
contains only tests that are valid inside a target repo.

- **#5 point 2** — every engine hook ships a 60 s timeout, and `merge_hooks` treats the
  shipped timeout as a **floor**: an existing entry below it is raised, a higher
  hand-edited value is kept. That is what reaches the installs that already exist,
  including this repo (10 entries, previously 10 s / 15 s, now all 60).
- **#5 point 1** — `uv.lock` is tracked instead of ignored, removing the dependency
  resolve from a cold start. `prune_gitignore` is the new counterpart to the append-only
  `merge_gitignore`, so the ignore rule an earlier release wrote is removed on the next
  install rather than living forever in existing repos.
- **#33** — the `_shared/` copytree and its plugin-only test exclusion have one
  definition in the new plugin-side-only `engines/_shared_install.py`, used by all four
  installers (the block was previously byte-identical in four places, with the exclusion
  in only two). It also unlinks copies an older install left behind, which repaired this
  repo's own `knowledge-base/_shared/tests/` and `claudemd-lerner/_shared/tests/`.
- Released as plugin `0.8.0` with all four engine VERSIONs bumped, because both
  migrations only run during an install.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s _shared/tests` | passed | `Ran 63 tests ... OK` (+9 for the timeout floor and the prune) |
| `python3 -m unittest discover -s knowledge-compiler/tests` | passed | `Ran 44 tests ... OK` |
| `python3 -m unittest discover -s claudemd-lerner/tests` | passed | `Ran 40 tests ... OK` |
| `python3 -m unittest discover -s compliance-compiler/tests` | passed | `Ran 163 tests ... OK` |
| `python3 -m unittest discover -s stack-compiler/tests` | passed | `Ran 198 tests ... OK` (incl. `test_payload_drift.py`) |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | passed | `Ran 102 tests ... OK` |
| `uvx ruff check` (from `engines/`) | no regression | `Found 154 errors` — identical count on `main`; none in the new or edited lines |
| `python3 plugins/neurawork-cc-harness/scripts/doctor.py` | passed | `40 checks: 31 OK, 5 NOTE, 4 WARN — worst: WARN`; all four engines `version ... (current)` and `_shared/ matches the plugin`. The 4 WARNs are `.venv is missing`, which is the fresh-worktree state this plan makes survivable, not a new finding |
| `git ls-files \| grep -c 'uv\.lock'` | passed | `4` |
| `git check-ignore -v <the four lock files>` | passed | exit 1, no output — none is ignored |
| settings.json timeouts after re-running the four installers | passed | `[60] * 10` — 10 harness hook entries, all 60 (the plan said 8; the count grew with the stack gate and the two retrieval hooks) |
| Cold-start timing in a throwaway worktree of this branch (no `.venv`) | passed | `uv run --directory knowledge-base python -c ...`: **6.95 s cold** (venv creation + 32 package installs incl. a 91 MB download), **0.084 s warm**. That is the cost paid *before* a hook's own code runs, against the previous 10 s SessionEnd budget |

The plan's last manual gate — starting and ending an interactive Claude Code session
inside a throwaway worktree and checking for a `Hook cancelled` line — cannot be run from
a non-interactive session. The timing measurement above is the substitute evidence: it
isolates the exact bootstrap that was being killed, in a real fresh worktree of this
branch, with the committed `uv.lock` in place.

## Deviations and Decisions

- **`env.PRP_HOME` written by the installers was removed from `.claude/settings.json`.**
  Re-running `compliance-compiler`'s installer calls `set_env_default("PRP_HOME",
  ".claude/PRPs")`, which the root `CLAUDE.md` explicitly forbids for this repo ("Never
  set `env.PRP_HOME` in `.claude/settings.json`" — the `prp-core` resolver appends
  `<slug>-<hash8>`, so a literal path nests a second store). The block was dropped from
  the committed settings.json; the rest of that file is exactly what the installers
  produced. The installer behaviour itself is outside this plan's scope and belongs to
  `prp-store-symlink-wiring-and-stack-gate-blindness.plan.md`, which owns that surface.
- **The four `uv.lock` files were regenerated with `uv lock`**, not copied from the main
  checkout, whose lock files were 2–3 months stale (Jun/Jul) and would have been
  committed as a pin nobody chose. All four resolve to 35 packages.
- **`stack-compiler/tests/test_install_recon.py:88` was inverted, not deleted.** It
  asserted `uv.lock` was in the shipped `.gitignore`; it now asserts the opposite, with
  the reason. That is the one existing test the change contradicts.
- **The four stale tracked test copies were removed by re-running the installers**, not
  by `git rm` — `refresh_shared`'s unlink is exactly the repair path being shipped, so
  running it is also the proof it works.
- **Engine VERSION bump reading:** all four bumped. The installed directory content
  changes in every engine (`_shared/settings.py`, `.gitignore`, the removed tests, the
  hook timeouts), and VERSION is the signal that a re-install is needed — which is
  precisely what these two migrations require.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` (Tasks 1–4)
- **Acceptance criteria satisfied:** `Yes` (AC1–AC8)
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One commit: the three install-time fixes plus the release. Includes
`engines/_shared_install.py`, the four installers, `_shared/settings.py`, the new and
adapted tests, the self-host install dirs as re-produced by running the installers
(`.claude/settings.json`, four `.gitignore`s, four `VERSION`s, four `uv.lock`s, the four
deleted plugin-only test copies), `plugin.json` and `CHANGELOG.md`.

## Delivery

- **Commits:** `a48b2be` — `fix(harness): hooks survive a cold checkout, and installs stop shipping plugin-only tests`
- **Pull Request:** `Not opened` — this repo routes every PR through `/neurawork-cc-harness:nw-ship-pr` (root `CLAUDE.md`, Coding Discipline), which owns push, review, the validation gate and merge.
- **Base / Head:** `main <- feature/harness-install-hygiene`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
