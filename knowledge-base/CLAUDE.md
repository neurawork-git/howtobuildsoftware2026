# CLAUDE.md — knowledge-base/

This directory is a **live self-host install** of the `knowledge-compiler` skill
into this repo (the engine source is `plugins/neurawork-cc-harness/engines/knowledge-compiler/`).
It holds both the engine machinery and the tracked knowledge wiki it produces.

## What lives here

- `hooks/`, `scripts/`, `_shared/`, `pyproject.toml`, `AGENTS.md` — **machinery**,
  copied from the engine `payload/` + `_shared/` at install time.
- `config.json` — runtime config (`knowledge_dir`, `model`, `compile_age_hours: 6`,
  plus the `research_*` keys below).
- `knowledge/` — **the tracked output**: `index.md` (read first), `concepts/`,
  `connections/`. `knowledge/log.md`, `daily/`, and `reports/` are git-ignored.
- `AGENTS.md` is the compiler's constitution — the spec the LLM follows when turning
  `daily/` logs into articles (concepts, connections, index). Read it before
  reasoning about compile/query behaviour.

## The kb-researcher spawn directive

Two of the five installed hooks do not capture anything — they inject a directive that
tells the session to spawn `neurawork-cc-harness:kb-researcher` (the plugin's read-only
knowledge-base agent) alongside `prp-core`'s three research agents whenever a PRP
research workflow starts:

- `hooks/user-prompt-submit.py` — a **typed** `/prp-prd`, `/prp-plan` or `/prp-debug`.
- `hooks/pre-skill.py` — a **model-invoked** `Skill` call for the same, registered under
  a `matcher: "Skill"` group in `.claude/settings.json` so it does not fire on every
  tool call.

Both render the same text from `scripts/research_directive.py`. **`PreToolUse` must
never exit non-zero — exit code 2 on that event blocks the tool call** — so both hooks
fail open: any exception yields no output and exit 0.

Disable without re-installing: set `"research_directive": false` in `config.json` (read
live on every hook run). To remove them entirely, delete the two entries from
`.claude/settings.json`. The patterns are `research_skill_match` /
`research_prompt_match` in the same file, so an upstream rename of a `prp-core` skill
is a one-line config edit.

## Conventions & gotchas

- **Do not hand-edit the machinery** (`hooks/`, `scripts/`, `_shared/`, `AGENTS.md`,
  `pyproject.toml`). It is copied from the plugin payload and is overwritten on
  re-install (ADOPT). Fix the source under `plugins/…/engines/knowledge-compiler/payload/`
  and re-run the installer to refresh.
- `knowledge/` is **never organised by hand** — the compiler synthesizes it from
  `daily/` logs. Edit logs, not articles.
- Resolve deps with `uv sync --directory knowledge-base`; compile with
  `uv run --directory knowledge-base python scripts/compile.py` (`--all` recompiles,
  `--file <daily>` for one log, `--dry-run` to preview). Query with
  `uv run --directory knowledge-base python scripts/query.py "..."`.
- Nothing is written under `.claude/`; the wiki stays in-repo and tracked.

See [`../docs/INSTALL.md`](../docs/INSTALL.md) for the full install/upgrade flow.
