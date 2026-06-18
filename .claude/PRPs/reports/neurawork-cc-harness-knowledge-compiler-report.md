# Implementation Report

**Plan**: `.claude/PRPs/plans/completed/neurawork-cc-harness-knowledge-compiler.plan.md`
**Source PRD**: `.claude/PRPs/prds/neurawork-cc-harness.prd.md` (Phase 2)
**Branch**: `feature/knowledge-compiler`
**Date**: 2026-06-18
**Status**: COMPLETE

---

## Summary

Added the `knowledge-compiler` skill to the `neurawork-cc-harness` plugin: a
per-repo, self-building knowledge base. Sessions are captured (SessionEnd /
PreCompact) into `<kdir>/daily/` logs and compiled by the `claude-agent-sdk` into
`<kdir>/knowledge/{concepts,connections,index.md}`; SessionStart injects the index
and, on a 6-hour age gate, spawns a detached compile. Install copies the payload +
Phase-1 `engines/_shared/` into the repo, scaffolds the trees, merges the three
hooks, and can brownfield-seed an existing repo. All knowledge lives in the repo,
never under `.claude/`.

Implementation was a PORT of `coleam00/claude-memory-compiler`
(commit `54eddd709e83d3be244e9c56c9fc3a6cf375d534`) restructured to our layout, with
our deltas applied: `_shared` wiring, the 6h SessionStart trigger replacing cole's
18:00 clock, a new `seed.py`, and 2026 SDK conventions (`total_cost_usd`,
`setting_sources=[]`, `strict_mcp_config=True`, `model` configurable, dep `>=0.2.96`).
Code is written fresh — only Phase-1 `_shared` is reused verbatim.

---

## Assessment vs Reality

| Metric | Predicted | Actual | Reasoning |
| ------ | --------- | ------ | --------- |
| Complexity | HIGH | HIGH | LLM pipeline + hooks + trigger + seed, all fresh, as scoped |
| Confidence | 8/10 | 8/10 | Non-LLM parts unit-tested + smoke-validated; the LLM pipeline still needs live-auth smoke (gated on `ANTHROPIC_API_KEY`) |

Deviations: see below.

---

## Tasks Completed

| # | Task | File | Status |
|---|------|------|--------|
| 0 | Fetch cole reference | `/tmp/claude-memory-compiler-ref` (SHA `54eddd7`) | ✅ |
| 1 | VERSION | `engines/knowledge-compiler/VERSION` | ✅ |
| 2 | config.default.json | `engines/knowledge-compiler/config.default.json` | ✅ |
| 3 | pyproject.toml | `engines/knowledge-compiler/payload/pyproject.toml` | ✅ |
| 4 | AGENTS.md constitution | `…/payload/AGENTS.md` | ✅ |
| 5 | utils.py (+ `should_compile`) | `…/payload/scripts/utils.py` | ✅ |
| 6 | config.py | `…/payload/scripts/config.py` | ✅ |
| 7 | flush.py | `…/payload/scripts/flush.py` | ✅ |
| 8 | compile.py | `…/payload/scripts/compile.py` | ✅ |
| 9 | query.py | `…/payload/scripts/query.py` | ✅ |
| 10 | lint.py (7 checks) | `…/payload/scripts/lint.py` | ✅ |
| 11 | seed_prompt.txt | `…/payload/scripts/seed_prompt.txt` | ✅ |
| 12 | seed.py | `…/payload/scripts/seed.py` | ✅ |
| 13 | session-end.py | `…/payload/hooks/session-end.py` | ✅ |
| 14 | pre-compact.py | `…/payload/hooks/pre-compact.py` | ✅ |
| 15 | session-start.py (6h gate) | `…/payload/hooks/session-start.py` | ✅ |
| 16 | recon.py | `engines/knowledge-compiler/recon.py` | ✅ |
| 17 | install.py | `engines/knowledge-compiler/install.py` | ✅ |
| 18 | SKILL.md | `skills/knowledge-compiler/SKILL.md` | ✅ |
| 19 | kc-compile command | `commands/kc-compile.md` | ✅ |
| 20 | unit tests | `engines/knowledge-compiler/tests/*` | ✅ |
| 21 | validate + smoke | plugin-validator PASS; non-LLM smoke ✅ | ✅ |

