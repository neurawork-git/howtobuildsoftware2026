---
name: nw-rules-init
description: Write the harness baseline coding rules — scope discipline, simplicity/YAGNI, PR routing through /nw-ship-pr, and evaluation-first with THIS repo's real test command — into the repo's root CLAUDE.md as a marker-delimited, idempotent block. Recons the existing CLAUDE.md first (already covered / conflicts / absent) and detects the test runner from the repo before asking whether to write. Trigger when the user says "rules init", "nw-rules-init", "baseline rules", "coding rules", "coding discipline", "test-first rules", "evaluation first", "PR-Regel", "PRs nur über nw-ship-pr", "Regeln einrichten", "Coding-Regeln", "YAGNI-Regeln", or runs /nw-rules-init.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion
argument-hint: "[--force]   (--force = refresh an existing block without asking)"
---

# nw-rules-init — baseline coding rules → managed CLAUDE.md block

The harness's three engines describe a repo — purpose, commands, architecture, conventions.
None of them states **how to change it**. This skill writes that missing half into the root
`CLAUDE.md` as one marker-delimited block: scope discipline, simplicity, PR routing through
`/nw-ship-pr`, and evaluation-first carrying the repo's *actual* test command.

There is no engine. The rule text is static, so there is nothing to synthesize; the recon is
you reading the repository. What makes the block safe is the other half of this feature: the
`claudemd-lerner` marker guard (`payload/scripts/markers.py`) restores any marker span the
learner edits, so the block survives every update and seed run.

The block is deliberately small (< 1,500 characters, rendered). A root `CLAUDE.md` is read on
every session; a marker block spends that budget before a single repo-specific rule is written.
The number is 1,500 rather than the original 1,200 because the test command is now a fenced list:
this repo's own six `unittest discover` lines render to 1,281 characters, and a budget the
shipping repo violates is not a budget.

The fence is **machine-read**: `/nw-ship-pr`'s Phase 4.5 validation gate runs exactly those lines,
and the `compliance-compiler` plan precheck names them when a plan declares no test. Changing the
`Run:` label, the fence, or the one-command-per-line rule breaks both readers.

`$ARGUMENTS` may contain `--force` (refresh an existing block without prompting).

Run every stage with **absolute paths** and `git -C "$ROOT"` — the Bash cwd resets between
calls.

## Stage 0 — anchor

```bash
ROOT="$(git -C "$PWD" rev-parse --show-toplevel)"   # fails → not a git repo: report + stop
ls "$ROOT/CLAUDE.md" 2>/dev/null && echo "CLAUDE.md present" || echo "CLAUDE.md absent"
```

- Not a git repo → report "not a git repo — nothing to anchor to" and **stop**.
- `CLAUDE.md` absent → `AskUserQuestion`: "No CLAUDE.md at repo root — create one with the
  rules block?" {Create it / Stop}. On "Create it" the file is a `# CLAUDE.md` heading plus
  the block. On "Stop", exit without writing.
- `CLAUDE.md` present → **Read it fully.** Stages 1 and 2 both depend on having read it, not
  on grepping it.

## Stage 1 — detect the test runner

The Evaluation-first rule is worthless if it names a command the repo does not run. Work the
signals in this order and **stop at the first hit**, then quote the evidence back to the user:

| Order | Signal | Inference |
|---|---|---|
| 1 | A test command already stated in the CLAUDE.md you just read | Use it verbatim — the repo already declared its gate |
| 2 | `.github/workflows/*.yml` test steps (`grep -nE 'pytest\|unittest\|npm test\|go test\|cargo test' `) | CI is the authoritative gate |
| 3 | `pyproject.toml`: `pytest` in dependencies or a `[tool.pytest…]` table | `pytest` (add the paths the repo actually uses) |
| 4 | Python `tests/` trees whose files `import unittest` and no pytest | `python3 -m unittest discover -s <dir>` — **one line per test directory** |
| 5 | `package.json` → `scripts.test` | `npm test` (or the declared runner) |
| 6 | `go.mod` / `Cargo.toml` | `go test ./...` / `cargo test` |

Rules that matter more than the table:

- **Never default to pytest.** A Python repo without pytest gets the `unittest` form. Shipping
  a rule the repo's own suite violates is the exact failure this stage exists to prevent.
- A repo with several suites in different directories gets the multi-line command it really
  uses, not a single collapsed line that under-collects.
- Write **every** detected command into the fence, one per line, in the order you detected them.
  No prompt characters, no comments, no blank lines inside the fence — every non-fence line in it
  is a command a machine will run.
- Nothing found → `AskUserQuestion` for the command. If the user declines, the Evaluation-first
  bullet still ships **with no fence at all** — drop the `Run:` label and the fence together. An
  absent fence is a valid state both readers handle; an invented command is not.
  **Never invent a command.**

