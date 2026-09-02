# CLAUDE.md — claudemd-lerner/

This directory is a **live self-host install** of the `claudemd-lerner` skill into
this repo (the engine source is `plugins/neurawork-cc-harness/engines/claudemd-lerner/`).
It holds **only machinery** — its outputs live at the repo root.

## What lives here vs. what it produces

- Here (machinery, copied from the engine `payload/` + `_shared/`): `hooks/`
  (`cl-`-prefixed), `scripts/` (`update.py`, `seed.py`, `flush.py`, `config.py`,
  `utils.py`), `_shared/`, `pyproject.toml`, `AGENTS.md`, `config.json`, `daily/`.
- Produced **at the repo root** (not in this dir): the `CLAUDE.md` hierarchy and the
  `docs/` tree — the files the agent already reads. There is **no** knowledge wiki
  (that is the separate `knowledge-compiler` skill).
- `AGENTS.md` is the learner's constitution — the spec the LLM follows when turning
  `daily/` logs (and the live repo) into surgical edits to `CLAUDE.md` + `docs/`.

## Config (`config.json`)

`claudemd_depth: 2` (root + immediate-subdir `CLAUDE.md` only — never deeper),
`docs_dir: docs`, `language: en`, `excluded_dirs` (`node_modules`, `.venv`, `dist`,
`build`, `.git`), `update_age_hours: 6`. The updater reads these to scope where it
writes — keep them in sync with how this repo is actually laid out.

## Conventions & gotchas

- **Do not hand-edit the machinery** (`hooks/`, `scripts/`, `_shared/`, `AGENTS.md`,
  `pyproject.toml`). It is copied from the plugin payload and is overwritten on
  re-install (ADOPT). Fix the source under `plugins/…/engines/claudemd-lerner/payload/`.
  The engine lives in **two byte-identical copies** — the payload
  (`plugins/…/engines/claudemd-lerner/payload/hooks/`) and this self-host
  (`claudemd-lerner/hooks/`) — that must stay in sync; version bumps (`VERSION`,
  `pyproject.toml`) apply to both. After editing a hook, confirm
  `diff -rq claudemd-lerner/hooks/ plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/hooks/`
  is empty as a sync check.
- The `SessionStart` hook (`cl-session-start.py`) **injects no context** — it only
  fires the gated background `update.py`. `CLAUDE.md` + `docs/` are already read at
  session start, so re-injecting them would only crowd the context; that
  `SessionStart` budget is left for `knowledge-compiler`'s concepts inject.
- The updater **edits docs in place, surgically** — it does not rewrite from scratch,
  never invents, and refuses to write outside the repo or under `.claude/`
  (`_shared/repo_guard.py`).
- Run: `uv sync --directory claudemd-lerner` then
  `uv run --directory claudemd-lerner python scripts/update.py` (`--all` re-applies
  every log, `--dry-run` previews without calling the model).
- Hooks are `cl-`-prefixed so they coexist with `knowledge-compiler`'s hooks in
  `.claude/settings.json`.

See [`../docs/INSTALL.md`](../docs/INSTALL.md) for the full install/upgrade flow.
