# CLAUDE.md — compliance-base/

This directory is a **live self-host install** of the `compliance-compiler` skill into
this repo (the engine source is
`plugins/neurawork-cc-harness/engines/compliance-compiler/`). It holds both the engine
machinery and the tracked compliance catalog it produces.

## The four layers

```
standards (GDPR / SOC 2 / ISO 27001)
  → extract.py       → catalog/{gdpr,soc2,iso27001}.json   359 constraints, 279 mandatory
  → capabilities.py  → catalog/capabilities.{json,md}      68 capabilities + component options
  → stack.py         → catalog/stack.json                  the component actually chosen
  → validate.py      → reports/<plan-stem>.md              a PRP plan checked against all of it
```

A **constraint** is a requirement to prove ("maintain an asset inventory with a named
owner"). A **capability** is a thing to build ("immutable audit logging") that satisfies
many constraints at once — the lists are deliberately **per-framework with overlap
kept**, because SOC 2 / ISO 27001 / GDPR are audited separately. Capability keys are
`<framework>/<slug>`, e.g. `gdpr/immutable-audit-logging`.

## What lives here

- `hooks/`, `scripts/`, `_shared/`, `pyproject.toml`, `AGENTS.md` — **machinery**,
  copied from the engine `payload/` + `_shared/` at install time.
- `config.json` — runtime config: `frameworks` (what gets extracted),
  `validate_frameworks` (which of them plans are checked against; empty = all),
  `validate_mode` (`warn` | `block`), `max_concurrency`, `model`.
- `catalog/` — **the tracked output**: the three constraint JSONs, `index.md` (read
  first), the derived `capabilities.{json,md}`, and `stack.json`.
- Git-ignored: `catalog/.shards/` (per-agent shard files), `reports/`,
  `scripts/state.json`, `scripts/last-extract.json`.
- `AGENTS.md` is the engine's constitution — the spec the LLM follows when distilling
  standards into constraints. Read it before reasoning about extraction behaviour.

## Running it

```bash
uv sync --directory compliance-base                                   # resolve deps
uv run --directory compliance-base python scripts/extract.py          # ~30 agents → constraints
uv run --directory compliance-base python scripts/capabilities.py     # constraints → capabilities
uv run --directory compliance-base python scripts/stack.py --scaffold # refresh stack.json + gaps
uv run --directory compliance-base python scripts/stack.py            # gap + staleness report
uv run --directory compliance-base python scripts/validate.py <plan>  # deep check of one plan
```

Both `extract.py` and `capabilities.py` take `--frameworks <a,b>` and `--dry-run`.
`extract.py` always re-extracts what it is asked for; `capabilities.py` additionally
**skips** a framework whose constraint catalog is unchanged since the last run (content
hash in `scripts/state.json`) unless given `--all`. Both need `ANTHROPIC_API_KEY` or
`CLAUDE_CODE_OAUTH_TOKEN`. `stack.py` and the inline precheck are pure stdlib and need
neither. Slash-command equivalents: `/neurawork-cc-harness:co-extract`,
`/neurawork-cc-harness:co-capabilities`, `/neurawork-cc-harness:co-validate <plan>`.

## Conventions & gotchas

- **Do not hand-edit the machinery** (`hooks/`, `scripts/`, `_shared/`, `AGENTS.md`,
  `pyproject.toml`). It is copied from the plugin payload and overwritten on re-install
  (ADOPT). Fix the source under
  `plugins/…/engines/compliance-compiler/payload/` and re-run the installer.
  This repo's catalog is the source of truth for the *shipped seed*: after changing it,
  run `python3 plugins/…/engines/compliance-compiler/sync_catalog_seed.py`
  (`--check` reports drift; `tests/test_catalog_seed.py` enforces it).
- **One hook, `PostToolUse`, `co-`-prefixed** — deliberately nothing at `SessionStart`
  (that budget belongs to the knowledge engines). A fresh install gets a working catalog
  from the shipped seed, not from a bootstrap run, and `install.py` actively prunes any
  leftover `co-session-start.py`. Do not add one.
- **`stack.json` ownership is split.** Its schema, `--scaffold` and the gap report live
  here; the three passes that fill it live in `stack-base/` and write through this
  script's three apply modes — `scripts/scope.py → --apply-scope` (does a capability
  apply to this product, and why), `scripts/rank.py → --apply-ranking` (the
  best-fit-first order of its `options`), `scripts/selection.py → --apply-selection`
  (the component a human chose). A re-scaffold carries all eight decision-owned fields
  — `chosen`, `rationale`, `chosen_from`, `applicable`, `applicability_reason`,
  `scoped_from`, `ranked`, `ranked_from` — over by key; never re-derive them here.
  `--apply-selection` also stamps `chosen_from`, the hash of the catalog capability the
  choice was made against, so `gaps()` can name the choices a catalog change
  invalidated instead of invalidating the whole file. Scope and ranking demand the
  complete key set; selection is deliberately partial — an undecided capability stays a
  counted gap.
- **The gap report is report-only and exits 0.** An unfilled stack is the normal
  starting state, not a regression. Enforcement is the plan validator's job.
- **A `replaced` verdict is not a rejection.** In a catalog capability's `stack[]`,
  `verdict: "replaced"` means the component *superseded* the one named in
  `replaced_from` during the license audit — it stays a live option. Every entry is a
  live recommendation regardless of verdict, so `stack.py`'s `component_options()`
  never filters on verdict (doing so would drop a large share of the catalog's
  components).
- **Copyright**: the catalog stores official control/article identifiers, short titles,
  and *paraphrased* requirements — never verbatim text of the copyrighted standards.
- Nothing is written under `.claude/` — enforced at runtime by `_shared/repo_guard.py`.

See [`../docs/INSTALL.md`](../docs/INSTALL.md) for the full install/upgrade flow and
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for how the engine fits the harness.
