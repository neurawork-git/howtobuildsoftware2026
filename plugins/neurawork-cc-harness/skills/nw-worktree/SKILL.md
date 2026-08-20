---
name: nw-worktree
description: Create and immediately activate a Hand git worktree (session cwd switched into it) in one step, so pair-coding on a feature or phase can start without manual setup. Works in ANY git repo — on first run it detects the repo's worktree conventions (branch/name/slug patterns, PRD-based slug source, WSL/editor integration) and caches them in `<repo-root>/.claude/worktree.local.md`; later runs reuse the cache. Trigger on "/nw-worktree", "worktree for phase N", "worktree für phase N", "mach mir einen worktree", "neuer worktree", "new worktree", "worktree for <slug>", "setup worktree", "start phase N worktree", or any request to set up and enter a Hand worktree. NOT for ephemeral Agent/Archon worktrees (those live nested under `.claude/worktrees/` and belong to archon/subagent tooling), and NOT for plain branch switches (use git).
allowed-tools: Bash, Read, Write, Grep, AskUserQuestion, EnterWorktree
argument-hint: "[phase number | slug] [optional explicit slug]"
---

# Worktree Setup Skill

One command from `/nw-worktree <id>` to a session already working inside a fresh worktree —
no re-explaining the convention each time, in **any repo**. The repo-specific bits
(branch/name patterns, slug source, editor integration) are learned once per repo and
cached; the worktree-type convention below is universal.

## Universal pattern (every repo — FIXED, not detected)

Two worktree types, two locations, chosen by **purpose**:

| Type | Purpose | Location | Mechanism |
|------|---------|----------|-----------|
| **Hand** (human + Claude pair-coding) | **this skill** | **sibling** `<parent-of-repo>/<expanded-name>` | `git worktree add <sibling>` → `EnterWorktree {path}` |
| **Agent/Archon** (ephemeral, isolated) | archon / subagent runs | **nested** `<repo-root>/.claude/worktrees/<slug>` | `EnterWorktree {name}` / archon itself — gitignored, `git worktree prune` after merge |

**This skill only ever creates the Hand/sibling kind.** The location is never asked or
detected — Hand = sibling, always, in every repo. The nested kind is documented here only
so the split is clear; archon/subagent tooling owns it. Plain branch work → use `git`,
not this skill.

## Discipline (CRITICAL)

The Bash tool resets cwd to the original directory after **every** command. So:

- Resolve the repo root once: `ROOT=$(git -C "$PWD" rev-parse --show-toplevel)`.
- Use **absolute paths** everywhere (Read/Write/Edit), and `git -C "$ROOT"` for every git
  command. Never `cd` and rely on it persisting to the next command.
- Before edits inside a created worktree, verify the branch:
  `git -C "<worktree-path>" rev-parse --abbrev-ref HEAD`.
- **Scan discipline:** never run recursive tools (`grep -r`, tests, linters) blindly from a
  repo root that contains nested worktrees — scope to `git -C <wt>` or explicit paths.
- **NEVER run `git checkout <branch>` / `git switch <existing-branch>` inside a worktree.**
  This skill does it nowhere — it uses only `git worktree add -b` + `EnterWorktree`. A worktree
  stays on its one branch for its whole life; every movement goes through
  `EnterWorktree` / `ExitWorktree`. **Anyone extending this skill: never add a `git checkout ` here.**
  **Never add a `git switch ` onto an existing branch either** — a bare checkout inside a worktree
  detaches HEAD and makes the branch fair game for the next `git branch -d`. (The same rule guards
  `/nw-ship-pr` phases 8.3 / 8.4 via `is_main_checkout`.)

## Config file (`<repo-root>/.claude/worktree.local.md`)

Per-repo, gitignorable (`.claude/*.local.md`), the documented `.claude/<name>.local.md`
pattern. Holds the **variable** conventions only — location is fixed by the universal rule.

