---
description: PR lifecycle in a fixed order — commit → push → PR → workflow review → validation gate → explanation → approval gate → follow-up capture → merge → branch cleanup
argument-hint: "[PR number]  (empty = PR of the current branch)"
---

# /nw-ship-pr

Carries a finished state safely to the default branch — **always in this order**. The review
and the explanation are produced in parallel by a **workflow engine script**
(`nw-ship-pr-review`); this command wraps that with a **mandatory user approval before the
merge** and cleans the branch up afterwards (remote + local).

Prompt-only: it installs nothing and copies nothing. It reads and lazily writes one per-repo
config file, and runs in any repo that has `git` + `gh`.

**Argument**: `$ARGUMENTS` — optional PR number. Empty → the PR of the current branch.

**Ground rules**
- **Never** merge without explicit approval (Phase 6). Approval is valid for this one run only.
- Never commit or merge onto the default branch when the work belongs on a feature branch.
- At every git/merge step: read what is there first, then act. Red is red — never dress it up
  as green.
- Detect the default branch (`gh repo view --json defaultBranchRef -q .defaultBranchRef.name`);
  do not assume `main`.
- Commit trailer per the repo's own convention (this repo:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`).
- **NEVER `git checkout <other-branch>` / `git switch <existing-branch>` in a linked worktree.**
  A worktree stays on its one branch for its whole life. Movement goes through
  `EnterWorktree` / `ExitWorktree` only. A bare `git checkout <base>` in a worktree detaches HEAD
  → the branch becomes fair game (a following `git branch -d` then eats it). Anything that
  checks out implicitly — including `gh pr merge`'s post-merge branch-delete flag — is forbidden
  for the same reason. Every branch-moving step runs in the main checkout only.
- **Worktree probe (defined once, used everywhere):**
  `is_main_checkout() { [ "$(git rev-parse --path-format=absolute --git-dir)" = "$(git rev-parse --path-format=absolute --git-common-dir)" ]; }` —
  in the main checkout `--git-dir` and `--git-common-dir` are the same, in a linked worktree they
  differ. `--path-format=absolute` (git ≥ 2.31) is mandatory on **both** sides: without
  normalisation the test compares output formats instead of locations, because `--git-dir`
  answers absolutely from a subdirectory (`<main-root>/.git`) while `--git-common-dir` answers
  relatively (`../../.git`) — the probe then reported `WORKTREE` inside the main checkout
  (observed 2026-08-18). Every branch-moving block guards
  `if is_main_checkout; then …; else … (worktree path) fi`. Because ground-rule prose is not
  sourced into each Bash subshell, the affected blocks (8.3 / 8.4) inline the raw
  `[ … = … ]` test themselves; `is_main_checkout` is the named intent.

---

