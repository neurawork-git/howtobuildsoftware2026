# Feature: Ship a prebuilt compliance catalog + constraint-granularity incremental regen

## Summary

Two related changes to the `compliance-compiler` engine:

1. **Ship a prebuilt catalog with the plugin.** Bundle the already-extracted,
   license-audited GDPR/SOC2/ISO27001 constraint catalog (`catalog/*.json`) and the
   derived capabilities (`capabilities.json`, `capabilities.md`, `index.md`) inside the
   plugin payload, and have `install.py` seed them into a fresh target repo. A new
   install then has a working catalog + capabilities with **no `ANTHROPIC_API_KEY` and
   no LLM run**. ADOPT mode still never clobbers an existing catalog.

2. **Make capability regeneration incremental at constraint granularity.** Today a
   single new constraint in `catalog/<fw>.json` invalidates the whole-file hash and
   forces the entire framework to re-cluster (~25 capabilities) and re-stack. Change it
   so only **added / removed constraint ids** drive LLM work: capabilities whose
   `satisfies` set is unchanged are reused verbatim; only new ids get clustered into
   (new or existing) capabilities, only capabilities whose `satisfies` set changed get
   re-stacked, then the deterministic coverage gate re-runs over the merged framework.

## User Story

As a developer installing the `neurawork-cc-harness` plugin into a new repo
I want the three compliance frameworks' catalog + capabilities to already be present,
and future edits to only re-generate the constraints that actually changed
So that I get instant value without an LLM bill, and extending the catalog is cheap and
does not churn unrelated, already-correct capabilities.

## Problem Statement

- **P1 (shipping):** A fresh `install.py` scaffolds only empty dirs
  (`install.py:75-90`). The catalog is populated only by running `extract.py` (LLM,
  needs an API key) — so out of the box there is nothing to validate PRP plans against
  and no capability guidance. Testable: after `install.py` on a clean git repo (no API
  key), `catalog/gdpr.json`, `catalog/soc2.json`, `catalog/iso27001.json`,
  `catalog/capabilities.json`, `catalog/capabilities.md`, `catalog/index.md` must
  exist and be valid.
- **P2 (incrementality):** Adding one constraint to `gdpr.json` re-derives all ~25 GDPR
  capabilities. The per-framework hash gate at `capabilities.py:308-316` is the coarse
  unit. Testable: with a stored state and existing `capabilities.json`, adding exactly
  one new constraint id must result in LLM work touching only the capability(ies) that
  new id maps to — capabilities whose `satisfies` set is unchanged must be byte-identical
  before/after (verified via the pure delta functions without invoking the SDK).

## Solution Statement

- **Shipping:** add a payload seed subtree `payload/catalog-seed/` holding the six files,
  kept in sync with the repo's own `compliance-base/catalog/` (source of truth) via a
  small `sync_catalog_seed.py` promote step + a drift test. `install.py` gains a
  `_seed_catalog(target)` step that copies each seed file into `<target>/catalog/`
  **only if absent** (mirrors the `if not …exists()` guard used for `config.json` /
  `.gitignore` at `install.py:80-88`), so ADOPT never clobbers. It runs in the scaffold
  phase, never in the unconditional-overwrite `_copy_code`.
- **Incrementality:** keep the whole-file `catalog_hash` gate as the fast "framework
  totally unchanged → reuse" path. When the hash differs, compute a constraint-id delta
  in new pure `cap_lib` helpers, and only fan out agents for the affected capabilities:
  - `new_ids = current_ids − covered_ids`, `orphaned_ids = covered_ids − current_ids`.
  - `orphaned_ids` pruned deterministically (strip from `satisfies`, drop emptied caps).
  - `new_ids` → one **delta-cluster** agent per framework that receives the existing
    capability list + the new constraints and returns id→capability assignments plus any
    brand-new capabilities.
  - Only capabilities whose `satisfies` set changed (gained/lost ids or newly created)
    get a `stack_one` call; unchanged caps keep their `stack`/`stack_notes` verbatim.
  - `assemble_catalog` + coverage gate re-run over the merged framework.
  - If the hash changed but the id set did **not** (a constraint's prose was edited,
    same id), no LLM runs by default — the stored hash is refreshed and caps reused.
    Full re-derivation stays available via `--all`.

## Metadata