---

## Validation Results

| Check | Result | Details |
| ----- | ------ | ------- |
| py_compile (all .py) | ✅ | engine + payload scripts + hooks + tests |
| JSON / TOML parse | ✅ | config.default.json, pyproject.toml |
| Leak grep (`homeserver-knowledge`/`America/Chicago`) | ✅ | clean |
| Unit tests (KC) | ✅ | 15 passed |
| Unit tests (Phase-1 `_shared`) | ✅ | 18 passed (no regression) |
| Integration smoke (non-LLM) | ✅ | install scaffolds; hooks import `_shared` and run; session-start emits JSON; compile `--dry-run` works |
| plugin-validator | ✅ | PASS (focus: plugin.json, SKILL.md, command) |
| Manual SDK smoke (compile/seed/flush) | ⏭️ | Gated on `ANTHROPIC_API_KEY`; documented below |

---

## Deviations from Plan

1. **Level 3 broad discovery quirk.** `python3 -m unittest discover -s engines`
   only collects the `_shared` suite (18). The `knowledge-compiler` directory name
   contains a hyphen, so unittest cannot import it as a package and silently skips
   `knowledge-compiler/tests/`. Both suites pass when run with their explicit
   `-s <path>` (15 + 18 = 33 green, Level 2). No test fails; this is a discovery
   limitation of the hyphenated dir, not a defect.
2. **`install.py --seed` runs `uv sync` first.** The plan's Phase-C order
   (install `--seed` then `uv sync`) would call `seed.py` before deps exist. To make
   `--seed` self-contained, install runs `uv sync --directory <kdir>` immediately
   before `seed.py`. The skill's subsequent `uv sync` stays (idempotent).
3. **`should_compile` lives in `utils.py`.** Kept with the other pure helpers (no
   SDK import) so both the SessionStart hook and the unit test import it cheaply.

---

## Issues Encountered

- **Self-pollution during smoke.** The first smoke run invoked `install.py` from the
  plugin dir, so `git_root_or_none()` resolved to the main repo and scaffolded a
  stray `kb/` + `.claude/settings.json` at the repo root. Both were removed; the
  emitted settings.json confirmed the hook-merge output is correct. The corrected
  smoke runs `install.py` with `cwd` = a temp git repo.

---

## Tests Written

| Test File | Test Cases |
| --------- | ---------- |
| `tests/test_install_recon.py` | FRESH scaffold + 3 hooks merged; idempotent ADOPT re-install (keeps a user article, no duplicate hook); recon emits parseable RECON_JSON with `seed_recommended`; recon `NOT_A_GIT_REPO` |
| `tests/test_utils_trigger.py` | slugify / file_hash / extract_wikilinks / build_index_entry; `should_compile` truth table (fresh→no, stale+new→yes, no-daily→no, worktree→no, lock-fresh→no, missing-stamp variants) |

---

## Manual SDK Smoke (run when `ANTHROPIC_API_KEY` is set)

1. `python3 engines/knowledge-compiler/install.py --knowledge-dir kb` in a throwaway git repo.
2. `uv sync --directory kb`; write `kb/daily/<today>.md`; `uv run --directory kb python scripts/compile.py --all`
   → expect `kb/knowledge/concepts/*.md`, updated `index.md`, and `kb/scripts/last-compile.json`.
3. `uv run --directory kb python scripts/seed.py` on a small repo → initial concepts.
4. New session → SessionStart injects the index; after 6h + new daily content → compile auto-spawns.

---

## Next Steps

- [ ] Review the diff.
- [ ] Run the live-auth SDK smoke once an API key is available.
- [ ] Create PR for the branch.
- [ ] Phase 3 (`claudemd-lerner`) is unblocked and can run in parallel; Phase 4 waits on 2 + 3.