```markdown
---
enabled: true
schema_version: 1
# --- discovered conventions (variable per repo) ---
main_repo_path: /abs/path/to/repo          # git rev-parse --show-toplevel at recon
# NOTE: location is FIXED — Hand→sibling, Agent/Archon→.claude/worktrees. NOT a choice.
worktree_name_template: "{repo}-phase-{N}"  # tokens {repo} {id} {slug} {N} — Hand sibling name
branch_template: "phase-{N}-{slug}"         # tokens {id} {slug} {N}
id_scheme: phase-number                      # phase-number | free-slug
slug_source: prd-grep                         # prd-grep | arg-only | ask
prd_glob: ".claude/PRPs/prds/*-platform.prd.md"  # only when slug_source=prd-grep
prd_grep_template: "Phase {N}:"             # heading pattern to extract the title
base_ref: main                               # branch to pull/branch from
pull_before_branch: true
editor_unc: true                             # WSL→Windows: print `wslpath -w` UNC path
editor_note: "Zed Command Palette → workspace: add folder to project (CLI --add broken in WSL)"
---

# worktree skill config

Detected on first run. Edit any field and re-run `/nw-worktree`.
Delete this file to force a fresh RECON. Set `enabled: false` to disable the skill here.
```

**The path and the keys are deliberately the same** ones a `coding-suite` `/worktree` install
uses. A repo that has both keeps **one** profile instead of two that drift, and a repo that has
already run either skill needs no RECON here at all.

**Token expansion:**
- `{repo}` = basename of `main_repo_path`
- `{N}` = numeric id (only when `id_scheme: phase-number`)
- `{slug}` = derived slug (see `slug_source`)
- `{id}` = raw user arg (when `id_scheme: free-slug`)

---

## Stage 0 — Config check

1. `ROOT=$(git -C "$PWD" rev-parse --show-toplevel)`. If this fails → the user is not in a
   git repo; report that and stop (do **not** write any config).
2. `CFG="$ROOT/.claude/worktree.local.md"`. If it exists:
   - Parse the frontmatter:
     ```bash
     FM=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$CFG")
     ```
   - Read `enabled`. If `enabled` is not `true` → the skill is disabled in this repo; report
     and stop.
   - Load every convention field (`main_repo_path`, `worktree_name_template`,
     `branch_template`, `id_scheme`, `slug_source`, `prd_glob`, `prd_grep_template`,
     `base_ref`, `pull_before_branch`, `editor_unc`, `editor_note`).
   - **Skip to Stage 2 (CREATE).**
3. If `CFG` does not exist → proceed to **Stage 1 (RECON)**.

Read a field with the plugin-settings technique:
```bash
VALUE=$(echo "$FM" | grep '^field_name:' | sed 's/field_name: *//' | sed 's/^"\(.*\)"$/\1/')
```

---

## Stage 1 — RECON (first run only)

Detect the **variable** conventions. Detection-not-assumptions, fault-tolerant — a missing
tool degrades a single field, never aborts the run.

### Detection signals

| Field | Signal / command | Inference |
|-------|------------------|-----------|
| `main_repo_path` | `git -C "$PWD" rev-parse --show-toplevel` | repo root (already have it as `$ROOT`) |
| `editor_unc` | `grep -qi microsoft /proc/version && command -v wslpath` | WSL → `true`, else `false` |
| `id_scheme` + `slug_source` | does `<root>/.claude/PRPs/prds/*.prd.md` glob match? | yes → offer `phase-number`+`prd-grep`; no → `free-slug`+`ask` |
| `worktree_name_template` + `branch_template` | `git -C "$ROOT" branch --format='%(refname:short)'` → common prefix (`phase-`, `feature/`, none); plus any existing sibling worktree names from `git -C "$ROOT" worktree list` | seed a default; confirm with user |
| `base_ref` | `git -C "$ROOT" symbolic-ref refs/remotes/origin/HEAD` (strip `refs/remotes/origin/`); fallback `main` → `master` | default branch |

> **Location is never detected.** Hand = sibling is the fixed universal rule.

### Confirm + write

1. Build a **proposed profile** from the signals, with graceful defaults (no `wslpath` though
   `/proc/version` says microsoft → `editor_unc: false`; no PRD glob → `id_scheme: free-slug`,
   `slug_source: ask`; multiple PRD globs → first match, or ask).