| Field            | Value                                                              |
| ---------------- | ----------------------------------------------------------------- |
| Type             | ENHANCEMENT                                                        |
| Complexity       | HIGH (F2 changes the core incremental pipeline + agent contract)  |
| Systems Affected | `compliance-compiler` engine: `install.py`, `payload/scripts/{capabilities.py,cap_lib.py}`, new `payload/catalog-seed/`, new `sync_catalog_seed.py`, tests; live self-host `compliance-base/` |
| Dependencies     | stdlib only; `claude-agent-sdk` on the delta-cluster/stack path only |
| Estimated Tasks  | 12                                                                 |

---

## UX Design

### Before State

```
FRESH INSTALL
  install.py  ──►  copies code + _shared          ──►  catalog/  (EMPTY)
                   scaffolds empty catalog/.shards       .shards/ (empty)
                   writes config.json, .gitignore
  (to get a catalog you must:)
  install.py --extract  ──►  extract.py (~30 SDK agents, needs API key)  ──►  catalog/*.json
  capabilities.py       ──►  cluster+stack (SDK)                          ──►  capabilities.json

ADD ONE CONSTRAINT to gdpr.json
  capabilities.py ──►  file_hash(gdpr.json) changed
                   ──►  WHOLE gdpr re-clustered (1 agent, all constraints)
                   ──►  EVERY gdpr capability re-stacked (~25 agents)
  PAIN: instant value needs an API key; one new constraint churns 25 capabilities.
```

### After State

```
FRESH INSTALL
  install.py  ──►  copies code + _shared
                   scaffolds empty dirs, config, .gitignore
                   _seed_catalog(): copy payload/catalog-seed/* ──►  catalog/  (POPULATED)
                        gdpr.json soc2.json iso27001.json                *.json  ✓
                        capabilities.json capabilities.md index.md        *.md    ✓
                   (only if absent — ADOPT keeps the repo's own catalog)
  RESULT: working catalog + capabilities, NO API key, NO LLM.

ADD ONE CONSTRAINT to gdpr.json  (GDPR-ARTxx-01)
  capabilities.py ──►  file_hash changed → constraint_delta(current, existing_caps)
                   ──►  new_ids = {GDPR-ARTxx-01}, orphaned_ids = {}
                   ──►  1 delta-cluster agent: assign new id (existing cap OR new cap)
                   ──►  re-stack ONLY the capability that gained the id
                   ──►  coverage gate re-runs; unchanged caps byte-identical
  GAIN: 1 (+maybe 1) agent instead of ~26; unrelated capabilities untouched.
```

### Interaction Changes

| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| `install.py` (fresh) | empty `catalog/` | seeded 3 frameworks + capabilities | Works offline, no API key |
| `install.py` (ADOPT) | catalog untouched | catalog untouched (seed only-if-absent) | No regression |
| `capabilities.py` (1 new constraint) | full framework rebuild | constraint-delta rebuild | Cheap extension, no churn |
| `capabilities.py --all` | full rebuild | full rebuild (unchanged) | Escape hatch preserved |

---

## Mandatory Reading

**The implementation agent MUST read these before starting.**

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | 59-90, 100-156, 179-206 | `_copy_code` (overwrite) vs `_scaffold` (only-if-absent) vs `--extract`; where `_seed_catalog` attaches; `_prune_removed` migration pattern |
| P0 | `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/capabilities.py` | 275-414 | `main()`: the `to_run`/`reuse` hash gate (297-320), cluster/stack fan-out (330-367), assemble+coverage (372-380), state write-back (390-395) |
| P0 | `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/cap_lib.py` | 35-113 | `capability_slug`, `coverage_gap`, `assemble_catalog`, `merge_preserving` — where the delta helpers attach and the exact capability dict shape |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/capabilities.py` | 64-95, 98-140, 143-215 | `_build_cluster_prompt`, `_build_stack_prompt`, `cluster_one`/`stack_one` — the agent contracts to extend with a delta-cluster variant |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/utils.py` | 22-49, 52-75 | `load_state`/`save_state`, `file_hash`, `catalog_file`, `load_constraints`, `mandatory_ids` |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py` | 27-114 | temp-git-repo + subprocess install test pattern; idempotent-reinstall + prune assertions to mirror |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_capabilities.py` | 11-100 | `cap_lib` pure-function unit-test pattern (fake catalog, assert on returned dict) |
| P2 | `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | 39-51 | `GITIGNORE` constant — confirm seeded `*.json`/`*.md` stay tracked |
| P2 | `compliance-base/catalog/capabilities.json` | header + one capability | live shape incl. `satisfies`, `stack[]` with `license`/`role`/`verdict` |

**External Documentation:** none required — stdlib Python only; the SDK usage pattern is
already established in `cluster_one`/`stack_one` (local `from claude_agent_sdk import …`).

---

## Patterns to Mirror

**ONLY-IF-ABSENT DATA WRITE (for `_seed_catalog`):**
```python
# SOURCE: install.py:80-88 — never clobber existing data
config = target / "config.json"
if not config.exists():
    ...
