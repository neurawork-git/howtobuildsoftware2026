# Implementation Report

**Plan**: `.claude/PRPs/plans/compliance-prebuilt-catalog-incremental.plan.md`
**Branch**: `feature/compliance-catalog-seed`
**Date**: 2026-07-23
**Status**: COMPLETE (SDK-dependent full run deferred — see Deviations)

---

## Summary

Two changes to the `compliance-compiler` engine:

1. **Prebuilt catalog shipped with install.** New `payload/catalog-seed/` holds the six
   audited catalog files; `install.py._seed_catalog()` copies them into a fresh target's
   `catalog/` only-if-absent (ADOPT never clobbers). A fresh install now has a working
   catalog + capabilities with no API key and no LLM. `sync_catalog_seed.py` promotes
   `compliance-base/catalog/` → the seed and a drift test guards them.

2. **Constraint-granularity incremental regen.** `capabilities.py` now classifies each
   framework into three tiers: whole-file-hash match → full reuse; hash changed but the
   constraint id set is identical → reuse + refresh hash (no LLM); id set changed → a
   delta-cluster agent places only the new ids into existing/new capabilities, only
   capabilities that gained ids (or are new) get re-stacked, orphaned ids are pruned
   deterministically, and the coverage gate re-runs over the merged framework. `--all`
   still forces a full rebuild. Delta logic lives in three pure `cap_lib` helpers.

---

## Assessment vs Reality

| Metric     | Predicted | Actual | Reasoning |
| ---------- | --------- | ------ | --------- |
| Complexity | HIGH      | HIGH   | F2 touched the core pipeline + a new agent contract, as expected |
| Confidence | 8/10      | 8/10   | Pure helpers + three-tier classification verified without SDK; only the delta-cluster agent prompt is unverified (needs API key) |

---

## Tasks Completed

| # | Task | File | Status |
|---|------|------|--------|
| 1 | Seed dir from audited catalog | `payload/catalog-seed/*` (6 files) | ✅ |
| 2 | Promote + drift-check script | `sync_catalog_seed.py` | ✅ |
| 3 | `_seed_catalog` in install | `install.py` | ✅ |
| 4 | Verify gitignore keeps outputs tracked | `install.py` (no change needed) | ✅ |
| 5 | `constraint_delta` | `payload/scripts/cap_lib.py` | ✅ |
| 6 | `prune_orphaned_ids` + `merge_delta_capabilities` | `payload/scripts/cap_lib.py` | ✅ |
| 7 | delta-cluster agent + prompt | `payload/scripts/capabilities.py` | ✅ |
| 8 | wire delta path into `main()` | `payload/scripts/capabilities.py` | ✅ |
| 9 | install seed tests | `tests/test_install_recon.py` | ✅ |
| 10 | delta unit tests | `tests/test_capabilities.py` | ✅ |
| 11 | drift test | `tests/test_catalog_seed.py` | ✅ |
| 12 | sync live self-host + verify | `compliance-base/scripts/*` | ✅ (full API run deferred) |

---

## Validation Results

| Check | Result | Details |
| ----- | ------ | ------- |
| Compile (py_compile) | ✅ | payload + live copies |
| Lint (ruff) | ✅ | no new issues beyond 1 TRY004 that mirrors `cluster_one`/`stack_one`; rest pre-existing |
| Unit tests | ✅ | 83 pass (18 _shared + 15 kc + 13 cl + 37 co; co was 29) |
| Seed drift | ✅ | `sync_catalog_seed.py --check` green |
| Incremental wiring | ✅ | isolated `COMPLIANCE_ROOT` dry-run: reuse-all / delta-on-new-id / reuse-on-text-edit |
| Delta-cluster agent (SDK) | ⏭️ | needs `ANTHROPIC_API_KEY`; deferred |

Isolated dry-run proof:
- all hashes match → `reuse: gdpr, soc2, iso27001`
- add `GDPR-ARTZZ-99` → `Δ gdpr: +1 new / -0 orphaned`, `delta: gdpr`, `reuse: soc2, iso27001`
- reword an existing constraint (same id set) → `~ gdpr: constraint id set unchanged — reusing, refreshing hash`

---

## Files Changed

| File | Action |
| ---- | ------ |
| `payload/catalog-seed/{gdpr,soc2,iso27001,capabilities}.json`, `capabilities.md`, `index.md` | CREATE |
| `sync_catalog_seed.py` | CREATE |
| `tests/test_catalog_seed.py` | CREATE |
| `install.py` | UPDATE (SEED_DIR, `_seed_catalog`, call) |
| `payload/scripts/cap_lib.py` | UPDATE (3 delta helpers) |
| `payload/scripts/capabilities.py` | UPDATE (delta agent + prompt + main wiring + hash persistence) |
| `tests/test_capabilities.py` | UPDATE (3 delta test classes) |
| `tests/test_install_recon.py` | UPDATE (seed assertions, sentinel no-clobber) |
| `compliance-base/scripts/{cap_lib,capabilities}.py` | UPDATE (live self-host refresh) |

---

## Deviations from Plan

- **Task 12 full incremental run deferred.** The plan's manual end-to-end run needs
  `ANTHROPIC_API_KEY` and would mutate tracked catalog files + cost money. Instead the
  three-tier classification was proven in an isolated `COMPLIANCE_ROOT` temp dir via
  `--dry-run` (which returns before any agent). The pure delta helpers are unit-tested;
  only the delta-cluster **prompt quality** remains to be validated on a real API run.
- **`utils.py` untouched.** The plan flagged an optional `constraint_hashes` helper for
  content-change detection — not needed: the id-set delta + the "unchanged" branch cover
  the requirement (regen only on new/removed ids), and `load_constraints` already existed.

---

## Tests Written

| Test File | Test Cases |
| --------- | ---------- |
| `tests/test_capabilities.py` | `TestConstraintDelta` (new/orphaned/identical), `TestPruneOrphaned` (strip+drop, partial), `TestMergeDeltaCapabilities` (assign-by-name+new-cap, slug fallback) |
| `tests/test_install_recon.py` | fresh install seeds 6 valid files + not gitignored; sentinel survives ADOPT reinstall |
| `tests/test_catalog_seed.py` | seed bytes == `compliance-base/catalog` (skips if absent) |

---

## Next Steps

- [ ] Optional: one real `capabilities.py` incremental run with an API key to validate the
      delta-cluster agent prompt (append a constraint, confirm only the affected cap re-stacks).
- [ ] Review + create PR (`/ship-pr` or `/prp-pr`) — `/ship-pr` flushes the worktree's
      learning capture before removal.