2. Confirm via `AskUserQuestion` — one question: *"Detected worktree profile for `<repo>` —
   use it?"* with options:
   - **Accept detected** — use the inferred profile.
   - **Phase-numbered** — `phase-number` + `worktree_name_template: "{repo}-phase-{N}"` +
     `branch_template: "phase-{N}-{slug}"` + `slug_source: prd-grep`.
   - **Customize** — then ask follow-up questions for the 2-3 ambiguous fields.

   All options use the **sibling** location (universal Hand rule); they differ only in
   name/branch/slug derivation. Use each option's `preview` to show the resulting example
   sibling path + branch.
3. On resolution, `Write` `$ROOT/.claude/worktree.local.md` from the config schema above,
   filled with the chosen profile.
4. **Auto-gitignore the config** so it never gets committed by accident — append the pattern
   to `<repo-root>/.gitignore` if missing (idempotent):
   ```bash
   GI="$ROOT/.gitignore"
   grep -qxF '.claude/*.local.md' "$GI" 2>/dev/null \
     || printf '\n# worktree skill local config\n.claude/*.local.md\n' >> "$GI"
   ```
   This edits the working tree only (the user commits it with their next change). Doing it
   *before* any stash-carry below matters: `git stash -u` skips ignored files, so the now-ignored
   `worktree.local.md` stays put in the repo root instead of being carried into the worktree.
5. Report: which profile was cached, the config path, the `.gitignore` line added, and an
   example expansion. Then continue to **Stage 2**.

Do **not** invent a slug when `slug_source: ask` — ask. Do **not** write the config until the
user confirms.

---

## Stage 2 — CREATE + ACTIVATE

1. **Parse arg** → `{id}` / `{N}` per `id_scheme`. An explicit trailing slug in the invocation
   (e.g. `/nw-worktree 10 sovereign-hosting`) overrides slug derivation.
2. **Derive slug** per `slug_source`:
   - `prd-grep`: grep the title, then kebab-case it:
     ```bash
     grep -iE "$(echo "$prd_grep_template" | sed "s/{N}/$N/")" $ROOT/$prd_glob
     ```
     Slug rules — short and recognizable, not the whole title: lowercase, words joined by
     `-`; German umlauts → `ae/oe/ue`, `ß` → `ss`; drop punctuation and em-dash; keep the
     distinctive layer/feature words. Worked example: `Phase 10: Layer 4 — Souveränes Hosting`
     → `layer4-souveraen-hosting`. If grep returns nothing → ask the user for a one-word slug;
     do not invent one.
   - `arg-only`: use `{id}` directly as the slug.
   - `ask`: ask the user for a one-word slug.
3. **Expand** `worktree_name_template` + `branch_template` with `{repo}` / `{N}` / `{slug}` /
   `{id}`. Compute the sibling path:
   ```bash
   WT_PATH="$(dirname "$ROOT")/<expanded-name>"   # Hand = always sibling
   BRANCH="<expanded-branch>"
   ```
4. **Pull base** if `pull_before_branch`:
   ```bash
   git -C "$ROOT" pull --ff-only        # skip gracefully if no upstream
   ```
5. **Collision guard:**
   ```bash
   git -C "$ROOT" worktree list
   ```
   If `WT_PATH` or `BRANCH` already exists → either just activate the existing one (step 7) or
   report the conflict. Clean genuine stale/empty leftovers first:
   `git -C "$ROOT" worktree remove --force <path>` + `git -C "$ROOT" branch -D <branch>` +
   `git -C "$ROOT" worktree prune`.
