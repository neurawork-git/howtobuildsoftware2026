# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

This repository documents how to build software in 2026 and ships the tooling
that does it: **`neurawork-cc-harness`**, a Claude Code plugin (under `plugins/`)
that keeps a repo's project knowledge fresh. The plugin bundles two independently
installable skills — `knowledge-compiler` (distils session logs into a per-repo
knowledge base) and `claudemd-lerner` (keeps the `CLAUDE.md` hierarchy + `docs/`
current). Both write **inside the target repo, never under `.claude/`**.

This repo **self-hosts** both skills: `knowledge-base/` and `claudemd-lerner/`
are live installs of the harness into this repo itself.

## Build / test / lint / run commands

There is no compile step — the engines are interpreted Python (≥ 3.12, run via
[`uv`](https://docs.astral.sh/uv/)). LLM calls (compile / update / seed) need
`ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`; capture and scaffolding do not.

**Test** (stdlib `unittest`). A single top-level `discover` under-collects because
`engines/` and the hyphenated engine dirs are not importable packages — run
discovery per test directory. From `plugins/neurawork-cc-harness/engines/`:

```bash
python3 -m unittest discover -s _shared/tests
python3 -m unittest discover -s knowledge-compiler/tests
python3 -m unittest discover -s claudemd-lerner/tests
```

The tests use a real git temp repo and subprocess; they make no network/LLM calls.

**Lint:** `ruff` is configured (`line-length = 100`) in each `pyproject.toml`:

```bash
uvx ruff check
```

**Resolve engine deps** (after install / when adopting): `uv sync --directory <dir>`.

**Run the self-hosted harness in this repo:**

```bash
uv run --directory knowledge-base python scripts/compile.py   # distil daily/ → knowledge/
uv run --directory claudemd-lerner python scripts/update.py   # apply daily/ → CLAUDE.md + docs/
```

Both also run automatically via the `SessionStart` / `PreCompact` / `SessionEnd`
hooks in `.claude/settings.json` (a 6-hour `SessionStart` gate triggers compile/update).
Slash commands: `/neurawork-cc-harness:kc-compile` and `/neurawork-cc-harness:cl-update`.

## High-level architecture

- **`plugins/neurawork-cc-harness/`** — the distributed plugin source (see
  `plugins/CLAUDE.md`). Contains the plugin manifest (`.claude-plugin/plugin.json`),
  the two install skills (`skills/*/SKILL.md`), slash commands (`commands/`), and
  the Python install engines (`engines/`). Each engine has `install.py`, `recon.py`,
  a `payload/` (the code copied into a target repo), and `tests/`. `engines/_shared/`
  holds stdlib-only helpers reused by both engines.
- **`.claude-plugin/marketplace.json`** — repo-root marketplace manifest
  (`neurawork-harness`) that distributes the plugin via a `git-subdir` source.
- **`knowledge-base/`** — a live self-host install of `knowledge-compiler` (see
  `knowledge-base/CLAUDE.md`). Holds the engine machinery plus the tracked
  `knowledge/` wiki output.
- **`claudemd-lerner/`** — a live self-host install of `claudemd-lerner` (see
  `claudemd-lerner/CLAUDE.md`). Holds only machinery; its outputs are the repo-root
  `CLAUDE.md` hierarchy and `docs/`.
- **`docs/`** — longer-form guides: [`docs/INSTALL.md`](docs/INSTALL.md),
  [`docs/WHEN-TO-USE.md`](docs/WHEN-TO-USE.md),
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- Each skill's behaviour is specified by an `AGENTS.md` constitution copied into the
  install dir — the LLM (compiler / learner) follows it when synthesizing outputs.

## Conventions

- Engines are **stdlib-only** except for the SDK call paths; the only third-party
  runtime deps are `claude-agent-sdk`, `python-dotenv`, `tzdata` (see `pyproject.toml`).
- `engines/_shared/` is the **single source of truth** for shared helpers; every
  install refreshes the copied `_shared/` rather than diverging.
- Outputs (knowledge, CLAUDE.md, docs) are always written **inside the repo, never
  under `.claude/`** — enforced at runtime by `_shared/repo_guard.py`.
- Dates ISO 8601 (`YYYY-MM-DD`); timestamps full ISO with offset. File names
  lowercase, hyphenated. Doc prose is factual, neutral, instructive.
- No timezone is hardcoded — local time is read from the system.
- Invoke skills by their **fully qualified** names (`neurawork-cc-harness:…`):
  `knowledge-compiler` also exists in the `coding-suite` plugin.

## Key decisions

- **Knowledge/docs live in the repo, never under `.claude/`** — they are tracked,
  reviewable artifacts the agent reads, not hidden local state.
- **Two separate skills, coexisting in one repo** — `knowledge-compiler` and
  `claudemd-lerner` use distinct install dirs and distinct hook filenames
  (`cl-`-prefixed for the learner) so their `.claude/settings.json` entries never
  clobber each other.
- **No RAG / no embeddings** for the knowledge base — at repo scale an LLM reasoning
  over a curated `index.md` beats vector similarity. Revisit only past ~2,000
  articles / ~2M tokens. Rationale in `knowledge-base/AGENTS.md`.
- **Engine / payload split** — installs copy a `payload/` into the target and merge
  hooks idempotently; ADOPT mode refreshes code without clobbering existing data.
- **Subscription credentials are not sanctioned** for third-party plugin use; public
  installs must set an API key in the environment.

## Working principles

### 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
1. [Step] → verify: [check]
2. [Step] → verify: [check]

Strong success criteria enable independent looping. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
