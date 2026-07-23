# Implementation Report

**Plan**: `.claude/PRPs/plans/compliance-capabilities-engine.plan.md`
**Source PRD**: `.claude/PRPs/prds/compliance-capabilities.prd.md` (Phase 1)
**Branch**: `feature/compliance-capabilities-engine`
**Date**: 2026-07-23
**Status**: COMPLETE (Task 8 = manual, needs API key — deferred)

---

## Summary

Added a repeatable capability-derivation engine to `compliance-compiler`: `capabilities.py` (SDK fan-out) + `cap_lib.py` (pure logic). It reads `catalog/<fw>.json`, clusters each framework's constraints into capabilities (one agent/framework), maps each unique capability to greenfield-2026 stack components (one agent/capability), then applies a **deterministic** mandatory-coverage gate and writes `capabilities.json` + `capabilities.md` + refreshes `index.md`. Content-hash idempotency skips unchanged frameworks. Shipped in both the `payload/` source tree and the live `compliance-base/` self-host, byte-identical.

---

## Assessment vs Reality

| Metric | Predicted | Actual | Reasoning |
| ------ | --------- | ------ | --------- |
| Complexity | MEDIUM | MEDIUM | Matched — all patterns existed in-repo; only new code was `cap_lib` pure logic + two prompt builders |
| Confidence | 9/10 | 9/10 | Held — no surprises; fan-out/gate/atomic-write reproduced verbatim from `extract.py`/`precheck.py` |

**Deviations**: `_fan_out` is a generic thunk-runner (used by both cluster and stack stages) rather than two copies of `extract_all` — same semaphore + `asyncio.gather(return_exceptions=True)` semantics, less duplication. Documented below.

---

## Tasks Completed

| # | Task | File | Status |
| - | ---- | ---- | ------ |
| 1 | Add `file_hash` | `scripts/utils.py` (both trees) | ✅ |
| 2 | Pure logic: slug/assemble/coverage/renderers | `scripts/cap_lib.py` (both trees) | ✅ |
| 3 | Engine: cluster/stack fan-out + deterministic verify + main | `scripts/capabilities.py` (both trees) | ✅ |
| 4 | Capability-derivation constitution | `AGENTS.md` (both trees) | ✅ |
| 5 | Pure-logic tests | `tests/test_capabilities.py` | ✅ |
| 6 | Assert new scripts copied on install | `tests/test_install_recon.py` | ✅ |
| 7 | Full suite + lint + parity | — | ✅ |
| 8 | Regenerate catalog from code (real LLM run) | — | ⏭️ deferred (needs `ANTHROPIC_API_KEY`) |

---

## Validation Results

| Check | Result | Details |
| ----- | ------ | ------- |
| Import (top-level) | ✅ | `cap_lib`, `capabilities`, `utils` import; SDK import deferred |
| Dry-run | ✅ | `--dry-run` exit 0, zero SDK calls |
| Unit tests (compliance) | ✅ | 29 passed (12 new in `test_capabilities.py`) |
| Sibling engine suites | ✅ | `_shared`, `knowledge-compiler`, `claudemd-lerner` all OK — no regressions |
| Lint (my files) | ✅ | ruff clean on all new/edited files |
| Tree parity | ✅ | `diff -q` clean across all 4 shared files |
| Build | N/A | interpreted Python |

Note: repo-wide `uvx ruff check` reports 65 errors, all in files this change did not touch (pre-existing debt). Left untouched per surgical-changes discipline.

---

## Files Changed

| File | Action | Lines |
| ---- | ------ | ----- |
| `…/payload/scripts/capabilities.py` + `compliance-base/scripts/capabilities.py` | CREATE | +394 each |
| `…/payload/scripts/cap_lib.py` + `compliance-base/scripts/cap_lib.py` | CREATE | +175 each |
| `…/payload/scripts/utils.py` + `compliance-base/scripts/utils.py` | UPDATE | +6 each (`file_hash` + `hashlib`) |
| `…/payload/AGENTS.md` + `compliance-base/AGENTS.md` | UPDATE | +21 each (capability-derivation section) |
| `…/tests/test_capabilities.py` | CREATE | +151 |
| `…/tests/test_install_recon.py` | UPDATE | +2 |

`install.py` unchanged — its `payload/scripts/*.py` glob copies the new scripts automatically.

---

## Deviations from Plan

- **Generic `_fan_out(thunks, cfg)`** instead of separate `cluster_all`/`stack_all` copies of `extract_all`. Same bounded-concurrency + `return_exceptions=True` contract; avoids duplicating the semaphore boilerplate for two stages.
- **Idempotency reuse path**: when a framework's catalog hash is unchanged, its capabilities AND stack are reused from the existing `capabilities.json` (reused stacks seeded first so a fresh recommendation wins any slug clash). This makes partial re-runs correct without re-invoking agents for unchanged frameworks.

---

## Issues Encountered

- **Stack↔capability name drift** (seen in the v1 ultracode run): stack agents append parentheticals to the capability name. Handled by joining on `capability_slug` (trailing `(…)`/`—`/`-` clause stripped), unit-tested in `test_capabilities.py::TestSlug` and `TestAssemble::test_schema_and_slug_join`.
- **index.md coupling**: `extract.py._write_index` writes only the constraints table; a later `extract.py` run would drop the "Derived capabilities" section. Pre-existing coupling, out of this plan's scope — noted for a future shared index renderer.

---

## Tests Written

| Test File | Test Cases |
| --------- | ---------- |
| `tests/test_capabilities.py` | slug: parenthetical/em-dash strip, ampersand+inner-hyphen kept, clean↔suffixed share slug; coverage_gap: complete/missing/non-mandatory; assemble: schema+slug-join, uncovered recorded; render: capabilities.md + index.md |
| `tests/test_install_recon.py` | + `capabilities.py`/`cap_lib.py` present after install |

---

## Next Steps

- [ ] Task 8 — operator with `ANTHROPIC_API_KEY` runs `uv run --directory compliance-base python scripts/capabilities.py --all` to regenerate the tracked catalog from code (expect gdpr 109/109, soc2 111/111, iso 59/59; 0 uncovered), then a second run to confirm idempotent skips.
- [ ] Review + PR (`/ship-pr` flushes learning capture before worktree removal).
- [ ] PRD Phase 2 (stack mapping) and Phase 3 (validator) unblocked — can run in parallel.
