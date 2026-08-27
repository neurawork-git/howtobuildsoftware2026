# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-evaluation-first-gate-coupling/.claude/PRPs/plans/evaluation-first-gate-coupling.plan.md`
**Branch:** `feature/evaluation-first-gate-coupling`
**Status:** `COMPLETE`

## Outcome

A repo now has exactly one place where its test command is authored — the
`neurawork-cc-harness:rules` block in the root `CLAUDE.md` — and both halves of the harness read
it from there.

- The block's Evaluation-first bullet ends with `Run:` followed by a fenced code block, one
  command per line. `/neurawork-cc-harness:nw-rules-init` writes every detected command into it;
  an absent fence stays a valid state.
- `compliance-compiler` gained `scripts/rules_block.py` (the only Python parser of the block) and
  `precheck.validation_precheck()`. On every plan write the `co-` `PostToolUse` hook now appends
  one advisory clause about the plan's own `## Validation` section — missing section, section with
  no runnable command (naming the repo's declared commands), commands but no test file named
  anywhere, or a confirming clause. Advisory only: it never touches the `blocking` condition.
- `/nw-ship-pr` Phase 4.5's input became the block's commands followed by `validate_commands`,
  exact duplicates dropped. The key's role narrowed to **extras** (lint, type-check); the block
  owns the test command. A repo with no block behaves exactly as before.
- This repo now carries the block (six `unittest discover` suites, 1,280 chars) and its
  `.claude/ship-pr.local.md` `validate_commands` list is empty with a comment stating why.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests` | `passed` | Ran 161 tests, OK (was 131; +11 `test_rules_block.py`, +12 validation precheck/corpus, +7 advisory) |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | `passed` | Ran 22 tests, OK (was 19) |
| `… discover -s _shared/tests` | `passed` | Ran 41 tests, OK |
| `… discover -s knowledge-compiler/tests` | `passed` | Ran 15 tests, OK |
| `… discover -s claudemd-lerner/tests` | `passed` | Ran 30 tests, OK |
| `… discover -s stack-compiler/tests` | `passed` | Ran 189 tests, OK |
| `uvx ruff check` on the three changed modules | `passed` | `All checks passed!` for `rules_block.py`, `precheck.py`, `co-post-tooluse.py` |
| `uvx ruff check` over `engines/` | `passed (+1 pre-existing-in-kind)` | 142 findings stashed vs 143 applied; the delta is one `RUF100` on `test_rules_block.py`'s `# noqa: E402`, the identical directive every sibling test file carries and is flagged for |
| Corpus test (AC2) | `passed` | `TestValidationPrecheckCorpus` ran (not skipped): `section_present` on all live + completed plans |
| Payload identity (AC8) | `passed` | `diff -r` on `payload/scripts` vs `compliance-base/scripts` and `payload/hooks` vs `compliance-base/hooks` — no output; both `VERSION` files read `4` |
| Runtime — advisory, empty section (AC1, AC4) | `passed` | Throwaway plan + real hook: `…'## Validation' names no runnable command — this repo declares: \`cd …_shared/tests\`, …` (all six, none typed into the plan or the config); probe deleted |
| Runtime — advisory, no section (AC1, AC4) | `passed` | `decision key present: False`; `No '## Validation' section — add one naming a runnable command and the test files this change adds.` |
| Runtime — block extraction (AC5) | `passed` | Phase 0.2's `sed` form over the live `CLAUDE.md` returns the six commands; `rules_block.read()` returns the same six |
| Runtime — block-absent fallback (AC8) | `passed` | Scratch `CLAUDE.md` with the BEGIN marker renamed: `sed` extraction yields 0 lines, `rules_block.read()` yields `[]` |

**Not run:** `/nw-ship-pr` on this PR (the plan's *Runtime — gate* row). It cannot run before the
PR exists; it is the merge step for this change and will exercise Phase 4.5 for real.

## Deviations and Decisions

1. **Phase 0.2 reads the rules block from `<wt-root>`, not `<main-root>`.** The plan specified
   `<main-root>/CLAUDE.md`. Changed for the reason Phase 4.5 already states about the commands
   themselves: the main checkout holds `<base>`, so a PR that adds a test directory declares it in
   *its* `CLAUDE.md` and a main-root read would run the base's declaration against the branch's
   code — the exact class of error the `<wt-root>` anchoring rule exists to prevent. It also
   matches the hook, which reads the working tree's `CLAUDE.md`. `validate_commands` still comes
   from `<main-root>` (it is gitignored per-machine config and lives only there).
2. **Budget raised to 1,500, not an unstated number.** This repo's six commands render to 1,281
   characters. Stated in the skill, in `RULES_BLOCK_BUDGET`, and measured against this repo's own
   command list rather than a single sample command.
3. **The skill's block template is wrapped in a four-backtick fence.** A three-backtick outer
   fence ends at the inner ```` ```sh ````, handing the extractor half a block. The skill says so
   in one line, and the test regex matches four.
4. **`validation_precheck` returns `repo_commands` as well as the count.** The plan listed five
   keys; the advisory needs the command strings to name them, so the list is returned too.
5. **The advisory is not folded into `_summary`'s `catalog_built: False` early return.** It joins
   the two branches the plan named (`:88,93`), the same two `_capability_summary` joins. A repo
   with no compliance catalog gets the "run `co-extract`" sentence alone, unchanged.
6. **The `## Validation` block template writes `stack-compiler/tests`,** which this repo's
   `CLAUDE.md` prose Test section still omits (it lists four engine suites, not five). The block
   follows `.claude/ship-pr.local.md`'s authoritative six. Reconciling the prose is explicitly out
   of scope per the plan's *Not building*.
7. **The plan's *Not building* items were left alone:** the stale `.claude/BACKLOG.md` line about
   an empty `validate_commands`, and the overlap between the new block and this repo's
   hand-written "Working principles" section.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` (Tasks 1-5)
- **Acceptance criteria satisfied:** `Yes` — AC1-AC4 by unit test plus the two runtime hook probes;
  AC5 by the live and block-absent extractions plus the Phase 4.5 asset test; AC6 by
  `test_validation_gate_merges_the_rules_block_with_the_config_extras`, which pins `<wt-root>` and
  forbids a main-root-anchored gate; AC7 by `grep -c 'rules BEGIN' CLAUDE.md` == 1 and the rewritten
  `.claude/ship-pr.local.md`; AC8 by the payload/VERSION identity checks and the block-absent path.
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One coherent outcome: the rules block becomes machine-readable and both the plan precheck and the
pre-merge gate consume it.

- `plugins/neurawork-cc-harness/skills/nw-rules-init/SKILL.md` — fenced command slot, 1,500 budget,
  Stage 1 rendering rules, the machine-read warning.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/rules_block.py` (new),
  `payload/scripts/precheck.py`, `payload/hooks/co-post-tooluse.py`, `VERSION` (3 → 4).
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_rules_block.py` (new),
  `tests/test_shards_precheck.py`.
- `plugins/neurawork-cc-harness/commands/nw-ship-pr.md` — Phase 0.2 block read, Phase 4.5 merged
  input and the two roles, Phase 5 source line, the first-run proposal rule.
- `plugins/neurawork-cc-harness/tests/test_skill_assets.py` — the fence/`Run:`/budget cases and the
  Phase 4.5 guard invariant.
- `compliance-base/` — the ADOPT re-install (`scripts/rules_block.py`, `scripts/precheck.py`,
  `hooks/co-post-tooluse.py`, `VERSION`).
- `CLAUDE.md` — the rules block.

Not committed (gitignored, per-machine): `.claude/ship-pr.local.md` in the main checkout, rewritten
to an empty extras list with a comment stating the key's new meaning.

## Delivery

- **Commits:** `Not created`
- **Pull Request:** `Not opened`
- **Base / Head:** `main <- feature/evaluation-first-gate-coupling`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