## Phase 0 — Recon (read-only)

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name   # = BASE
git branch --show-current                                         # = HEAD
git status --short
git log --oneline origin/<base>..HEAD
```
- PR number = `$ARGUMENTS` when set, otherwise `gh pr view --json number,state,headRefName` for
  the current branch.
- **Check the PR state** (`gh pr view <nr> --json state -q .state`): `MERGED` / `CLOSED` →
  **STOP** (nothing to ship).
- **STOP** when: branch == BASE and there are uncommitted changes (the work belongs on a feature
  branch → offer one); detached HEAD.

### 0.1 — Resumption guard (detect re-entry, NO re-run loop)

The workflow tool (Phase 4) runs in the background: the turn ends, and when the review is done a
`<task-notification>` re-invokes the main loop — `/nw-ship-pr` is then called a second time from
the top. As long as the PR is `OPEN`, the MERGED/CLOSED stop above does not fire, so
commit → push → PR → review would run again. **Guard at the very top of Phase 0**, before the
normal flow continues:

The call-form rule from Phase 4 applies here too: **single, simple calls**, paths inserted
literally — a `cat "$cand"` in a loop over computed paths is refused in a worktree-isolated
session.

```bash
git rev-parse HEAD                                              # -> <sha>
git rev-parse --show-toplevel                                   # -> <wt-root>
git rev-parse --git-common-dir                                  # -> <main-root>/.git
# Exclude the marker from the cleanliness check: it sits in the working tree as soon as the
# checkout-local candidate has been written, and in a repo without the .gitignore line
# (Phase 6.5 writes it uncommitted into the MAIN checkout only) it would otherwise flip
# condition 1 below and disarm exactly the re-entry guard it is supposed to prove.
git status --short -- ':(exclude).claude/.ship-pr-state.json'   # -> DIRTY (empty == clean)
git rev-list --count origin/<branch>..HEAD                      # -> AHEAD (0 == no new commit)
```

Then read each candidate **individually** (`cat`, literal path; "does not exist" is not an error)
and compare its `head_sha` yourself against `<sha>` — **the first MATCHING one counts**, not the
first existing one, otherwise a stale marker in the main root masks the valid one in the checkout:

```bash
cat <wt-root>/.claude/.ship-pr-state.json 2>/dev/null
```
```bash
cat <main-root>/.claude/.ship-pr-state.json 2>/dev/null
```

**Re-entry detected** (→ straight to **Phase 5**, do NOT repeat phases 1-3) when ALL hold:
- `DIRTY` empty (nothing new to commit — the command's own marker does not count as "new"), AND
- `AHEAD == 0` (no new local commit since the last push), AND
- an open PR exists (`gh pr view <nr> --json state -q .state` == `OPEN`), AND
- **a review for exactly this HEAD is demonstrably already triggered** — by ONE of two witnesses:
  - one of the two markers read above carries `head_sha` == `<sha>`, **OR**
  - in THIS session a `nw-ship-pr-review` workflow was already started for this HEAD (a task
    notification / task id is in context). A second witness exists because the marker write can
    fail (see Phase 4) — without it, a re-entry pays for a second review.

Then: consume the workflow result or wait for its completion → **Phase 5**. No re-commit,
re-push, or re-PR.

**Critical distinction** (otherwise the guard blocks a legitimate "fix the findings first" from
Phase 6): **new local commits since the push (`AHEAD > 0`) ⇒ a genuine second run** (findings
fixed, the review MUST run again) → the guard does not fire, normal flow. **No new commits ⇒
notification re-entry** → resume.

No witness / a marker with a different SHA → the guard does not fire, normal flow from Phase 1.
That is the **normal case of a first run** on an already committed and pushed branch with an open
PR: clean `status`, `AHEAD == 0`, PR `OPEN` — and still NO re-entry. Therefore **never** weaken
the first three conditions to compensate for a missing marker: they cannot distinguish a first
run from a re-entry. The `status` / `AHEAD` / PR part only prevents a re-commit and re-push — the
second review is prevented by the witness alone.

### 0.2 — Load the config (`.claude/ship-pr.local.md`, read-only)

Per-repo config for the follow-up sink, the worktree cleanup default, and the validation
commands (written on first run in Phase 6.5, see below). Read only here (Phase 0 stays
read-only):

```bash
CFG=<main-root>/.claude/ship-pr.local.md   # insert literally — 0.1 already resolved the path
if [ -f "$CFG" ]; then
  FM=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$CFG")   # $CFG stays call-local
  SINK=$(echo "$FM" | grep '^followup_sink:'           | sed 's/followup_sink: *//;s/^"\(.*\)"$/\1/')
  BACKLOG=$(echo "$FM" | grep '^backlog_path:'         | sed 's/backlog_path: *//;s/^"\(.*\)"$/\1/')
  WT_DEFAULT=$(echo "$FM" | grep '^worktree_cleanup_default:' | sed 's/worktree_cleanup_default: *//;s/^"\(.*\)"$/\1/')
fi
```

**`validate_commands`** is a YAML list, so it is extracted as a slice rather than a single grep.
Take the lines between the key and the next top-level key, keep the `- ` items, strip the dash:

```bash
VALIDATE=$(printf '%s\n' "$FM" | sed -n '/^validate_commands:/,/^[a-z_]*:/p' \
           | grep '^[[:space:]]*- ' | sed 's/^[[:space:]]*- *//')