gitignore = target / ".gitignore"
if not gitignore.exists():
    gitignore.write_text(GITIGNORE, encoding="utf-8")
```

**CODE-COPY LOOP (shape for the seed copy, but guarded per-file):**
```python
# SOURCE: install.py:63-67
for src in (PAYLOAD / "scripts").iterdir():
    if src.suffix in (".py", ".txt"):
        shutil.copy2(src, target / "scripts" / src.name)
```

**PER-FRAMEWORK HASH GATE (extend, do not replace):**
```python
# SOURCE: capabilities.py:308-316
h = file_hash(cf)
prev = cap_state.get(fw, {})
if (not args.all and prev.get("catalog_hash") == h
        and fw in existing.get("frameworks", {})):
    reuse[fw] = existing["frameworks"][fw]["capabilities"]
else:
    to_run.append((fw, h))
```

**FRAMEWORK-LEVEL MERGE (mirror one level down for capability-list delta):**
```python
# SOURCE: cap_lib.py:104-113
def merge_preserving(existing: dict, fresh: dict) -> dict:
    frameworks = dict(existing.get("frameworks", {}))
    frameworks.update(fresh.get("frameworks", {}))
    ...
```

**COVERAGE MATH (reuse for delta id-set diff):**
```python
# SOURCE: cap_lib.py:46-53
def coverage_gap(capabilities, constraints):
    covered = {cid for c in capabilities for cid in c.get("satisfies", [])}
    return sorted(mandatory_ids(constraints) - covered)
```

**REUSED-STACK CARRYOVER (no agent call — apply to unchanged delta caps):**
```python
# SOURCE: capabilities.py:357-363
for fw, caps in reuse.items():
    for c in caps:
        stacks.append({"capability": c["name"],
                       "components": c.get("stack", []),
                       "notes": c.get("stack_notes", "")})
```

**TEMP-REPO INSTALL TEST:**
```python
# SOURCE: tests/test_install_recon.py:74-88 — drop fake data, reinstall, assert survives
```

**cap_lib PURE UNIT TEST:**
```python
# SOURCE: tests/test_capabilities.py:17-28, 96-100 — fake catalog dir, assert on dict
```

---

## Files to Change

| File | Action | Justification |
|------|--------|---------------|
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/catalog-seed/gdpr.json` | CREATE | Shipped constraint catalog (copied from `compliance-base/catalog/gdpr.json`) |
| `.../payload/catalog-seed/soc2.json` | CREATE | Shipped constraint catalog |
| `.../payload/catalog-seed/iso27001.json` | CREATE | Shipped constraint catalog |
| `.../payload/catalog-seed/capabilities.json` | CREATE | Shipped derived capabilities (license-audited) |
| `.../payload/catalog-seed/capabilities.md` | CREATE | Shipped human-readable capabilities |
| `.../payload/catalog-seed/index.md` | CREATE | Shipped combined index |
| `.../engines/compliance-compiler/install.py` | UPDATE | Add `_seed_catalog(target)`, call it in scaffold phase; add `SEED_DIR` const |
| `.../engines/compliance-compiler/sync_catalog_seed.py` | CREATE | Promote `compliance-base/catalog/*` → `payload/catalog-seed/`; drift-check mode |
| `.../payload/scripts/cap_lib.py` | UPDATE | Add `constraint_delta`, `prune_orphaned_ids`, `merge_delta_capabilities` (pure) |
| `.../payload/scripts/capabilities.py` | UPDATE | Wire delta path; add `_build_delta_cluster_prompt` + `delta_cluster_one`; per-constraint state |
| `.../payload/scripts/utils.py` | UPDATE (maybe) | Optional `constraint_hashes` helper if content-change detection is enabled |
| `.../tests/test_install_recon.py` | UPDATE | Assert seed copied on FRESH, not clobbered on ADOPT |
| `.../tests/test_capabilities.py` | UPDATE | Unit tests for the three new `cap_lib` delta functions |
| `.../tests/test_catalog_seed.py` | CREATE | Drift test: `payload/catalog-seed/*` matches `compliance-base/catalog/*` |
| `compliance-base/scripts/{cap_lib.py,capabilities.py,utils.py}` | UPDATE | Refresh live self-host copies (kept identical to payload) |