6. **Carry pending work into the worktree.** A new worktree is branched from `HEAD`, so
   uncommitted changes and untracked files left in the repo root do **not** appear in it — work
   you started before `/nw-worktree` (e.g. a freshly-written plan) would be stranded in the main
   checkout. Detect and carry it:
   ```bash
   git -C "$ROOT" status --porcelain        # non-empty (ignored files excluded) ⇒ pending work
   ```
   If there is pending work, ask via `AskUserQuestion` how to handle it:
   - **Carry into worktree (default)** — stash including untracked, create the worktree, then pop
     the stash *inside* it (the stash is stored in the shared git dir, so it pops cleanly into the
     new tree since it branched from the same `HEAD`):
     ```bash
     git -C "$ROOT" stash push -u -m "worktree-carry: $BRANCH"   # -u = untracked too; ignored skipped
     # ... create the worktree (step 7) ...
     git -C "$WT_PATH" stash pop
     ```
   - **Commit on base first** — commit the pending work on the current branch before branching,
     so the new branch inherits it (only when it genuinely belongs on the base).
   - **Leave behind** — proceed; pending work stays in the repo root.

   If the tree is clean, skip straight to step 7. (The auto-gitignored `worktree.local.md` is
   ignored, so `stash -u` never carries it — the config stays in the repo root.)
7. **Create + (optional) UNC** (absolute paths only; the Bash cwd resets after each command):
   ```bash
   git -C "$ROOT" worktree add "$WT_PATH" -b "$BRANCH"
   ```
   If you stashed in step 6, pop it now: `git -C "$WT_PATH" stash pop`.
   If `editor_unc` is `true`:
   ```bash
   wslpath -w "$WT_PATH"     # print the Windows-UNC path to paste into the editor
   ```
   and surface `editor_note` alongside it.
8. **Activate.** Call `EnterWorktree` with `path: "$WT_PATH"` (it must already appear in
   `git -C "$ROOT" worktree list` from step 7). This switches the session cwd into the
   worktree so work starts immediately. (Note: `EnterWorktree { name }` would instead create a
   *nested* `.claude/worktrees/` tree — that is the Agent/Archon kind, not what we want here.)
9. **Report** back: worktree path, branch, the slug/phase title, what was carried (if any), and
   the UNC path (if any) to paste into the editor.
10. **Harness capture note (only if the harness is installed).** If any of
    `<root>/*/hooks/session-end.py`, `<root>/*/hooks/cl-session-end.py`, or
    `<root>/*/hooks/co-post-tooluse.py` exists, add one line to the report:
    *"Harness capture (knowledge-compiler / claudemd-lerner) from this worktree is redirected
    into the main checkout by `_shared/gitctx`, and both compile gates are suppressed inside a
    worktree — no manual step is needed. `/nw-ship-pr` never removes a worktree the session is
    still inside."* No action required — the SessionEnd/PreCompact hooks self-detect the
    worktree. If no harness install is present, omit the line entirely (graceful — never assume
    one is there).

---

## Config & re-detection

- Edit any field in `<repo-root>/.claude/worktree.local.md` and re-run `/nw-worktree` — it is
  read live each run (no restart needed).
- Delete the file to force a fresh RECON.
- `enabled: false` disables the skill in that repo.
- RECON auto-adds `.claude/*.local.md` to the repo `.gitignore` (Stage 1 step 4) so the config
  stays local — no manual step needed.

## Why these rules

- **Hand = sibling, Agent/Archon = nested** — Hand worktrees must be addable as an editor
  project root (sibling, visible); ephemeral agent worktrees stay nested and gitignored. This
  split is universal across repos.
- **`git -C "$ROOT"` everywhere** — the Bash cwd reset otherwise silently lands work in the
  main checkout instead of the worktree.
- **Pull before branching** — phases/features stack; a stale base causes painful rebases later.
- **Carry before stranding** — a new worktree branches from `HEAD` and ignores uncommitted /
  untracked work; without an explicit carry step, work begun before `/nw-worktree` is left behind
  in the main checkout. Stash-carry (untracked included, ignored skipped) moves it into the
  worktree cleanly.
- **Detect once, cache** — repo conventions differ (branch prefixes, slug sources, WSL); learn
  them once per repo rather than re-deriving or hardcoding one repo's convention everywhere.
- **The harness is worktree-aware at the hook layer, not here** — all four capture hooks resolve
  their output directory through `_shared/gitctx` and map a worktree path back onto the main
  checkout before writing, and both compile gates refuse to run inside a worktree at all. This
  skill therefore needs **no** wiring for them — it only surfaces the contract in its report
  (step 10) and stays fully functional in repos with no harness install.
