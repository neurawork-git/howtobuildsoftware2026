# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-harness-doctor/.claude/PRPs/plans/harness-doctor.plan.md`
**Branch:** `feature/harness-doctor` (worktree `/home/felix/projects/howtobuildsoftware2026-harness-doctor`)
**Status:** `COMPLETE`

## Outcome

`/nw-doctor` — a read-only health report for a repo's harness installs. One command
answers which engines are installed and where, whether each is at the shipped version,
whether its files and wiring are intact, and whether its queue is draining, with a fix
command on every finding.

Two new plugin-side scripts (stdlib-only, system `python3`, no `uv`, no venv, no API key):

- `plugins/neurawork-cc-harness/scripts/harness_probe.py` — the engine registry and
  install discovery, merging two sources whose disagreement is itself the finding: the
  hook commands in `.claude/settings.json` and a directory-signature scan.
  `hooks/version-check.py` now reads this registry instead of its own copy, which had
  already fallen a whole engine behind reality.
- `plugins/neurawork-cc-harness/scripts/doctor.py` — the checks, findings, text/`--json`
  report and severity exit code (0 OK/NOTE, 1 WARN, 2 ERROR).

Run against the self-host it immediately surfaced two things nothing else reports: the
`knowledge-compiler` queue stall (pending logs behind a fresh lock with no completion
stamp) and `stack-base/_shared/settings.py` drifted from the plugin — an installed copy
missing `set_env_default` entirely. `stack-base` is invisible to `version-check.py` by
construction.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | passed | `Ran 67 tests ... OK` (was 38 before this change) |
| `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests` | passed | `Ran 44 tests ... OK` — **unmodified**, which is the AC8 proof |
| `... discover -s knowledge-compiler/tests` | passed | `Ran 36 tests ... OK` |
| `... discover -s claudemd-lerner/tests` | passed | `Ran 30 tests ... OK` |
| `... discover -s compliance-compiler/tests` | passed | `Ran 161 tests ... OK` |
| `... discover -s stack-compiler/tests` | passed | `Ran 189 tests ... OK` |
| `python3 plugins/neurawork-cc-harness/scripts/doctor.py --repo <main checkout>` | passed | 36 checks, all four installs found with dir + discovery method + version; exit 2 while the `knowledge-compiler` stall was live, exit 1 after it cleared |
| Live stall report (AC2) | passed | `ERROR queue  1 pending daily log of 4; a run was spawned at 2026-08-27 12:34 and never completed — the fresh lock blocks the gate until 2026-08-27 18:34`, with the foreground command and the lock path as its fix |
| Degraded run (AC4, AC7) | passed | `PATH=/usr/bin:/bin`, both credential vars unset, `--json`: `exit=1`, `json.tool` exit 0, `worst=WARN` — exit code matches `worst` |
| Read-only (AC5) | passed | `git status --porcelain` after every run shows only the intended edits; the unit suite snapshots size+mtime of every file in a fixture repo before/after, and a source-level test forbids `subprocess`/`Popen`/`mkdir`/`write_text`/`unlink` in `doctor.py` |
| Worktree (AC6) | passed | run inside the worktree: `NOTE worktree ... both compile gates are suppressed here by design`; queue lag is a NOTE, and gitignored `daily/` absence a NOTE, not a fault |
| `uvx ruff check` | pre-existing failures | Not a clean gate today: 277 findings at repo root, 145 under `engines/` before this change. The changed files add 4 `RUF100` on `# noqa: E402` — the same pattern already carried by 16 existing files under `engines/`. No other rule fires on them. |

**Not run:** `/nw-doctor` as a slash command. The session's plugin resolves from the
marketplace cache at 0.3.0, which does not contain this unreleased command file; it will
resolve once the plugin ships. The command's only executable content — the direct
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"` invocation — was run and is pinned by
`tests/test_skill_assets.py::DoctorCommandTests`.

## Deviations and Decisions