---

## NOT Building (Scope Limits)

- **Incremental `extract.py`.** Extraction stays a full rebuild (it has no hash logic
  today, `extract.py` has no skip path). Only `capabilities.py` becomes constraint-incremental.
- **Content-edit re-clustering by default.** Editing a constraint's prose without
  changing its id does **not** trigger re-derivation in the default path (user wants
  regen only when *new* constraints arrive). It is reachable via `--all`. An optional
  `constraint_hashes` state key MAY flag edited ids, but acting on them is out of scope
  for the default run.
- **Auto-promoting the seed on every capabilities run.** `sync_catalog_seed.py` is a
  manual/CI promote step, not wired into `capabilities.py`.
- **New frameworks in the shipped seed.** Only the three current frameworks ship. A new
  framework still needs `extract.py` + `capabilities.py` (LLM) in the target.
- **Changing the license/cost policy.** The stack prompt's OSS/embeddable +
  internal-infra rules stay exactly as they are.

---

## Step-by-Step Tasks

Execute in order. Each task is atomic and independently verifiable.

### Task 1: CREATE `payload/catalog-seed/` from the audited catalog

- **ACTION**: create the seed dir and copy the six files from `compliance-base/catalog/`.
- **IMPLEMENT**: `gdpr.json`, `soc2.json`, `iso27001.json`, `capabilities.json`,
  `capabilities.md`, `index.md` copied verbatim into
  `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/catalog-seed/`.
- **GOTCHA**: do NOT copy `.shards/`, `reports/`, or `state.json` (local machinery).
- **VALIDATE**: `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('plugins/neurawork-cc-harness/engines/compliance-compiler/payload/catalog-seed/*.json')]"` — all JSON parses.

### Task 2: CREATE `sync_catalog_seed.py` (promote + drift check)

- **ACTION**: create `engines/compliance-compiler/sync_catalog_seed.py`.
- **IMPLEMENT**: a `--check` mode that compares each `compliance-base/catalog/<name>`
  against `payload/catalog-seed/<name>` and exits non-zero on any diff; default mode
  copies source → seed. File list: the six names from Task 1.
- **MIRROR**: `install.py` path-constant style (`PAYLOAD`, `Path(__file__).resolve()`).
- **GOTCHA**: resolve `compliance-base/catalog` relative to the repo root (walk up from
  the engine dir), not the CWD.
- **VALIDATE**: `python3 plugins/neurawork-cc-harness/engines/compliance-compiler/sync_catalog_seed.py --check` exits 0 right after Task 1.

### Task 3: UPDATE `install.py` — add `_seed_catalog`