```

An absent, empty, or unreadable key yields an empty list — which means the Phase 4.5 gate
**SKIPs**. It is never a failure.

Missing config → the fields stay empty; only when needed (Phase 6.5) are they asked for and
written. Auto-gitignore: `.claude/*.local.md` covers the config; the marker
`.ship-pr-state.json` is gitignored in addition (Phase 6.5 / Phase 4 write it).

**Sharing state with a `coding-suite` install is safe and intentional.** Both use
`.claude/.ship-pr-state.json` and `.claude/*.local.md`. The marker's meaning is identical in both
("a review was triggered for this SHA"), so a cross-read prevents a duplicate review instead of
causing one, and `validate_commands` is additive — the other reader greps only its own three
fields and ignores it.

## Phase 1 — Commit (if there are uncommitted changes)

When `git status --short` shows something: look at the diff, formulate a meaningful message
(what + why), **show it to the user**, stage only the relevant files (strays / generated files
out; when in doubt, ask), commit. **NEVER stage `.claude/.ship-pr-state.json`** — the command's
own resumption marker never belongs in a commit, not even in a repo whose `.gitignore` does not
list it yet. If on BASE: `git switch -c <name>` first (creating a new branch is allowed
everywhere; it is moving onto an *existing* branch that is forbidden in a worktree).

## Phase 2 — Push

```bash
git push -u origin <branch>
```
Check the result (no silent fail).

## Phase 3 — Ensure the PR exists

Find the open PR; if there is none → `gh pr create --base <base> --head <branch>` with a title
and body (the body ends with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`). Remember the PR number.

## Phase 4 — Trigger the review workflow (engine)

Call the **Workflow tool** — the script does the fan-out (explanation agent + parallel review
dimensions correctness / security / quality with adversarial verification).

**Name resolution (in THIS order — plugin workflows are `<plugin>:<name>` namespaced):**
1. **`name: "neurawork-cc-harness:nw-ship-pr-review"`** — primary. The workflow lives in this
   plugin (`meta.name: nw-ship-pr-review`) and the runtime registers it namespaced. The bare name
   `nw-ship-pr-review` does NOT resolve (`not found`) → no trial and error, call it namespaced
   right away.
2. `scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/nw-ship-pr-review.js"` — deterministic fallback
   (`${CLAUDE_PLUGIN_ROOT}` is set when this command runs from the harness plugin; resolve it via
   `echo "$CLAUDE_PLUGIN_ROOT"` if the tool call does not expand env vars).

```
Workflow({
  name: "neurawork-cc-harness:nw-ship-pr-review",
  args: {
    base: "<base>", head: "<branch>", pr: <nr>,
    context: "<1-2 sentences: what was done in this session/branch and why; empty if unknown>"
  }
})
```
- **`context`** is filled by the main loop from session knowledge (intent a fresh diff agent
  cannot know).

**Write the state marker (against the re-run loop, see Phase 0):** immediately AFTER the workflow
launch, record the review state for this HEAD so that a re-entry (the workflow tool runs in the
background → the turn ends → the completion notification re-invokes the main loop) does NOT
restart the command from the top:

❌ **NEVER write it with the Write/Edit tool — Bash only.** A Write to a `.claude/` path OUTSIDE
the session cwd is refused, and the error message is a terse "Error writing file" that is easy to
wave through: on 2026-08-18 the marker stayed silently unwritten this way.

❌ **AND NEVER as one compound Bash call with a computed target.** In a worktree-**isolated**
session the harness checks the *form* of the command, not the target: a redirect to a path
computed at runtime (`> "$cand"`, `> "$WT_ROOT/…"`) is **refused wholesale** — *"too complex to
verify that it stays inside the worktree"* — and refused before anything runs. A candidate loop
therefore fails as a whole: no marker, and no error from inside the block either, because the
block never executes. A **single, literal** redirect does go through, even into the main root
(empirically, 2026-08-18).

So the main loop writes the marker in **separate, individually simple calls** and inserts the
paths and values **literally** (it knows them: `<sha>` from Phase 0, `<nr>` / `<branch>` from
Phase 3). Resolve the paths first — pure read calls, no redirect inside them:

```bash
git rev-parse HEAD                # -> <sha>
git rev-parse --show-toplevel     # -> <wt-root>  (in the main checkout == <main-root>)
git rev-parse --git-common-dir    # -> <main-root>/.git  → <main-root> is its parent
```

Then **call 1 — the session's own checkout** (always allowed, even isolated; hence first):

```bash
printf '{"head_sha":"<sha>","pr":"<nr>","branch":"<branch>"}\n' > <wt-root>/.claude/.ship-pr-state.json
```

**Call 2 — verification** (its own call, otherwise it is a compound again):

```bash
test -s <wt-root>/.claude/.ship-pr-state.json && echo marker-ok
```

**Call 3 — main root, optional.** It survives `worktree remove` and a new session but is
dispensable: if it fails or is refused, **continue without consequence** — call 1 already wrote
the witness.

```bash
printf '{"head_sha":"<sha>","pr":"<nr>","branch":"<branch>"}\n' > <main-root>/.claude/.ship-pr-state.json
```

(If a `.claude/` directory is missing, `mkdir -p <literal-path>` as its **own** call first.)

Both candidates share the same **relative** path and are therefore covered by the same
`.gitignore` line (Phase 6.5) and the same 8.0b artifact filter, without changing either.
`$(git rev-parse --git-dir)` is NOT usable as a candidate: in a worktree it points at
`<main-root>/.git/worktrees/<name>`, i.e. outside every working tree.

**Three outcomes, handle all of them:**
1. **Call 1 green** (`marker-ok`) → continue normally, the marker sits in the session's checkout.
2. **Call 1 red** (error OR refused by the harness — both count the same) → in the message that
   ends this turn, say explicitly: *"A review for `<sha>` is already running, the marker could not
   be written, the resumption guard hangs on session context alone: a re-entry must NOT start a
   second review."* That gives the resuming turn the witness in context (Phase 0.1, second
   witness) even without the file.
3. **Call 3 red / refused** → say nothing, do nothing. Not a failure case.

(The marker is deleted again in Phase 9 after the merge. Gitignored — see Phase 0.)

The script runs headless and returns:
`{ explanation:{changed,purpose,verification,risk}, findings:[…], blocking_count, total_findings }`.

**Null / error fallback:** if the workflow returns `null`, has no `explanation`, or fails → **do
NOT continue to the gate**. Instead: one re-run; if it is empty again → an inline mini-review
(read the diff yourself and assess it briefly) as a fallback, OR STOP with an explanation.
**Never merge unreviewed.**

## Phase 4.5 — Validation gate (deterministic, local, config-driven)

**Runs the repo's own validation commands — no LLM, no workflow.** It runs on the turn that
continues to Phase 5 (including on a re-entry, Phase 0.1), **before** the explanation is built —
not on the turn that starts the background review (that one ends immediately). Local and
synchronous, independent of the review workflow.

Input is `validate_commands` from Phase 0.2. **Absent or empty → gate `SKIP`, no block.**
Otherwise run each command **in the shipped checkout** — `<wt-root>` from Phase 0.1, inserted
literally — **each in its own Bash call**, and record its exit status:

```bash
cd <wt-root> && <command 1>; echo "exit=$?"
```
```bash
cd <wt-root> && <command 2>; echo "exit=$?"
```

Insert the commands and the path literally, one call each — a loop over a computed list hits the
same call-form refusal as the marker write in Phase 4.

**`<wt-root>`, never `$MAIN_ROOT`** — this is the whole point of the gate. The documented flow is
`/nw-worktree` → work in the sibling worktree → `/nw-ship-pr` from there, and the main checkout
holds `<base>`, not the PR branch (8.1 and 8.4 rely on exactly that). A gate anchored to the main
checkout would run the repo's tests against **base** and never see the shipped commits: `GREEN`
for a PR that breaks the suite, `RED` for a base failure the PR actually fixes — and a command the
PR itself introduces (a new test directory, say) would find nothing there at all. In the main
checkout `<wt-root>` is the main root, so the same line is correct in both cases. If one command
genuinely needs the main checkout's environment, anchor **that** command to `$MAIN_ROOT` and say
why in the config comment — never move the whole gate off the branch.

**Interpretation (robust, never a false block):**
- **Empty list / no config** → **SKIP**, no block, no question.
- **A command is not installed at all** (`command not found`, missing runner) → **skip that
  command with a named reason** — an infrastructure fact, not a validation failure. If nothing
  could run, the whole gate is `SKIP`.
- **Any command exits non-zero** → gate **RED**. Carry the verdict (the failing command plus the
  shortest decisive output line) into Phase 5 / Phase 6. **No hard exit here** — the block
  deliberately takes effect only at the approval gate (Phase 6), so the override path exists.
- **All commands that ran exited 0** → **GREEN**.

The list is whatever the repo declares authoritative — for this repo, the test and lint commands
in its `CLAUDE.md`. That is why the gate is a list of commands rather than one hardcoded tool: it
covers tests, not only types, and it never reports a permanent `SKIP` because some tool the repo
does not use is missing.

## Phase 5 — Explanation (the heart of it)

Present it to the user briefly and clearly, fed by the workflow result:
1. **What changed** — `explanation.changed`
2. **Which problem was solved / feature implemented** — `explanation.purpose`
3. **How it was verified** — `explanation.verification`
4. **Risk / irreversible steps** — `explanation.risk`
5. **Review findings** — `findings`, **blocking first** (`blocking_count`). None → "no blockers".
6. **Validation gate** (Phase 4.5) — `GREEN` | `RED (command X failed: …)` |
   `skipped (reason)`. **RED feeds the approval gate** (Phase 6): treat it like a blocking finding.

**Augment:** reconcile the workflow `explanation` with your own session knowledge and add to it
(the main loop often knows the intent more precisely than the diff agent). **Mark contradictions
explicitly** between what the diff implies and what the session context says.

**Findings handling (do not over-fix):** only **blocking** findings justify a fix before the
merge. **nice-to-have** = list informatively, do NOT fix automatically — the user decides at the
gate (often: merge, address later). No fix loop over small stuff.

## Phase 6 — Approval gate (MANDATORY)

**AskUserQuestion**: "Merge PR #<nr>?"
- **Approve & merge** → Phase 7. (When `blocking_count > 0` **OR the validation gate is RED**:
  warn explicitly — name the failing command — so the override is a conscious choice.)
- **Fix findings first** → back to Phase 1 (fix → commit → review again).
- **Fix validation failures first** (only offer this when the gate is RED) → back to Phase 1 (fix
  → commit → Phase 4 review + Phase 4.5 gate again).
- **Cancel** → merge nothing, branch and PR stay. Report.

**Without explicit approval, do NOT merge.**

## Phase 6.5 — Follow-up capture (BEFORE the merge)

Runs **only** after the gate decision "approve & merge". After "fix findings first", "fix
validation failures first", or "cancel" no merge follows — then this step is skipped.

The **non-blocking** findings from the review (severity `nice-to-have`) PLUS every `blocking`
finding the user consciously overrode at the gate ("merge anyway") are persisted here instead of
being lost. **If there are 0 deferred findings → skip this step entirely** (no question, no
write, no empty commit).

**Why before the merge and not after:** the `backlog-file` sink writes relatively, i.e. into the
working tree of the branch being shipped. After the merge the entry no longer reaches the PR and
stays behind as an uncommitted change; from a worktree, `git worktree remove` (8.4) even deletes
it without comment. Both inputs of this step — the `nice-to-have` findings from Phase 5 and the
`blocking` findings overridden at the gate in Phase 6 — are already settled at this point, so
nothing is missing here.

Sink per config (`$SINK` from Phase 0.2):
- **`backlog-file`** (default when `$BACKLOG` exists): append one line per finding to `$BACKLOG`
  (default `.claude/PRPs/feature-backlog.md`):
  ```
  - [ ] **<finding.title>** — <finding.why>  (`<finding.file>:<finding.line>`, ship-pr deferred #<nr>)
  ```
  **De-dup**: a finding whose `title` is already in the backlog is NOT appended again.
  Then commit + push so the entry travels with the PR. **Every command MUST be anchored to
  `<wt-root>`** (the shipped checkout from Phase 0.1, inserted literally — call-form rule from
  Phase 4). Two reasons, both binding: `$BACKLOG` comes from the config call in Phase 0.2 and is
  **call-local** there — the variable is empty here; and no earlier phase leaves the Bash cwd on
  the shipped branch, since the cwd resets between calls and any phase may have `cd`-ed elsewhere.
  Unanchored, the commit would therefore risk running in the MAIN checkout on `<base>`, and
  `git push` would push it **straight to `origin/<base>`** — past the PR review, and the entry
  would again not reach the PR. First the branch assertion, then the three commands:
  ```bash
  git -C <wt-root> rev-parse --abbrev-ref HEAD    # MUST be <branch> — otherwise STOP, do not commit
  ```
  ```bash
  git -C <wt-root> add <wt-root>/<backlog-path>
  git -C <wt-root> commit -m "docs(backlog): capture the findings deferred at PR #<nr>"
  git -C <wt-root> push
  ```
  Commit trailer as in the ground rules. The push must be **through** before Phase 7 queries
  mergeability — otherwise Phase 7 judges a state GitHub does not know yet. (`mergeable` briefly
  drops to `UNKNOWN` after the push; the `UNKNOWN` branch in Phase 7 covers that.)
- **`github-issues`**: per finding
  `gh issue create --title "<finding.title>" --body "<why> · <file>:<line> · ship-pr #<nr>"`.
  Writes outward, so nothing to commit. In a repo without a GitHub remote → report quietly, do
  not crash.
- **`none`**: write nothing, name the findings in the Phase 9 report only.

**First run (no `.claude/ship-pr.local.md`):** ask once via `AskUserQuestion` for the sink AND the
validation commands, then write the config into the **MAIN checkout** (survives
`worktree remove`).

- **Sink proposal**, probed in this order: `.claude/PRPs/feature-backlog.md`, then
  `.claude/BACKLOG.md`, then fall back to `github-issues`.
- **`validate_commands` proposal**: the repo's authoritative commands when they are readable from
  its `CLAUDE.md` (build / test / lint section) — propose exactly those. When no source of truth
  is readable, propose an **empty list** rather than guessing; an empty list is a clean `SKIP`,
  a guessed command is a false block waiting to happen.

```bash
cat > "$MAIN_ROOT/.claude/ship-pr.local.md" <<EOF
---
followup_sink: <backlog-file|github-issues|none>
backlog_path: <.claude/PRPs/feature-backlog.md  # backlog-file only>
worktree_cleanup_default: ask   # ask | remove | defer
validate_commands:              # empty or absent → Phase 4.5 SKIPs
  - <command 1>
  - <command 2>
---

# ship-pr local config (per-repo, gitignored). Edit + re-run /nw-ship-pr to change.
EOF
# idempotent auto-gitignore (shares the rule with the nw-worktree skill config):
GI="$MAIN_ROOT/.gitignore"
grep -qxF '.claude/*.local.md'      "$GI" 2>/dev/null || printf '\n# ship-pr / worktree skill local config\n.claude/*.local.md\n' >> "$GI"
grep -qxF '.claude/.ship-pr-state.json' "$GI" 2>/dev/null || printf '.claude/.ship-pr-state.json\n' >> "$GI"
```

The first run belongs in this step: a sink choice that only ran after the merge could never serve
the run that needs it. Therefore the capture exists **exactly once** in this file, here — no
second block in Phase 8.x.

**Two deliberately unhandled points:**
- If `$BACKLOG` has grown on `<base>` meanwhile, the merge in 8.1 can conflict on that file. That
  is the already-covered `CONFLICTING` path from Phase 7, not a new case — no special handling.
- After the backlog commit, the resumption marker from Phase 4 carries a stale `head_sha`. Without
  consequence, because Phase 9 deletes it shortly after — not a defect, do not "repair" it.

## Phase 7 — Pre-merge checks

```bash
gh pr checks <nr>          # exit: 0=all pass | 8=pending | 1=failures | "no checks" (non-zero, no checks)
gh pr view <nr> --json mergeable,mergeStateStatus
```
Interpretation (robust):
- **Checks red (failures)** → STOP, inform the user.
- **Pending** → wait / ask, do not merge blindly.
- **"no checks found"** (repo without CI) → **OK, continue** (not every repo has CI — no false
  block).
- `mergeable=UNKNOWN` → **no verdict, query again.** GitHub computes mergeability asynchronously,
  and Phase 6.5 just pushed — right afterwards `UNKNOWN` is the normal case, not a special one.
  Neither `MERGEABLE` nor `CONFLICTING`: waving it through here decides on a state GitHub has not
  evaluated yet. Re-query up to **3×** a few seconds apart until `MERGEABLE` or `CONFLICTING`
  stands; if it stays `UNKNOWN` → STOP and tell the user GitHub is still computing.
  ```bash
  gh pr view <nr> --json mergeable,mergeStateStatus   # repeat until != UNKNOWN (max 3×)
  ```
- `mergeable=CONFLICTING` → `gh pr merge` will fail. Offer a rebase / `gh pr update-branch <nr>`
  instead of merging blindly.
- `mergeStateStatus=BLOCKED` (branch protection, missing approvals) → STOP, explain what is
  missing.

## Phase 8 — Merge + cleanup (worktree-aware)

(The number **8.2** is deliberately free: the follow-up capture lives as Phase 6.5 before the
merge. The gap stays so 8.3 / 8.4 keep their established numbers.)

### 8.0 — Capture contract (NO flush — the harness redirects at the hook layer)

First check whether the session runs in a worktree:

```bash
[ "$(git rev-parse --path-format=absolute --git-dir)" != "$(git rev-parse --path-format=absolute --git-common-dir)" ] && echo WORKTREE || echo MAIN
```

When **WORKTREE**: state in the report that no flush exists and none is needed — this session's
capture is **already** redirected into the main checkout. Every harness capture hook resolves its
output directory through `_shared/gitctx.effective_output_dir()` / `state_home()` and maps the
worktree path back onto the main checkout **before** writing
(`knowledge-compiler/payload/hooks/session-end.py`,
`knowledge-compiler/payload/hooks/pre-compact.py`,
`claudemd-lerner/payload/hooks/cl-session-end.py`), and both compile gates refuse to run inside a
worktree at all (`knowledge-compiler/payload/hooks/session-start.py`,
`claudemd-lerner/payload/hooks/cl-session-start.py`), so a worktree session never pollutes the
feature PR with auto-doc edits either.

**No subprocess, no failure handling.** There is no manual flush entry point in any harness hook,
and porting one from elsewhere would recreate a problem this harness does not have. The one
requirement the invariant still needs is the one 8.4 already enforces: **the worktree is never
removed while the session is still inside it.**

When **MAIN**: nothing to say — capture writes where it always does.

### 8.0b — Gitignored-artifact gate (worktree ONLY, BEFORE the merge)

A worktree is a fresh checkout → it starts with **zero** ignored files. Everything
`git ls-files -o -i` shows here was produced by **this session**. `git worktree remove` refuses on
untracked/modified files (needs `--force`) — but it does **NOT** block on ignored files; those are
deleted without comment on removal. Exactly here (in the worktree, before merge/remove, while
everything still exists) check whether gitignored artifacts are hanging off the branch:

```bash
ARTIFACTS=$(git ls-files -o -i --exclude-standard --directory \
  | grep -vE '(__pycache__|\.(pytest|mypy|ruff)_cache|node_modules|\.venv|\.next/|/dist/|\.pyc$|tsbuildinfo$|catalog/\.shards/|reports/|\.ship-pr-state)')
[ -n "$ARTIFACTS" ] && printf '⚠ gitignored worktree artifacts — lost on remove:\n%s\n' "$ARTIFACTS"
```

- **`$ARTIFACTS` empty** → continue quietly, no gate, no question.
- **not empty** → show the list + `AskUserQuestion` *"These gitignored artifacts are lost on
  worktree cleanup — what now?"*:
  - **Copy into main** → rescue each file into the main checkout via
    `cp -a <path> "$MAIN_ROOT"/<path>` (directories with `mkdir -p` first), then continue
    normally. Survives `remove`.
  - **Keep the worktree** → force the cleanup in 8.4 to **"later"** (do NOT remove the worktree),
    otherwise merge normally.
  - **Don't care, continue** → discard consciously, continue normally.

(The filter only drops generic build/cache/tooling debris plus the harness's own gitignored
output dirs — `catalog/.shards/` and `reports/`. If a real artifact is wrongly filtered out, it
shows up in a manual look at the unfiltered `git ls-files -o -i` — when in doubt, run it without
the `grep`.)

### 8.1 — Merge (worktree-safe, NO implicit checkout)

```bash
# gh pr merge's post-merge branch-delete flag is FORBIDDEN: from a worktree it triggers a local
# `git checkout <base>` and aborts with `fatal: '<base>' is already checked out at <main>`
# (exit 128). The GitHub-side merge is through by then, but gh stops BEFORE deleting → the remote
# branch is left behind. So delete the remote separately and checkout-free — AND only AFTER a
# successful merge (`&&`), otherwise a failed merge would delete the branch of an unmerged PR:
gh pr merge <nr> --merge \
  && { git push origin --delete <branch> 2>/dev/null || echo "remote branch already gone (delete_branch_on_merge?)"; }
```
- **Uniform** for MAIN and worktree — `git push origin --delete` performs no local checkout and
  works from both. The `|| echo` swallows the "remote ref does not exist" case when the repo
  setting `delete_branch_on_merge` already removed the remote.
- **The local branch** is NOT deleted here — 8.3 does it (MAIN: `git branch -d`) or 8.4
  (worktree: `git -C "$MAIN_ROOT" branch -d`).
- **The rule behind it:** anything that implicitly runs `git checkout <base>` breaks from a linked
  worktree — base is active in the main checkout. In the 8.x worktree paths always use
  `git -C "$MAIN_ROOT" …` plus checkout-free remote ops.

### 8.3 — Cleanup (MAIN checkout)

Only when the session is NOT in a worktree (probe from 8.0 → `MAIN`). The bare
`git checkout <base>` is **hard-guarded** (symmetric to 8.4, `is_main_checkout` from the ground
rules — inline here, because the prose is not sourced into the subshell). The prose in 8.0 alone
is NOT enough: were the `checkout` to run in a worktree by accident, it would detach HEAD and the
following `git branch -d` would eat the branch. In the worktree case the cleanup belongs to 8.4.
```bash
if [ "$(git rev-parse --path-format=absolute --git-dir)" = "$(git rev-parse --path-format=absolute --git-common-dir)" ]; then   # is_main_checkout
  git checkout <base>
  git pull --ff-only origin <base>
  git branch -d <branch> 2>/dev/null || true
  git remote prune origin
else
  echo "8.3 SKIP — session in a worktree; cleanup runs via 8.4 (NEVER a checkout here)."
fi
```

### 8.4 — Cleanup (worktree) — gated, executes itself

Only when the session is in a worktree (probe from 8.0 → `WORKTREE`). From inside the worktree
neither `git checkout <base>` works (base is active in the main checkout) nor
`git branch -d <branch>` (active branch) — so first **move** the session out of the worktree, then
clean up from the main root.

1. **Gate** (`worktree_cleanup_default` from Phase 0.2 steers it): on `ask` (default) via
   `AskUserQuestion` *"Clean up worktree `<worktree-path>` now?"* with the options
   **Remove now (recommended)** / **Later (manual, safe)** / **Skip**. On `remove` / `defer`
   choose the option automatically and only report it.

2. **Remove now:**
   ```
   ExitWorktree({ action: "keep" })
   ```
   tries to move the session back into the main checkout and clear cwd caches. **Three possible
   outcomes — all non-fatal:**
   - **(a) moved** (success): the session cwd is now the main checkout → its later natural
     SessionEnd hook captures into the main checkout as usual (and would have anyway — see 8.0).
     The guard below then removes.
   - **(b) no-op**: the worktree comes from an EARLIER session (no active EnterWorktree in this
     one) → ExitWorktree does nothing, the session stays in the worktree.
   - **(c) ERROR**: in a pinned/isolated session ExitWorktree refuses HARD
     (`cannot be called from a subagent with a cwd override`). **That is NOT a ship-pr failure —
     catch/ignore the tool error and continue.** The session stays in the worktree.

   In (b) + (c) the cwd stays the worktree → the hard guard below fires and skips the removal
   (falls back to step 3). **Never abort on the ExitWorktree error.**
   **Then** first clear the checkout-local marker — Phase 4 call 1 ALWAYS wrote it into the
   worktree, and `git worktree remove` aborts on an untracked file with
   `fatal: '<path>' contains modified or untracked files, use --force to delete it` (rc=128). In
   repos whose checked-out `.gitignore` does not carry the marker line yet, that is exactly the
   normal case (Phase 6.5 writes it uncommitted into the MAIN checkout only).
   Own call, literal path (call-form rule from Phase 4); Phase 9 repeats it idempotently:
   ```bash
   rm -f <worktree-path>/.claude/.ship-pr-state.json
   ```
   **Then** from the main root:
   ```bash
   # GUARD (hard blocking): the removal sequence runs ONLY when the session really left the
   # worktree (cwd == main checkout). `git worktree remove` does NOT refuse to delete the cwd
   # worktree — the guard MUST therefore skip the sequence, not merely warn. Otherwise it
   # destroys the session cwd (getcwd errors).
   if [ "$(git rev-parse --path-format=absolute --git-dir)" = "$(git rev-parse --path-format=absolute --git-common-dir)" ]; then
     git -C "$MAIN_ROOT" pull --ff-only origin <base>
     git -C "$MAIN_ROOT" worktree remove <worktree-path>
     git -C "$MAIN_ROOT" branch -d <branch>
     git -C "$MAIN_ROOT" worktree prune && git -C "$MAIN_ROOT" remote prune origin
   else
     echo "still in the worktree (ExitWorktree no-op OR error) → do NOT remove, fall back to step 3 (later)"
   fi
   ```
   **ExitWorktree no-op / error case:** if the session could not leave the worktree (no-op for a
   worktree from an earlier session, OR a hard error in a pinned/isolated session),
   `git-dir != git-common-dir` remains → the guard skips the removal. Then **print step 3
   (later)** and tell the user the worktree will be removed once this session is closed. NEVER
   remove the cwd worktree, NEVER abort on the ExitWorktree error.

3. **Later (manual, safe):** print the sequence only:
   ```bash
   # in the MAIN checkout, AFTER this worktree session has ended:
   rm -f <worktree-path>/.claude/.ship-pr-state.json   # otherwise: worktree remove rc=128 (untracked)
   git -C <main-root> pull --ff-only origin <base>
   git -C <main-root> worktree remove <worktree-path>
   git -C <main-root> branch -d <branch>
   git -C <main-root> worktree prune && git -C <main-root> remote prune origin
   ```

4. **Skip:** do nothing.

8.1 already deleted the remote branch explicitly (`git push origin --delete`, checkout-free — NOT
gh's post-merge delete flag, which breaks from a worktree); only the local branch and the worktree
directory are left here.

## Phase 9 — Report + state cleanup

First delete the resumption marker (merge is through → a future ship-pr starts clean): both
candidates from Phase 4, **each its own call with a literal path** (call-form rule):

```bash
rm -f <main-root>/.claude/.ship-pr-state.json
```
```bash
rm -f <wt-root>/.claude/.ship-pr-state.json
```
(In the main checkout it is twice the same path — the second `rm -f` is then a no-op.)

Report briefly:
- PR #<nr> merged (merge SHA), `<base>` up to date, branch gone remote + local.
- **Validation gate:** `GREEN` / `RED (overridden)` / `skipped (reason)`.
- **Follow-ups:** N findings written to `<sink>`, for `backlog-file` with the commit that carried
  them into the PR (or "none deferred").
- **Worktree:** removed | later (commands above) | n/a (main checkout).
- **Capture:** for a worktree session, the one-line 8.0 contract (redirected into the main
  checkout, nothing to flush).
- open / deferred items.

---

## Order mnemonic

`(resumption guard) → commit → push → PR → workflow review → validation gate → explain →
APPROVAL → follow-up capture → CI check → merge → cleanup`

Approval is the only manual gate (the worktree cleanup has its own, lighter gate). The review
fan-out runs in the workflow engine as `neurawork-cc-harness:nw-ship-pr-review` (namespaced;
`${CLAUDE_PLUGIN_ROOT}/workflows/nw-ship-pr-review.js` as the fallback), everything else in the
command. The resumption guard (Phase 0.1) prevents the background workflow notification from
restarting the command from the top.
