# Architecture — neurawork-cc-harness

How the harness is put together: the plugin source, the two engines, the shared
infrastructure, the install flow, and how this repo self-hosts both skills. For
*using* it see [INSTALL.md](INSTALL.md); for choosing it over `coding-suite` see
[WHEN-TO-USE.md](WHEN-TO-USE.md).

## The two skills

| Skill | Captures | Produces | Constitution |
|-------|----------|----------|--------------|
| `knowledge-compiler` | session transcripts → `<dir>/daily/` logs | `<dir>/knowledge/` wiki (`index.md`, `concepts/`, `connections/`) | `knowledge-base/AGENTS.md` |
| `claudemd-lerner` | session transcripts → `<dir>/daily/` logs | repo-root `CLAUDE.md` hierarchy + `docs/` (edited in place) | `claudemd-lerner/AGENTS.md` |

Both follow the same **LLM-as-compiler** model: sessions emit append-only `daily/`
logs (the "source code"); an LLM (the "compiler" / "learner") reads the logs plus
the live repo and synthesizes the executable output. The output is never organised
by hand. The concept derives from Andrej Karpathy's LLM wiki and coleam00's
`claude-memory-compiler`; the implementation is independent NeuraWork work.

## Plugin source layout (`plugins/neurawork-cc-harness/`)

```
.claude-plugin/plugin.json     plugin manifest
skills/<skill>/SKILL.md        install skills (recon → ask → execute)
commands/                      kc-compile.md, cl-update.md (manual triggers)
engines/
  _shared/                     stdlib-only helpers (single source of truth)
  knowledge-compiler/
    install.py  recon.py  config.default.json  VERSION
    payload/                   code copied into the target repo
    tests/
  claudemd-lerner/             (same shape)
```

The repo-root `.claude-plugin/marketplace.json` (marketplace `neurawork-harness`)
distributes `plugins/neurawork-cc-harness` via a `git-subdir` source; with no pinned
`version`, installs track the latest commit on the default branch.

### engine vs. payload

`engines/<engine>/` is **install-time tooling** run from the plugin.
`engines/<engine>/payload/` is **what runs inside the target repo** after install:
hooks, scripts, `pyproject.toml`, and the engine's `AGENTS.md`. Payload scripts
resolve their `config`/`utils` modules via `sys.path` at `uv run` time (not as
importable packages), so static type checkers flag those imports as unresolved —
expected and harmless.

### `_shared/` helpers

Stdlib-only, reused by both engines and **refreshed on every install** so there is
one source of truth:

| Module | Purpose |
|--------|---------|
| `hookio.py` | Parse hook stdin (Windows-safe) + recursion guard |
| `transcript.py` | Read a JSONL transcript → recent markdown turns |
| `gitctx.py` | Worktree detection + state redirect to the main checkout |
| `settings.py` | Idempotent `.claude/settings.json` hook merge |
| `repo_guard.py` | Enforce: outputs in-repo, never under `.claude/` |
| `recon.py` | Git-root resolution + `RECON_JSON` emit for install recon |

## Install flow

Each skill's `SKILL.md` runs three phases:

1. **Recon (read-only)** — `recon.py` prints a `RECON_JSON` blob: git root, whether
   a prior install exists (ADOPT vs FRESH), seed recommendation, timezone, and (for
   the learner) suggested CLAUDE.md depth / language / docs presence.
2. **Ask** — `AskUserQuestion` confirms the install dir, and for the learner the
   depth, docs dir, language, excluded dirs, timezone, and whether to seed.
3. **Execute** — `install.py` copies `payload/` + `_shared/` into `<repo>/<dir>/`,
   scaffolds data dirs (only if absent — never clobbers), writes `.gitignore`, and
   **idempotently merges** the hooks into `.claude/settings.json`.

`install.py` is **ADOPT-aware**: when it detects an existing install it refreshes
code (`payload/` + `_shared/`) without touching captured data (`daily/`, the wiki,
or the docs). Then `uv sync --directory <dir>` resolves engine deps; the user
commits `<dir>/` and `.claude/settings.json`.

## Runtime: capture and synthesis

Three hooks drive capture, merged into `.claude/settings.json`:

- **`SessionEnd`** / **`PreCompact`** — write the session into a `daily/` log.
- **`SessionStart`** — inject the current output (the wiki index, or the root
  `CLAUDE.md` + `docs/` listing) as additional context, and, if the last run is
  older than the 6-hour gate *and* there is new `daily/` content *and* no fresh
  lock, fire a detached compile/update (skipped inside a worktree).

Synthesis can also be triggered manually: `/neurawork-cc-harness:kc-compile` and
`/neurawork-cc-harness:cl-update`, or directly via
`uv run --directory <dir> python scripts/{compile,update}.py`. Runs are incremental
by SHA-256 of each daily log and stamp a `last-{compile,update}.json` so the gate
knows when they last ran. Synthesis needs `ANTHROPIC_API_KEY` /
`CLAUDE_CODE_OAUTH_TOKEN`; capture and scaffolding do not.

## Self-hosting in this repo

This repo installs **both** skills into itself:

- `knowledge-base/` — `knowledge-compiler` machinery + the tracked `knowledge/` wiki.
- `claudemd-lerner/` — `claudemd-lerner` machinery; its outputs are this repo's
  root `CLAUDE.md` hierarchy and `docs/` (including this file).

Both hook sets live side by side in `.claude/settings.json` (the learner's are
`cl-`-prefixed), so the two coexist without clobbering each other. The machinery in
those two dirs is a copy of the plugin payload — fix bugs in
`plugins/…/engines/<engine>/payload/` and re-run the installer to refresh, rather
than hand-editing the installed copy.