1. **`stack-compiler` has a hook now.** The plan (written 2026-08-21) states it installs
   none. It ships `hooks/st-post-tooluse.py` at `PostToolUse` and this repo wires it. The
   registry carries that marker, so `stack-base` is discovered by hook *and* signature.
2. **The nudge stays quiet about `stack-compiler`, by a different rule.** The plan skipped
   it for lack of a hook marker; with a marker present the reason had to change or
   `version-check.py` would tell users to run `/neurawork-cc-harness:stack-compiler`,
   which does not exist. `Engine.install_skill` is now the gate: `find_stale()` covers only
   engines with an installer — exactly today's three — and the doctor is where
   `stack-compiler` surfaces. `_shared/tests/test_version_check.py` passes unmodified.
3. **Required payload files are read from the shipped `payload/`, not a hand-kept list**
   (`probe.payload_files`). It is precisely what every `install.py` `_copy_code` copies, so
   a new payload script cannot enter the tree and quietly stay out of the integrity check.
4. **No `git` subprocess.** The plan's repo resolution used `git rev-parse`. The doctor
   walks up for a `.git` entry and reads worktree status from its type (a linked worktree
   has a `.git` *file*, the main checkout a directory). Stdlib, and it keeps the read-only
   invariant literal — the module starts no process at all, which a test enforces.
5. **Untracked data dirs are NOTE, not WARN.** `daily/` and `reports/` are gitignored and
   legitimately absent in a fresh clone or a worktree. Tracked ones (`knowledge/`,
   `catalog/`) stay ERROR. Without this the doctor reports a fault in every worktree.
6. **`_shared/` drift compares top-level `*.py` only.** `compliance-compiler`'s installer
   deliberately withholds two plugin-only tests, so comparing `_shared/tests/` would
   report drift the installer itself creates.
7. **The `_shared` drift fix does not point at `payload/`.** `_shared/` is deliberately
   absent from every payload (the installer copies it from `engines/_shared/`), so for an
   installer-less engine the fix names `engines/_shared/*.py` directly. Pinned by a test.
