# CLAUDE.md — plugins/

The distributed Claude Code plugin lives here at
`plugins/neurawork-cc-harness/`. This is the **source** that the repo-root
marketplace (`.claude-plugin/marketplace.json`, name `neurawork-harness`) ships
via a `git-subdir` source — it is what users install, not this whole repo.

## Layout

- `.claude-plugin/plugin.json` — plugin manifest (`name`, description, author, MIT).
- `skills/<skill>/SKILL.md` — the three install skills (`knowledge-compiler`,
  `claudemd-lerner`, `compliance-compiler`). Each runs a three-phase flow: **Recon**
  (read-only) → **Ask** (AskUserQuestion) → **Execute** (run `install.py`).
- `commands/` — slash commands `kc-compile.md`, `cl-update.md` (manual compile /
  update; bypass the SessionStart 6-hour gate) and `co-extract.md`,
  `co-capabilities.md`, `co-validate.md` (rebuild the constraint catalog / derive the
  capability layer + stack scaffold / validate a PRP plan).
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
- **Install modes:** `install.py` detects **ADOPT** (existing install — refresh code,
  never clobber data) vs **FRESH**. Hook merges are idempotent and use distinct
  filenames + events per skill (`cl-`-prefixed for the learner; `co-`-prefixed on the
  `PostToolUse` event for compliance) so all three skills coexist in one repo.
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
