# AGENTS.md — claudemd-lerner Constitution

This file is the specification the learner LLM follows when turning raw session
logs into an up-to-date **CLAUDE.md hierarchy** and **`docs/` tree**. Read it in
full before running an update or a seed.

> Lineage: this is a repo-local learner inspired by the LLM-as-compiler idea
> (Andrej Karpathy's LLM wiki, rebuilt openly by coleam00's claude-memory-compiler)
> and by the doc-maintenance pattern of NeuraWork's own coding-suite learner. The
> design here is independent NeuraWork work; only the underlying concept is shared.
> Unlike the knowledge-compiler, this learner builds **no** knowledge wiki — it
> only maintains the docs the agent already reads.

## The Learner Model

```
daily/        source code   — raw session logs, append-only, never rewritten
LLM           learner       — reads logs + the live repo, edits docs surgically
CLAUDE.md     executable     — the conventions/architecture the agent reads first
docs/         executable     — longer-form guides and design docs
```

Docs are never organised by hand. Sessions produce logs; the learner does the
synthesis and keeps the doc tree current. The learner EDITS existing files in
place — it does not maintain a separate wiki and does not rewrite from scratch.

## Where Things Go

The learner maintains three kinds of target, all **inside the repository** and
**never under `.claude/`**:

### Root `CLAUDE.md` (always)

The single most important file. Holds repo-wide, durable facts the agent needs on
every session:

- **Project purpose** — one or two sentences on what this repo is.
- **Build / test / lint / run commands** — the exact commands, copy-pasteable.
- **High-level architecture** — the major components and how they fit, with paths.
- **Conventions** — naming, structure, style rules that apply repo-wide.
- **Key decisions** — durable choices and their rationale (not session trivia).

### Area `CLAUDE.md` (only up to the configured depth)

For a repo with distinct areas, a `<area>/CLAUDE.md` holds notes specific to that
subtree (its own build/test quirks, local conventions, gotchas). Maintain these
**only down to `claudemd_depth`**: depth `1` = root `CLAUDE.md` only; depth `2` =
root + immediate subdirectories; and so on. Never create area files below the
configured depth, and never inside an excluded directory.

### `docs/` (longer-form)

The configured docs directory (default `docs/`) holds material too long for a
CLAUDE.md: guides, design docs, runbooks, architecture deep-dives. Create or
update a `docs/<topic>.md` when a session produces durable explanatory content
that would bloat CLAUDE.md.

## Daily Log Format

Session logs (the learner's input) use this shape, one file per day:

```markdown
# Daily Log: YYYY-MM-DD

## Sessions

### Session (HH:MM)

**Context:** what was being worked on.

**Conventions / Architecture:**
- a rule, pattern, or structural fact established this session

**Decisions Made:**
- decision with its rationale

**Commands:**
- a build/test/run command worth recording

**Lessons Learned:**
- gotcha or insight worth keeping in the docs
```

## Update Rules (daily/ + live repo → CLAUDE.md/docs)

1. Read the daily log(s), then the current root `CLAUDE.md`, then any area
   `CLAUDE.md` and `docs/` files the log touches. Use Glob/Grep/Read to ground
   every change in the **live repository** — confirm paths, commands, and names
   against the actual code before writing them.
2. **Prefer a surgical `Edit` over a rewrite.** Keep the existing structure,
   headings, ordering, and voice. Add or correct only what the session implies.
3. **Never invent.** Every statement must be grounded in the daily log or in a
   file you actually read. If something is uncertain, leave it out.
4. Respect the configuration: stay within `claudemd_depth`, write longer-form
   content under the configured `docs_dir`, write prose in the configured
   `language`, and ignore every path under `excluded_dirs`.
5. Put durable, repo-wide facts in the root `CLAUDE.md`; area-specific facts in
   the nearest in-depth area `CLAUDE.md`; long explanations in `docs/`.
6. Do not duplicate: if a fact already lives in a CLAUDE.md, update it in place
   rather than restating it elsewhere.
7. **Never write under `.claude/`** and never write outside the repository.

## Seed Rules (first install on an existing repo)

1. Read the README, every existing `CLAUDE.md`, the `docs/` tree, and a top-level
   source map — ignoring `excluded_dirs`. Open the files that look foundational.
2. Produce or **UPDATE** the root `CLAUDE.md` (purpose, commands, architecture,
   conventions, key decisions) and, up to `claudemd_depth`, area `CLAUDE.md`
   files. Refresh or create `docs/` entries for longer-form material.
3. If a root `CLAUDE.md` already exists, UPDATE it surgically — do not overwrite
   or discard hand-written content.
4. Use ONLY facts grounded in files you read. Do not guess. Write in `language`.

## Conventions

- Dates ISO 8601 (`YYYY-MM-DD`); timestamps full ISO with offset.
- Writing style: factual, neutral, instructive — these are docs an agent reads.
- Keep commands exact and copy-pasteable.
- Markdown headings stable across updates so diffs stay readable.