## Stage 2 — coverage recon

Having read the CLAUDE.md, classify **each** cluster against what the file already says:

- `✅ already covered` — the file states this rule (name the section or line).
- `⚠️ conflicts` — the file says something in tension with it (quote it briefly).
- `➕ absent` — not present.

Present the table with real quotes from the file you read:

| Cluster | Verdict | Evidence (section / quote) |
|---|---|---|
| Scope — touch only what the request requires | … | … |
| Simplicity — minimum that solves the problem | … | … |
| Pull requests — only via `/nw-ship-pr` | … | … |
| Evaluation first — failing test before the change | … | … |

This is reading and judgment, not a script. Be specific; a generic verdict makes the whole
gate worthless.

## Stage 3 — write it?

One `AskUserQuestion`: "Write the baseline rules block into CLAUDE.md?" {Write it / Skip}.

**Pre-recommend "Write it"** only when at least one cluster is `➕ absent`. When all four are
`✅ already covered`, recommend **Skip** — writing then duplicates a house rule and spends the
CLAUDE.md budget for nothing.

On "Skip" → report "nothing written" and **stop**; do not touch `CLAUDE.md`.

The block is all-or-nothing: four clusters, one marker span. There is no per-cluster
selection — a block that can emit fewer bullets is not worth a marker span.

## Stage 4 — already initialised?

If `<!-- neurawork-cc-harness:rules BEGIN` is already in the CLAUDE.md:

- `--force` in `$ARGUMENTS` → refresh silently (continue to Stage 5, replacing the block).
- else → `AskUserQuestion`: "Root CLAUDE.md already has a rules block — replace it with the
  current one?" {Replace / Keep existing (stop)}.

**Never write a second block.** Two spans with the same marker id is the one state the
learner's guard cannot resolve for you.

## Stage 5 — write the managed block

Read the target `CLAUDE.md`, then:

- marker absent → append the block at end of file, after a blank line.
- marker present → replace everything between the BEGIN and END markers **inclusive**.

Copy the template **byte-for-byte**, substituting only the `<TEST_COMMAND>` line with the
command lines Stage 1 resolved, so a re-run over an unchanged repo produces an empty diff. The
outer fence below is four backticks only so the inner ```sh block survives this file; write three
into `CLAUDE.md`:

````markdown
<!-- neurawork-cc-harness:rules BEGIN (auto-managed — re-run /neurawork-cc-harness:nw-rules-init to refresh) -->
### Coding Discipline

- **Scope** — touch only what the request requires; leave neighbouring code, formatting and
  working sections alone. Remove only the orphans your change created; name pre-existing dead
  code instead of deleting it.
- **Simplicity** — write the minimum that solves the problem. No speculative features, no
  abstraction for a single use, no configurability nobody asked for.
- **Pull requests** — open and merge every PR with `/neurawork-cc-harness:nw-ship-pr`. Another
  PR skill or a bare `gh pr create` skips its review, validation and approval gates.
- **Evaluation first** — a behaviour change starts with a test that fails for the right reason.
  Done means that test passes, not that the code is written. Run:

```sh
<TEST_COMMAND>
```
<!-- neurawork-cc-harness:rules END -->
````

No `MUST`/`NEVER` and no `(MANDATORY)`: none of the four clusters guards a secret, data loss,
a broken deploy, or a trust boundary. Emphasis reserved for everything is emphasis for nothing.

## Stage 6 — report

State: which file was written, the block's character count, the detected test command **and
the signal it came from**, and whether the learner's guard is active here:

```bash
ls "$ROOT"/*/scripts/markers.py 2>/dev/null && echo "marker guard installed" \
  || echo "no claudemd-lerner install — nothing edits CLAUDE.md automatically here"
```

Close with the next step: *"Commit the CLAUDE.md change."* If Stage 2 found a cluster already
covered elsewhere in the file, name that location — a duplicate outside the marker span is the
user's to remove, not this skill's.

## Why these rules

- **Static text, no engine** — the block varies in exactly one interpolated command. An engine
  would add an `install.py`, a `VERSION`, and a staleness entry for text that only changes when
  this file changes.
- **Marker-delimited** — it makes the block auditable (`grep` for the id), refreshable, and
  protectable. The `claudemd-lerner` guard keys on the marker pair, not on this skill.
- **Detect, never default** — the harness's own repo runs `python3 -m unittest discover`, not
  pytest. A hard-coded runner would make the shipped rule false in the repo that ships it.
- **Recommend Skip when covered** — a repo that already states these rules gains nothing from a
  second copy, and the CLAUDE.md budget is real.
