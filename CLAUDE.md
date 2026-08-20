# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

This repository documents how to build software in 2026 and ships the tooling
that does it: **`neurawork-cc-harness`**, a Claude Code plugin (under `plugins/`)
that keeps a repo's project knowledge fresh. The plugin bundles three independently
installable skills — `knowledge-compiler` (distils session logs into a per-repo
knowledge base), `claudemd-lerner` (keeps the `CLAUDE.md` hierarchy + `docs/`
current), and `compliance-compiler` (parallel agents distil GDPR/SOC2/ISO27001 into
a tracked constraint catalog, and a `PostToolUse` hook validates PRP plans against
it). All write **inside the target repo, never under `.claude/`**.

This repo **self-hosts** all three skills: `knowledge-base/`, `claudemd-lerner/`,
and `compliance-base/` are live installs of the harness into this repo itself.

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
python3 -m unittest discover -s compliance-compiler/tests
```

A fifth suite covers the prompt-only assets (skills, commands, workflows) and runs from the
**plugin root**, not from `engines/` — from `plugins/neurawork-cc-harness/`:

```bash
python3 -m unittest discover -s tests
```

The tests use a real git temp repo and subprocess; they make no network/LLM calls.

**Lint:** `ruff` is configured (`line-length = 100`) in each `pyproject.toml`:

```bash
uvx ruff check
```

**Resolve engine deps** (after install / when adopting): `uv sync --directory <dir>`.

**Run the self-hosted harness in this repo:**

```bash
uv run --directory knowledge-base python scripts/compile.py     # distil daily/ → knowledge/
uv run --directory claudemd-lerner python scripts/update.py     # apply daily/ → CLAUDE.md + docs/
uv run --directory compliance-base python scripts/extract.py    # ~30 agents → catalog/*.json
uv run --directory compliance-base python scripts/capabilities.py    # constraints → catalog/capabilities.{json,md}
uv run --directory compliance-base python scripts/stack.py --scaffold  # refresh catalog/stack.json + gap report
uv run --directory compliance-base python scripts/validate.py <plan>  # check a PRP plan
uv run --directory stack-base python scripts/scope.py           # which capabilities apply, and why
uv run --directory stack-base python scripts/rank.py            # order each one's components
uv run --directory stack-base python scripts/selection.py       # render the selection sheet
uv run --directory stack-base python scripts/selection.py --apply <sheet>  # record the choices
```

The first two run automatically via the `SessionStart` / `PreCompact` / `SessionEnd`
hooks in `.claude/settings.json` (a 6-hour `SessionStart` gate triggers compile/update).
`compliance-compiler` adds only a `PostToolUse` hook that validates each PRP plan
write (nothing at `SessionStart` — that budget is left for the knowledge concepts);
its catalog ships prebuilt with the install and is rebuilt on demand via `co-extract`
(constraints) and `co-capabilities` (the derived capability layer + stack scaffold). A
`validate_frameworks` config key scopes which frameworks plans are checked against
(default: all extracted). Slash commands:
`/neurawork-cc-harness:kc-compile`, `/neurawork-cc-harness:cl-update`,
`/neurawork-cc-harness:co-extract`, `/neurawork-cc-harness:co-capabilities`, and
`/neurawork-cc-harness:co-validate`.

## High-level architecture

- **`plugins/neurawork-cc-harness/`** — the distributed plugin source (see
  `plugins/CLAUDE.md`). Contains the plugin manifest (`.claude-plugin/plugin.json`),
  the install skills (`skills/*/SKILL.md`), slash commands (`commands/`), and
  the Python install engines (`engines/`). Each engine has `install.py`, `recon.py`,
  a `payload/` (the code copied into a target repo), and `tests/`. `engines/_shared/`
  holds stdlib-only helpers reused by all engines. Alongside them live three **workflow
  surfaces** that install nothing and have no engine: `/nw-worktree` (create + enter a
  Hand worktree), `/nw-ship-pr` (commit → push → PR → review → validation gate →
  approval gate → merge → cleanup), whose review fan-out lives in
  `workflows/nw-ship-pr-review.js`, and `/nw-rules-init` (detect the repo's test runner,
  then write the baseline coding rules — scope, simplicity, evaluation-first — into the
  root `CLAUDE.md` as one idempotent block delimited by `neurawork-cc-harness:rules`
  BEGIN/END marker comments); `tests/` pins their guard invariants, including the block's 1,200-char budget.
  Marker blocks are **learner-protected**: `claudemd-lerner` snapshots every
  `owner:name` marker span before its SDK run and restores it byte-for-byte afterwards
  (`payload/scripts/markers.py`), so no tool-owned block is silently reworded.
- **`.claude-plugin/marketplace.json`** — repo-root marketplace manifest
  (`neurawork-harness`) that distributes the plugin via a `git-subdir` source.
- **`knowledge-base/`** — a live self-host install of `knowledge-compiler` (see
  `knowledge-base/CLAUDE.md`). Holds the engine machinery plus the tracked
  `knowledge/` wiki output.
- **`claudemd-lerner/`** — a live self-host install of `claudemd-lerner` (see
  `claudemd-lerner/CLAUDE.md`). Holds only machinery; its outputs are the repo-root
  `CLAUDE.md` hierarchy and `docs/`.
- **`compliance-base/`** — a live self-host install of `compliance-compiler` (see
  `compliance-base/CLAUDE.md`). Holds the engine machinery plus the tracked `catalog/`
  (GDPR/SOC2/ISO27001 constraint JSON + `index.md`, the derived
  `capabilities.{json,md}`, and the chosen-component `stack.json`);
  `catalog/.shards/` and `reports/` are gitignored. The engine
  uses a `co-`-prefixed `PostToolUse` hook (no `SessionStart`) so it coexists with
  the other two in `.claude/settings.json`. Extraction fans out ~30 parallel SDK agents
  (`asyncio.gather` + a semaphore) — the harness's only parallel compile path.
- **`stack-base/`** — a self-host install of `stack-compiler` (product scoping),
  **installed by hand**: its `install.py` / `recon.py` / slash commands land in a
  later phase, so `plugins/…/engines/stack-compiler/payload/` and `stack-base/` are
  kept byte-identical by `tests/test_payload_drift.py`, not by an installer. It owns
  **no data artifact**. Three passes, all writing into
  `compliance-base/catalog/stack.json` through `compliance-base/scripts/stack.py` —
  the single schema owner: `scripts/scope.py` decides per capability *whether* it
  applies and why (`--apply-scope`), `scripts/rank.py` orders each still-applicable
  capability's catalog components best-fit-first with a reason per position
  (`--apply-ranking`), and `scripts/selection.py` renders that ranking as an editable
  **selection sheet**, reads back the component a human wrote per capability, and
  records it (`--apply-selection`, which also stamps `chosen_from` so a later catalog
  change reopens exactly the affected choices). The first two read the tracked
  `product.md` and run parallel SDK agents; selection runs **no agent** — the
  proposal already exists — and needs no API key. It is named `selection.py`, not
  `select.py`, because a module named `select` in `scripts/` shadows the stdlib
  `select` and breaks the other two at import time. The component pool is closed — a
  ranking must name exactly that capability's `options`, once each, and a choice must
  come from them — and a deterministic gate (pool match + the catalog's own
  `license_policy`, honouring `verdict: "keep-exception"`) runs before every write; a
  failed gate writes nothing. Scoping and ranking are all-or-nothing; selection is
  deliberately partial, because an undecided capability stays a counted gap rather
  than a silent omission. `product.md` is tracked; `.shards/` and `reports/` are
  gitignored.
- **`docs/`** — longer-form guides: [`docs/INSTALL.md`](docs/INSTALL.md),
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
- Invoke skills by their **fully qualified** names (`neurawork-cc-harness:…`) so an
  install always resolves to this plugin regardless of what else is enabled.

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
