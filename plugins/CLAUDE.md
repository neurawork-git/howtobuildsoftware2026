# CLAUDE.md — plugins/

The distributed Claude Code plugin lives here at
`plugins/neurawork-cc-harness/`. This is the **source** that the repo-root
marketplace (`.claude-plugin/marketplace.json`, name `neurawork-harness`) ships
via a `git-subdir` source — it is what users install, not this whole repo.

## Layout

- `.claude-plugin/plugin.json` — plugin manifest (`name`, description, author, MIT).
- `skills/<skill>/SKILL.md` — the three **install skills** (`knowledge-compiler`,
  `claudemd-lerner`, `compliance-compiler`). Each runs a three-phase flow: **Recon**
  (read-only) → **Ask** (AskUserQuestion) → **Execute** (run `install.py`). Plus the
  **workflow skills** `nw-worktree` (create + enter a Hand worktree) and
  `nw-rules-init` (write the marker-delimited baseline coding rules into the target's
  root `CLAUDE.md`), which install nothing — see the gotcha below.
- `commands/` — slash commands `kc-compile.md`, `cl-update.md` (manual compile /
  update; bypass the SessionStart 6-hour gate), `co-extract.md`,
  `co-capabilities.md`, `co-validate.md` (rebuild the constraint catalog / derive the
  capability layer + stack scaffold / validate a PRP plan), `nw-ship-pr.md`
  (the PR lifecycle; a workflow surface, not an install), and `nw-doctor.md`
  (the read-only harness health report — see `scripts/` below).
- `scripts/` — plugin-side diagnostics that install **nothing**: stdlib-only, run under
  system `python3` (no `uv`, no venv), never imported by payload code.
  `harness_probe.py` holds the engine registry and install discovery; `doctor.py` is the
  read-only health report behind `/nw-doctor`. They live here and not in an engine
  because only the plugin has `CLAUDE_PLUGIN_ROOT` and the shipped `VERSION`s to compare
  against — and because half the states the doctor reports (`uv` missing, no `.venv`,
  `uv sync` never run) would stop a `uv run` entry point from starting at all.
- `workflows/` — `nw-ship-pr-review.js`, the review fan-out `/nw-ship-pr` triggers. The
  runtime auto-discovers `workflows/*.js` and namespaces them by plugin name, so it
  resolves as `neurawork-cc-harness:nw-ship-pr-review`; the manifest needs no entry.
- `agents/` — exported agents, namespaced by plugin name. `kb-researcher.md` resolves as
  `neurawork-cc-harness:kb-researcher`: a read-only (`Read, Grep, Glob`) knowledge-base
  researcher, spawned by the `knowledge-compiler` payload's two injecting hooks.
- `tests/` — structural tests over the prompt-only assets (frontmatter agreement, the
  workflow name resolution, and the worktree guard invariants). Run from the plugin root:
  `python3 -m unittest discover -s tests`.
- `engines/<engine>/` — one per skill, plus shared code:
  - `install.py` — copies `payload/` + `_shared/` into the target repo, scaffolds
    data dirs, merges hooks into `.claude/settings.json`.
  - `recon.py` — read-only detection; emits a `RECON_JSON` blob the skill parses.
  - `config.default.json`, `VERSION`.
  - `payload/` — the code copied into the target repo (`hooks/`, `scripts/`,
    `pyproject.toml`, `AGENTS.md`).
  - `tests/` — install/recon + trigger tests against a real git temp repo.
- `engines/_shared/` — stdlib-only helpers reused by all engines and refreshed on
  every install (single source of truth): `hookio.py` (hook stdin + recursion
  guard), `transcript.py` (JSONL → markdown turns), `gitctx.py` (worktree redirect),
  `settings.py` (idempotent hook merge), `repo_guard.py` (in-repo / not-`.claude/`),
  `recon.py` (git-root + `RECON_JSON`).

## Conventions & gotchas

- **Engine vs payload:** `engines/<engine>/` is install-time tooling that runs from
  the plugin; `payload/` is what runs *inside the target repo* after install. Keep
  the distinction — payload code resolves `config`/`utils` via `sys.path` at
  `uv run` time, not as importable packages.
- **`_shared/` is the single source of truth.** Edit it here; `install.py` copies it
  into every target. Don't fork per-engine copies.
- **A workflow skill has no engine — that is intended, not an omission.** `nw-worktree`
  and `nw-ship-pr` copy nothing into a target repo, so they have no `install.py`, no
  `recon.py`, no `payload/`, no `VERSION`, and no entry in `scripts/harness_probe.py`'s
  `ENGINES` registry (a component that installs nothing has no install to discover or
  version). Don't "fix" the missing engine. Their only per-repo state
  is a lazily written `.claude/*.local.md` config, shared by path and key with a
  `coding-suite` install so the two never keep two drifting profiles.
- **Install modes:** `install.py` detects **ADOPT** (existing install — refresh code,
  never clobber data) vs **FRESH**. Hook merges are idempotent and use distinct
  filenames + events per skill (`cl-`-prefixed for the learner; `co-`-prefixed on the
  `PostToolUse` event for compliance) so all three skills coexist in one repo.
- **A hook may claim a matcher group.** `_shared/settings.py` accepts a 5th tuple element,
  the matcher; a 4-tuple still lands in the `matcher: ""` group, which is correct for the
  events that carry no tool name (`SessionStart`, `PreCompact`, `SessionEnd`,
  `UserPromptSubmit`). `knowledge-compiler`'s `hooks/pre-skill.py` uses `matcher: "Skill"`
  and `compliance-compiler`'s `hooks/co-post-tooluse.py` uses
  `matcher: "Write|Edit|MultiEdit"`: without one, the hook spawns a process on *every*
  tool call. Re-running an installer **moves** an entry found under a different matcher
  into the requested group, so a narrowing reaches installs that already exist.
- **Test discovery quirk:** `engines/` is a namespace package and the engine dirs
  are hyphenated, so a single `unittest discover -s engines` under-collects (finds
  only `_shared`). Run discovery per test directory — see the root `CLAUDE.md`.
- **Outputs never under `.claude/`** — enforced by `_shared/repo_guard.py`
  (`assert_in_repo_not_dotclaude`).
- **Auth:** SDK calls need `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`;
  subscription credentials are not sanctioned for third-party plugin use.

## Local development

Load the plugin from this checkout without a marketplace by symlinking it into a
repo's skills dir — see
[`../docs/INSTALL.md`](../docs/INSTALL.md#local-development-working-on-the-plugin).
Run `/reload-plugins` after editing non-`SKILL.md` components.
