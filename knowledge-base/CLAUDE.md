# CLAUDE.md — knowledge-base/

This directory is a **live self-host install** of the `knowledge-compiler` skill
into this repo (the engine source is `plugins/neurawork-cc-harness/engines/knowledge-compiler/`).
It holds both the engine machinery and the tracked knowledge wiki it produces.

## What lives here

- `hooks/`, `scripts/`, `_shared/`, `pyproject.toml`, `AGENTS.md` — **machinery**,
  copied from the engine `payload/` + `_shared/` at install time.
- `config.json` — runtime config (`knowledge_dir`, `model`, `compile_age_hours: 6`).
- `knowledge/` — **the tracked output**: `index.md` (read first), `concepts/`,
  `connections/`. `knowledge/log.md`, `daily/`, and `reports/` are git-ignored.
- `AGENTS.md` is the compiler's constitution — the spec the LLM follows when turning
  `daily/` logs into articles (concepts, connections, index). Read it before
  reasoning about compile/query behaviour.

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
