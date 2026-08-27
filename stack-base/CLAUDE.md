# CLAUDE.md — stack-base/

This directory is a **live self-host install** of the `stack-compiler` skill into
this repo (the engine source is
`plugins/neurawork-cc-harness/engines/stack-compiler/`). It scopes the compliance
capability catalog down to **this one product** and gates PRD/plan writes against the
component stack that scoping settles on.

It is **installed by hand.** The engine has no `install.py` / `recon.py` / slash
commands yet (they land in a later phase), so `plugins/…/engines/stack-compiler/payload/`
and this dir are kept **byte-identical** by `tests/test_payload_drift.py`, not by an
installer.

## What lives here vs. what it produces

- Here (machinery, copied from the engine `payload/` + `_shared/`): `hooks/`
  (`st-post-tooluse.py`), `scripts/` (`scope.py`+`scope_lib.py`, `rank.py`+`rank_lib.py`,
  `selection.py`+`selection_lib.py`, `validate.py`, `gate_lib.py`, `config.py`),
  `_shared/`, `pyproject.toml`, `AGENTS.md`, `config.json`, `VERSION`.
- `product.md` — the **tracked scoping input of record**. The scoping agents read
  **only this file**, so everything they need to know about the product is written here.
- **It owns no data artifact.** The three passes write into
  `compliance-base/catalog/stack.json` through `compliance-base/scripts/stack.py` — the
  single schema owner. `.shards/`, `reports/`, and `scripts/state.json` are gitignored.
- `AGENTS.md` is the engine's constitution — the spec every scoping, challenge, ranking
  and gate agent follows (`scope.py` and `rank.py` read it verbatim into each prompt).
  Read it before reasoning about behaviour.

## The three passes (all write through `compliance-base/scripts/stack.py`)

- **`scope.py`** — decides, per capability, *whether* it applies to this product and
  *why* (`--apply` → `stack.py --apply-scope`). Runs parallel SDK agents plus a
  challenge pass that re-reads each "not applicable" reason against `product.md`.
  All-or-nothing: every catalog key gets an explicit decision.
- **`rank.py`** — orders each still-applicable capability's catalog components
  best-fit-first, with a reason per position (`--apply` → `stack.py --apply-ranking`).
  Runs parallel SDK agents. The component pool is closed — a ranking names exactly that
  capability's `options`, once each.
- **`selection.py`** — renders the ranking as an editable **selection sheet**, reads
  back the component a human wrote per capability, and records it (`--apply <sheet>` →
  `stack.py --apply-selection`, which also stamps `chosen_from`). It runs **no agent**
  and needs **no API key** — the proposal already exists. Selection is deliberately
  **partial**: an undecided capability stays a counted gap, not a silent omission.
  It is named `selection.py`, not `select.py`, because a module named `select` in
  `scripts/` shadows the stdlib `select` and breaks the other passes at import time.

## The runtime gate (`st-post-tooluse.py` → `validate.py`)

A `PostToolUse` hook, `st-`-prefixed, sits in the `matcher: ""` group beside
`compliance-base`'s `co-post-tooluse.py`. On each PRD/plan write it runs a fast inline
structural precheck plus a detached deep LLM check (`validate.py`) that reads the
document for *intent* — whether it **proposes** a component or merely mentions one — and
writes `reports/<stem>.md` + a verdict `reports/<stem>.stack.json`. The gate **reads**
`stack.json`; it never writes it (`chosen` is recorded only by `selection.py`).
`config.json`'s `validate_mode` sets `warn` | `block` per document type (`prd`, `plan`).

## Config (`config.json`)

`stack_dir: stack-base`, `compliance_dir: compliance-base`, `model`, `max_concurrency:
12`, `product_file: product.md`, `prds_subpath: .claude/PRPs/prds`, `plans_subpath:
.claude/PRPs/plans`, `validate_mode: {prd: warn, plan: warn}`.

## Running it

```bash
uv sync --directory stack-base                                    # resolve deps
uv run --directory stack-base python scripts/scope.py             # decide applicability (--apply to record)
uv run --directory stack-base python scripts/rank.py              # order each one's components (--apply)
uv run --directory stack-base python scripts/selection.py         # render the selection sheet
uv run --directory stack-base python scripts/selection.py --apply <sheet>   # record the human choices
uv run --directory stack-base python scripts/validate.py <document>         # deep-check a PRD/plan vs the stack
```

`scope.py` and `rank.py` run parallel SDK agents and need `ANTHROPIC_API_KEY` or
`CLAUDE_CODE_OAUTH_TOKEN`; `selection.py` and the inline precheck are pure stdlib and
need neither. Both `scope.py` and `rank.py` take `--dry-run` and `--product <file>`.

## Conventions & gotchas

- **Do not hand-edit the machinery** (`hooks/`, `scripts/`, `_shared/`, `AGENTS.md`,
  `pyproject.toml`). Fix the source under
  `plugins/…/engines/stack-compiler/payload/`. Because there is no installer yet, the
  copy here is kept in sync **by drift test**, not by re-install —
  `plugins/…/engines/stack-compiler/tests/test_payload_drift.py` fails on any divergence.
- **No agent ever picks a component.** Ranking proposes an order and stops; `chosen`
  and its `rationale` are written only by the (agent-free) selection pass through the
  schema owner.
- **The gate changes nothing** — it reads a document and reports what the recorded
  stack says about it; it never edits `stack.json` or `capabilities.json`.
- Nothing is written under `.claude/` — enforced at runtime by `_shared/repo_guard.py`.

See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for how the engine fits the
harness and [`../docs/INSTALL.md`](../docs/INSTALL.md) for the install/upgrade flow.