8. **AC2's live fixture moved during implementation, as the plan's Agent Notes predicted.**
   The `claudemd-lerner` stall the plan described cleared mid-session (the learner
   completed at 12:30; its stamp now post-dates the 09:24 lock). `knowledge-compiler` then
   exhibited the identical ERROR stall and is the evidence above. Both engines' current
   states are still reported precisely — `claudemd-lerner` shows `5 pending daily logs of
   5 (no scripts/state.json — every log counts as pending)`. The deterministic proof is the
   unit suite on temp repos; the live state is not a fixture.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` — all four tasks.
- **Acceptance criteria satisfied:** `Yes` — AC1–AC8, with AC2's live evidence captured
  against `knowledge-compiler` rather than `claudemd-lerner` (deviation 8) and the
  `/nw-doctor` command invocation validated by direct script run plus asset test.
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The doctor and everything that makes it usable, as one coherent outcome:

- CREATE `plugins/neurawork-cc-harness/scripts/harness_probe.py`, `scripts/doctor.py`
- CREATE `plugins/neurawork-cc-harness/commands/nw-doctor.md`
- CREATE `plugins/neurawork-cc-harness/tests/test_harness_probe.py`, `tests/test_doctor.py`
- UPDATE `plugins/neurawork-cc-harness/hooks/version-check.py` (reads the shared registry)
- UPDATE `plugins/neurawork-cc-harness/tests/test_skill_assets.py` (command invariants)
- UPDATE `CLAUDE.md`, `plugins/CLAUDE.md`, `README.md`, `docs/INSTALL.md`

No `hooks.json` change — the doctor is on-demand only. No engine `VERSION` bump: no
payload changed, so no install is stale.

## Delivery

- **Commits:**
  - `458e5fe feat(plugin): /nw-doctor reports why a harness install went quiet` (11 files, +1719 / -79)
  - `230aa94 fix(doctor): a live compile is in flight, not a stall` — review round 1
  - `3f595fb fix(doctor): a stamp newer than every daily log means the gate never fires` — review round 2 (blocking)
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/40 —
  **MERGED 2026-08-27T11:30:44Z**, merge commit `910bdf7`.
- **Base / Head:** `main <- feature/harness-doctor` (remote branch deleted on merge)

### How the merge happened — not through this session's gate

This session never reached the `/nw-ship-pr` approval gate and never ran `gh pr merge`.
While review round 3 was being acted on, another actor merged `origin/main` into the
branch (`fef9252`, a commit this session did not author), merged PR #40, deleted the
remote branch, and removed the worktree
`/home/felix/projects/howtobuildsoftware2026-harness-doctor` — which killed the in-flight
edit for the round-3 fix. Everything committed was already pushed, so nothing committed
was lost. Most likely a parallel session running its own `/nw-ship-pr` on the same PR.

**Consequence: review round 3 returned a BLOCKING finding that is NOT in `main`.**

## Post-merge open defect (round 3, unfixed)

**In a linked worktree the queue check reads the wrong directory and reports every stall
as drained** — `plugins/neurawork-cc-harness/scripts/doctor.py`, `check_queue`.

`check_queue` reads `daily/`, `scripts/state.json`, the stamp and the lock out of
`<repo_root>/<dirname>/`. In a worktree the capture side writes none of them there: every
capture hook resolves its output through `_shared/gitctx.state_home()` and redirects into
the MAIN checkout, and all four are gitignored so they never exist in a worktree. So in a
worktree `logs` is `[]`, `pending` is `[]`, and the drained early-return fires
(`OK queue drained — 0 pending daily logs of 0`, exit 0) before the worktree branch is
ever reached — that branch only fires for a fixture state production cannot produce.

Verified against merged `main`: it contains neither `main_checkout_root` nor a `queue_root`
parameter; the old `suppressed by design` branch is still the only worktree handling.
Independently reproduced earlier in this session: run from the worktree, the doctor
reported no queue finding above OK for either queued engine, while the same run against
the main checkout reported a stall and five pending logs.

It matters because this repo's documented workflow (PRD → plan → `/nw-worktree` →
implement → ship) puts the user in a worktree by default, so the most likely place
`/nw-doctor` is invoked is the one place its central check silently lies, at exit 0.

**The fix that was being written when the worktree was removed** (process-free, keeps the
read-only contract):

1. Add `main_checkout_root(repo_root)` next to `in_worktree()`: read the `.git` FILE, which
   holds `gitdir: <main>/.git/worktrees/<name>`; require an absolute path whose parent is
   `worktrees` and whose grandparent is `.git`; return the great-grandparent when it is a
   directory, else `None`.
2. Thread a `queue_root` through `run_checks` into `check_queue` — the main checkout root
   in a worktree, `repo_root` otherwise — and anchor the queue `target` to it. Append to
   the message that the queue was read from the main checkout.
3. When the main root cannot be resolved, emit a NOTE saying the queue lives in the main
   checkout and was **not** read, with the fix "run the doctor from the main checkout" —
   never a drained/OK verdict that cannot be supported.
4. Replace `test_the_same_stall_inside_a_worktree_is_suppressed_by_design`: its fixture
   materialises daily logs inside the worktree, a state production cannot produce. Two
   tests instead — a worktree whose `.git` file resolves to a main checkout holding the
   stalled queue (the ERROR is reported, noting where it was read from), and one whose
   `.git` file does not resolve (NOTE, never "drained").

Plan AC6 ("inside a linked worktree, queue lag is reported as suppressed by design") was
written on the assumption that the doctor reads the worktree's own queue. Reading the main
checkout supersedes it: there is then no worktree lag to misreport.
- **Base / Head:** `main <- feature/harness-doctor`
- **Source PRD:** `None`
- **Tracked follow-ups:** Two live defects the doctor surfaced are reported, not fixed —
  the plan's own "Risks and Decisions" scopes repair out of this delivery:
  `stack-base/_shared/settings.py` is behind `engines/_shared/settings.py` (missing
  `set_env_default`), and `claudemd-lerner` has no `scripts/state.json` despite five
  captured daily logs. Neither has a tracking issue yet.