- **ACTION**: add `SEED_DIR = PAYLOAD / "catalog-seed"` and a `_seed_catalog(target)` fn.
- **IMPLEMENT**: for each file in `SEED_DIR` (`*.json`, `*.md`), `dst = target / "catalog" / f.name`; copy **only if** `not dst.exists()`. Call `_seed_catalog(target)` inside `main()` right after `_scaffold(...)`, before the hook merge.
- **MIRROR**: `install.py:80-88` only-if-absent guard; `install.py:63-67` copy loop.
- **GOTCHA**: must NOT live in `_copy_code` (unconditional overwrite → would clobber a
  repo's own extracted catalog on ADOPT reinstall). `catalog/` dir already ensured by
  `_scaffold` (`install.py:77`).
- **VALIDATE**: `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests` (after Task 9) — new seed test passes.

### Task 4: VERIFY `.gitignore` keeps seeded outputs tracked

- **ACTION**: confirm the `GITIGNORE` constant (`install.py:39-51`) does not match
  `catalog/*.json`, `catalog/capabilities.md`, or `catalog/index.md`.
- **IMPLEMENT**: no code change expected; if `capabilities.md`/`index.md` were somehow
  matched, adjust the comment/negation. (Current constant ignores only `.shards/`,
  `reports/`, `state.json`, `last-extract.json`, `*.log`, caches.)
- **VALIDATE**: in a temp install, `git check-ignore catalog/capabilities.md` returns
  non-zero (not ignored).

### Task 5: UPDATE `cap_lib.py` — `constraint_delta` (pure)

- **ACTION**: add `def constraint_delta(current_ids: set[str], existing_caps: list[dict]) -> dict`.
- **IMPLEMENT**: `covered = {cid for c in existing_caps for cid in c.get("satisfies", [])}`; return `{"new_ids": sorted(current_ids - covered), "orphaned_ids": sorted(covered - current_ids), "unchanged": not (current_ids - covered) and not (covered - current_ids)}`.
- **MIRROR**: the set-comprehension in `coverage_gap` (`cap_lib.py:46-53`).
- **GOTCHA**: `current_ids` is derived from the constraint file via
  `{c["id"] for c in constraints}`; caller passes the set, keep the helper pure.
- **VALIDATE**: `python3 -m unittest ...test_capabilities` (Task 10) covers add/remove/none.

### Task 6: UPDATE `cap_lib.py` — `prune_orphaned_ids` + `merge_delta_capabilities` (pure)

- **ACTION**: add two pure helpers.
- **IMPLEMENT**:
  - `prune_orphaned_ids(caps, orphaned_ids) -> list[dict]`: for each cap, drop orphaned
    ids from `satisfies`; drop caps whose `satisfies` becomes empty.
  - `merge_delta_capabilities(existing_caps, assignments, new_caps) -> list[dict]`:
    apply `assignments` (`{cap_name: [ids]}`) by appending ids to the named existing cap's
    `satisfies` (sorted+deduped, mirroring `assemble_catalog` normalization at
    `cap_lib.py:79-86`); append `new_caps` (each `{name,category,description,satisfies}`
    with empty `stack`/`stack_notes` to be filled by stacking). Join by exact `name`; if a
    name is missing, fall back to `capability_slug` match.
- **GOTCHA**: preserve each untouched cap's existing `stack`/`stack_notes` verbatim.
- **VALIDATE**: unit tests in Task 10.

### Task 7: UPDATE `capabilities.py` — delta-cluster agent contract

- **ACTION**: add `_build_delta_cluster_prompt(fw, existing_caps, new_constraints, shard_path)` and `delta_cluster_one(fw, existing_caps, new_constraints, cfg)`.
- **IMPLEMENT**: prompt gives the agent (a) the existing capability list (name +
  description + `satisfies`) and (b) the full text of only the NEW constraints, and asks
  it to either assign each new id to an existing capability name or define a new
  capability — output `{"assignments": {name: [ids]}, "new_capabilities": [{name,category,description,satisfies}]}`. Reuse the shard-file write + parse mechanics of `cluster_one` (`capabilities.py:143-176`) and the local `from claude_agent_sdk import …` pattern.
- **GOTCHA**: enforce "every new id assigned exactly once" in the prompt (mirror
  `capabilities.py:83-84`); `category` must be one of `cap_lib.CATEGORIES`.
- **VALIDATE**: not unit-tested (SDK); exercised by manual run in Task 12.

### Task 8: UPDATE `capabilities.py` — wire the delta path into `main()`

- **ACTION**: extend the per-framework decision (`capabilities.py:297-320`) with a middle
  tier between full-reuse and full-rebuild.
- **IMPLEMENT**: when `file_hash` differs and `fw in existing["frameworks"]` and not
  `--all`: compute `current_ids` from the constraint file, `delta = cap_lib.constraint_delta(current_ids, existing_caps)`.
  - `delta["unchanged"]` (hash changed but id set identical) → reuse caps, just refresh
    `cap_state[fw]["catalog_hash"]`, no agent.
  - else → run `delta_cluster_one`; `caps = prune_orphaned_ids(existing_caps, delta["orphaned_ids"])`; `caps = merge_delta_capabilities(caps, assignments, new_caps)`; mark which caps' `satisfies` changed → those + new caps go to `fresh_unique` for stacking; unchanged caps carry stacks over verbatim (mirror `capabilities.py:357-363`).
  - Fall back to the existing full-rebuild path when `fw not in existing` (first run) or `--all`.
- **GOTCHA**: after merge, run `assemble_catalog` for the framework so `mandatory_covered`/`uncovered_mandatory_ids` recompute; the coverage gate (`capabilities.py:373-376`) then covers delta frameworks too. Keep atomic writes (`_write_json_atomic`).
- **VALIDATE**: manual run (Task 12) + coverage gate exits 0.

### Task 9: UPDATE `tests/test_install_recon.py` — seed assertions

- **ACTION**: add a FRESH-install seed test and an ADOPT no-clobber test.
- **IMPLEMENT**: after a fresh `_install(repo)`, assert `catalog/gdpr.json`,
  `catalog/capabilities.json`, `catalog/capabilities.md`, `catalog/index.md` exist and
  parse; then write a sentinel into `catalog/gdpr.json`, reinstall, assert the sentinel
  survives (seed did not overwrite).
- **MIRROR**: `test_install_recon.py:74-88` idempotent-reinstall pattern.
- **VALIDATE**: `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests`.

### Task 10: UPDATE `tests/test_capabilities.py` — delta unit tests

- **ACTION**: add tests for `constraint_delta`, `prune_orphaned_ids`, `merge_delta_capabilities`.
- **IMPLEMENT**: cover: one new id → `new_ids` has it, `unchanged` False; one removed id →
  `orphaned_ids` has it; identical set → `unchanged` True; prune empties a cap; merge
  appends to an existing cap by name and adds a new cap; assert unchanged caps stay
  byte-identical (including `stack`).
- **MIRROR**: `test_capabilities.py:17-28` fake-data + direct-call style (no SDK).
- **VALIDATE**: `python3 -m unittest discover -s plugins/neurawork-cc-harness/engines/compliance-compiler/tests`.

### Task 11: CREATE `tests/test_catalog_seed.py` — drift test

- **ACTION**: assert `payload/catalog-seed/<name>` equals `compliance-base/catalog/<name>` for the six files.
- **IMPLEMENT**: read both, compare bytes (or parsed JSON for `*.json`); fail with a
  message telling the developer to run `sync_catalog_seed.py`. Skip gracefully if
  `compliance-base/catalog` is absent (so the test is a no-op in a pure plugin checkout).
- **VALIDATE**: passes after Task 1/Task 2.

### Task 12: SYNC live self-host copies + full manual run

- **ACTION**: copy the updated `capabilities.py`, `cap_lib.py`, (`utils.py`) from payload
  into `compliance-base/scripts/`; run `sync_catalog_seed.py`; do a manual incremental run.
- **IMPLEMENT**: append one fake constraint id to `compliance-base/catalog/gdpr.json`,
  run `uv run --directory compliance-base python scripts/capabilities.py`, confirm only
  the affected capability re-stacked and coverage gate exits 0; then revert the fake
  constraint and re-run to confirm reuse.
- **GOTCHA**: needs `ANTHROPIC_API_KEY`; if unavailable, stop after the pure-logic dry
  path and note it.
- **VALIDATE**: `uvx ruff check` clean on changed files; all four engine test dirs green.

---

## Testing Strategy

### Unit / integration tests

| Test File | Test Cases | Validates |
|-----------|-----------|-----------|
| `tests/test_capabilities.py` | delta add/remove/none, prune-empty, merge-by-name, merge-new-cap, unchanged-caps-identical | F2 pure logic |
| `tests/test_install_recon.py` | fresh seeds 6 files + valid; ADOPT keeps sentinel | F1 install/adopt |
| `tests/test_catalog_seed.py` | seed == compliance-base catalog (skips if absent) | F1 drift guard |

### Edge Cases Checklist

- [ ] Fresh install with NO API key → catalog present and valid.
- [ ] ADOPT reinstall over a hand-edited `catalog/gdpr.json` → not clobbered.
- [ ] New constraint id → only its capability re-stacked; others byte-identical.
- [ ] Removed constraint id → pruned; a capability emptied of all ids is dropped.
- [ ] Hash changed but id set identical → no LLM, hash refreshed.
- [ ] `--all` → full rebuild (unchanged behavior).
- [ ] Delta run still fails the coverage gate if a new mandatory id ends up uncovered.
- [ ] First-ever run for a framework (no `existing`) → falls back to full cluster.

---

## Validation Commands

### Level 1: STATIC_ANALYSIS
```bash
cd plugins/neurawork-cc-harness/engines/compliance-compiler && uvx ruff check payload/scripts install.py sync_catalog_seed.py
```
**EXPECT**: no NEW errors beyond the pre-existing ISC004/I001 in unchanged lines.

### Level 2: UNIT_TESTS (per-dir, as CLAUDE.md mandates)
```bash
cd plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: all tests pass.

### Level 3: FULL_SUITE (all engines, no regressions)
```bash
cd plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s _shared/tests
python3 -m unittest discover -s knowledge-compiler/tests
python3 -m unittest discover -s claudemd-lerner/tests
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: all pass.

### Level 4: SEED DRIFT
```bash
python3 plugins/neurawork-cc-harness/engines/compliance-compiler/sync_catalog_seed.py --check
```
**EXPECT**: exit 0.

### Level 5: MANUAL INCREMENTAL (needs API key)
```bash
uv run --directory compliance-base python scripts/capabilities.py            # reuse-all, no agents
# append a fake constraint to catalog/gdpr.json, then:
uv run --directory compliance-base python scripts/capabilities.py            # only affected cap re-stacked
```
**EXPECT**: log shows delta (1 new id) not a full framework rebuild; coverage gate OK.

---

## Acceptance Criteria

- [ ] Fresh `install.py` (no API key) yields valid `catalog/{gdpr,soc2,iso27001}.json` +
      `capabilities.json` + `capabilities.md` + `index.md`.
- [ ] ADOPT reinstall never overwrites an existing catalog file.
- [ ] Adding one constraint re-derives only the affected capability; unchanged
      capabilities are byte-identical.
- [ ] Removed constraints pruned; coverage gate still enforced on delta runs.
- [ ] `--all` still performs a full rebuild.
- [ ] `sync_catalog_seed.py --check` green; seed tracked in git (not gitignored).
- [ ] Level 1-4 pass; live `compliance-base/scripts` copies match payload.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Seed drifts from `compliance-base/catalog` over time | MED | MED | `test_catalog_seed.py` fails CI on drift; `sync_catalog_seed.py` one-command promote |
| Delta-cluster agent assigns a new id AND leaves a mandatory id uncovered | MED | HIGH | Coverage gate runs over the merged framework (`assemble_catalog` → `uncovered_mandatory_ids`), non-empty → exit 1 |
| Seeded catalog shipped in plugin bloats the package | LOW | LOW | Six JSON/MD files (~250 KB); acceptable, they are the product's value |
| `--extract` in a target overwrites the seeded catalog with a fresh LLM extraction | LOW | MED | Expected/intended (explicit rebuild); document that seed is a starting point |
| Name-based merge in `merge_delta_capabilities` misses a renamed capability | MED | MED | Fall back to `capability_slug` match; unit-test the fallback |
| Whole-file hash still triggers on trivial reformatting of the constraint file | MED | LOW | `constraint_delta` `unchanged` branch → no LLM, only refresh stored hash |

---

## Notes

- **Source of truth is `compliance-base/catalog/`** — the license-audited catalog. The
  payload seed is a *promoted copy*; never hand-edit `payload/catalog-seed/` directly,
  run `sync_catalog_seed.py`.
- **Two-level incrementality** is deliberate: keep the cheap whole-file hash as a fast
  "nothing changed" gate, add the id-delta only when the hash differs. This matches the
  user's rule: regenerate only when new constraints arrive, never wholesale.
- **Self-host duplication**: `compliance-base/scripts/{capabilities,cap_lib,utils}.py`
  are copies of payload and must be refreshed in the same change (Task 12), per the
  engine/payload convention in `plugins/CLAUDE.md`.
- **Confidence**: 8/10 for one-pass. F1 is mechanical and low-risk. F2's pure helpers
  are well-specified and unit-testable; the only soft spot is the delta-cluster agent
  prompt quality, which is exercised only by the manual run (Task 12) since it needs the
  SDK.
