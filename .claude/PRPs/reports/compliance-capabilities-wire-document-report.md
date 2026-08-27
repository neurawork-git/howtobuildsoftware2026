# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/compliance-capabilities-wire-document.plan.md`
**Branch:** `feature/capabilities-wire-document` (worktree `/home/felix/projects/howtobuildsoftware2026-capabilities-wire-document`)
**Status:** `COMPLETE`

## Outcome

The compliance capability layer — shipped but undiscoverable since Phases 1–3 — now has a
command, a signal, and documentation.

- `/neurawork-cc-harness:co-capabilities` derives the capability layer (`capabilities.py`)
  and refreshes the stack scaffold + gap report (`stack.py --scaffold`) in one command.
- The `co-` `PostToolUse` hook no longer stays silent when the capability layer is absent:
  it names the command that builds it, mirroring the existing constraint-catalog nudge.
- All seven doc surfaces that list `co-extract` now list `co-capabilities`; `stack.json`
  is named where `capabilities.{json,md}` already was; `docs/INSTALL.md` and
  `docs/ARCHITECTURE.md` now describe bootstrap truthfully (the prebuilt shipped seed,
  not an install-time extraction).
- `compliance-base/CLAUDE.md` exists for the first time, matching its two sibling installs.
- The PRD records that the SessionStart bootstrap is superseded, with the evidence.

No engine behavior changed: `capabilities.py`, `stack.py`, `validate.py` and `precheck.py`
are untouched.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s compliance-compiler/tests` (from `plugins/neurawork-cc-harness/engines`) | `passed` | Ran 92 tests, OK (baseline on `main`: 90; +2 for both nudge branches) |
| `python3 -m unittest discover -s _shared/tests` | `passed` | Ran 34 tests, OK |
| `python3 -m unittest discover -s knowledge-compiler/tests` | `passed` | Ran 15 tests, OK |
| `python3 -m unittest discover -s claudemd-lerner/tests` | `passed` | Ran 13 tests, OK |
| `diff …/payload/hooks/co-post-tooluse.py compliance-base/hooks/co-post-tooluse.py` | `passed` | no output — copies byte-identical |
| `python3 sync_catalog_seed.py --check` | `passed` | `seed in sync with compliance-base/catalog` |
| `uvx ruff check hooks/co-post-tooluse.py` (from `compliance-base`) | `passed` | 1 error — the pre-existing `I001` at line 29 (import block), unchanged from `main`; the edit is at line 50+ |
| `grep -rln "co-capabilities" <7 doc surfaces>` | `passed` | all seven files listed |
| `python3 -c "json.load(...)"` on both manifests | `passed` | `MANIFESTS OK` |
| `uv run --directory compliance-base python scripts/capabilities.py --dry-run` | `passed` | `reuse: gdpr, soc2, iso27001` — all three unchanged, no LLM call |
| `uv run --directory compliance-base python scripts/stack.py` | `passed` | `Stack gaps: 38 of 38 applicable mandatory-linked capabilities have no chosen component`, exit 0, report written |
| Manual — nudge end to end (capability catalog moved aside, hook run on a plan write, file restored) | `passed` | hook `additionalContext` ends `Capability layer not built — run \`/neurawork-cc-harness:co-capabilities\` to derive it; until then plans are checked against constraints only.`; with the catalog present the same run ends `Plan declares no compliance capabilities.` (unchanged from before) |

## Deviations and Decisions

- **One `stack.py` invocation, not two.** The plan's command step called for
  `--scaffold` followed by a plain run for the gap report. `stack.py:457-470` runs the gap
  computation and report unconditionally *after* the scaffold branch, so `--scaffold`
  alone already prints the summary and writes `reports/stack-gaps-<date>.md`. The command
  documents the single invocation.
- **Two nudge tests, not one.** The plan predicted 91 tests; the suite runs 92. Both
  branches are asserted: unbuilt layer names the command, built layer still advises on the
  declaration and does *not* mention the command.
- **The end-to-end nudge check had to move the MAIN checkout's `capabilities.json`,
  not the worktree's.** `effective_root()` (`co-post-tooluse.py:35-42`) deliberately
  redirects to the main checkout when the hook runs from inside a worktree. The first
  attempt moved the worktree copy and the nudge correctly did not fire — the test setup
  was wrong, not the code. Both files were restored by a `finally` block; the main
  checkout's catalog is intact.
- **AC1's "run the command end to end" was executed as `capabilities.py --dry-run` plus a
  plain `stack.py` run.** A full derive-and-scaffold rewrites tracked artifacts with a new
  `generated` date (and would desync the shipped seed) for no behavioral gain, since all
  three frameworks hash as unchanged. Both scripts were proven to run, resolve their
  config, and produce the documented output.
- **`docs/INSTALL.md` bootstrap text was factually wrong and was corrected beyond a pure
  command listing.** It claimed the install "builds the constraint catalog by fanning out
  ~30 parallel SDK agents"; installs land the prebuilt seed and extraction is opt-in
  (`install.py --extract`). AC4 required this.
- **Pre-existing pyright diagnostics** on `co-post-tooluse.py` and
  `test_shards_precheck.py` (`reportMissingImports` for the runtime `sys.path` imports)
  surfaced on edit. They are unrelated to this change — the affected import lines were not
  touched, and `[tool.pyright] extraPaths = ["scripts"]` already exists in both
  `pyproject.toml` files for editors that read it.

## Completion Gate

- **Plan tasks complete:** `Yes` — all 6.
- **Acceptance criteria satisfied:** `Yes` — AC1 (command, both scripts run), AC2 (nudge
  fires when absent, output unchanged when present), AC3 (7 surfaces + `stack.json` named
  + `compliance-base/CLAUDE.md` with every cited path verified to exist), AC4 (no
  `SessionStart` claim survives; remaining mentions are negations or the supersession
  record), AC5 (engine scripts untouched, payload parity `diff` clean).
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

Wire and document the compliance capability layer: the new `co-capabilities.md` command,
the hook nudge in both the payload and self-host copies plus its tests, the seven-surface
documentation sweep, the new `compliance-base/CLAUDE.md`, the two manifest descriptions,
and the PRD's Phase 4 supersession record. Also carried in this branch: the plan artifact
itself and the PRD's Phase 4 status/link row.

## Delivery

- **Commits:** `83dc4dc feat(compliance-compiler): the capability layer has a command, a signal, and docs`; `f9ab9c2 docs(prd): add the wire & document plan, retire the SessionStart bootstrap`; `2bd3e9a docs(prd): record the Phase 4 report and PR`
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/26 (open, ready for review)
- **Base / Head:** `main <- feature/capabilities-wire-document`
- **Source PRD:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/prds/compliance-capabilities.prd.md` — Phase 4 recorded as `implemented` (status stays `in-progress` until merge); report + PR linked in the phase row
- **Tracked follow-ups:** `None`
