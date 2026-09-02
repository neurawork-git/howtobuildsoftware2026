# stack.py honours config["frameworks"], and retains the frameworks it switches off

**Plan ID:** `stack-scaffold-honours-enabled-frameworks`
**Source PRD:** None
**PRD Phase:** None
**Source Issue:** https://github.com/neurawork-git/howtobuildsoftware2026/issues/46
**Plan Publication:** https://github.com/neurawork-git/howtobuildsoftware2026/issues/46#issuecomment-5508049927

## Outcome

**Problem:** `compliance-base/scripts/stack.py` never reads `config.json`. `main()` loads `catalog/capabilities.json` as the entire capability universe and hands it unfiltered to `scaffold()`, `gaps()` and `render_gap_report()`, so `catalog/stack.json` — the closed identity set every stack-compiler pass trusts — is a function of what was ever derived rather than of what the operator enabled. An operator who narrowed `frameworks` to `["gdpr"]` still paid a $1.60 `st-scope` run over 68 capabilities, 43 of them from deselected frameworks, and the run then wrote nothing because a CHALLENGE agent refuted a claim about `soc2/capacity-planning-elastic-scaling` — a capability that should never have been in the scope set. Scoping is all-or-nothing, so one out-of-scope framework discards the whole paid pass.

**Affected user:** The operator of a repo that has the compliance and stack compilers installed and does not want every extracted framework in play.

**User outcome:** `config.json`'s `frameworks` list is the single switch. Turning a framework off removes it from the stack pipeline on the next `--scaffold`; turning it back on restores it — including every scoping, ranking and selection decision previously recorded against it — with no LLM cost and no manual file surgery.

**Invariant:** No pass ever destroys derived or decided data as a side effect of a config edit. `catalog/capabilities.json` keeps every framework it has ever derived; `catalog/stack.json` keeps every decision it has ever recorded. The config selects what is *in play*, never what still *exists*.

**Success signal:** A scope run in a repo with `frameworks: ["gdpr"]` covers only the gdpr capabilities. In the reporter's repo that was 25 capabilities for $0.69 instead of 68 for $1.60, and it completed instead of aborting. Re-enabling `soc2` afterwards and re-running `--scaffold` restores its previously recorded choices rather than presenting them as new.

**Approach:** `main()` reads `load_cfg()` once and partitions the catalog by `cfg["frameworks"]`. `scaffold()` writes the enabled frameworks' capabilities into `stack.json`'s existing `choices` map and moves the disabled frameworks' entries, decisions intact, into a sibling `disabled` map in the same file. `choices` keeps meaning exactly what it means today — the working universe — so none of the fifteen downstream consumers across both engines change. An empty intersection is refused with a named cause instead of silently emptying the file.

## Recommendation

The defect is one missing call. `stack.py:76` imports `CATALOG_DIR, FRAMEWORK_TITLES, REPORTS_DIR, ROOT_DIR, today_iso` from `config` and never calls `load_cfg()`; `grep -n load_cfg compliance-base/scripts/stack.py` returns nothing. Every other script in the extraction pipeline already reads the key as the enabled set — `shards.py:127`, `extract.py:214`, `capabilities.py:391`, and `utils.validation_frameworks` (`utils.py:108`), whose docstring resolves an empty `validate_frameworks` to "all extracted `frameworks`". `stack.py` is the one consumer of derived catalog data with no config read, so honouring the key restores an established pattern rather than inventing one.

The design question is not *whether* to filter but **where the disabled frameworks' recorded decisions go**. Filtering alone is not safe: `scaffold()` carries a key's decision fields forward only when it finds that key in the current `stack.json` (`stack.py:185,193`). A plain filter therefore deletes `chosen`, `rationale`, `chosen_from`, `applicable`, `applicability_reason`, `scoped_from`, `ranked` and `ranked_from` for every capability of a disabled framework in a single run — and re-enabling plus re-scaffolding brings the key back blank, verified live. That is the same data destruction the issue exists to prevent, one layer down, and it costs a paid scope and rank pass plus the human selection work to recover.

So `stack.json` becomes the complete file: `choices` holds the enabled frameworks, a sibling `disabled` map holds the rest with their records untouched, and `scaffold()` — which `CLAUDE.md` names the single schema owner of `stack.json` — is the only code that moves entries between them. It reads previous decisions from both maps, so re-enabling is a config edit plus a re-scaffold.

This is deliberately a second map rather than an `enabled: false` flag inside `choices`. Fifteen distinct sites across `compliance-base/scripts/` and `stack-base/scripts/` read `stack["choices"]` as the working universe (`scope_lib.py:66`, `rank_lib.py:68,87`, `selection_lib.py:53`, `gate_lib.py:235,244,302`, `validate.py:96`, `precheck.py:187`, `stack.py` itself at 243, 300, 342, 420, 463, plus the counters in `main()`). A per-entry flag would have to be honoured at every one of them, and the one that forgets is a silent leak of exactly the kind this issue reports. The sibling map changes none of them: `choices` continues to mean the working universe, and the retained records are simply not in it. The record shape is identical in both maps, so this is one form in two buckets, not a second data form.

Two facts make this safe and were verified rather than assumed. `capabilities_hash` is `file_hash(CAPABILITIES_JSON)` (`stack.py:640`, `utils.py:40`) — a hash of the file's bytes, decoupled from any in-memory narrowing — so filtering cannot change it and cannot reopen settled choices. And per-capability staleness compares `chosen_from` against `capability_hash(described[key])` (`gaps():268-272`), which reads only the one capability's own fields, so it is likewise unaffected by which frameworks are in play.

The empty-intersection guard is not defensive padding; it closes a live hole. Today a catalog narrowed to nothing produces `choices = {}`, a gap report reading "0 of 0 … Nothing to report.", and **exit 0** — every recorded choice gone, reported as a clean stack. `stack-base/scripts/scope.py:394` already guards the same state and exits 1; `stack.py` must match.

### Evidence

- `compliance-base/scripts/stack.py:76` — the `config` import list; `load_cfg` is absent from the whole file.
- `compliance-base/scripts/stack.py:636-640` — `main()` loads the catalog, guards only on it being non-empty, and computes `cap_hash` from the file.
- `compliance-base/scripts/stack.py:185,193` — `scaffold()` carries decisions forward only for keys found in the existing `stack.json`; this is why a plain filter destroys them.
- `compliance-base/scripts/stack.py:188` — the `scaffold()` framework loop; `:107`, `:166`, `:481`, `:520` are the other four unfiltered iterations.
- `compliance-base/scripts/precheck.py:159-174` — `known_capabilities(frameworks, catalog_dir)` already returns `{"frameworks": filtered}`: the precedent for the partition helper, and the shape the narrowed catalog must have.
- `compliance-base/scripts/config.py:19,47-72` — `COMPLIANCE_ROOT` override, `DEFAULT_CFG["frameworks"]`, and `load_cfg()` (never raises).
- `compliance-base/scripts/stack.py:199-206` — the eight decision-owned fields that a plain filter would blank.
- `stack-base/scripts/scope_lib.py:53-79` — `capability_universe()` derives the scoping universe purely from `stack["choices"]` keys; this is why retained entries must live outside that map.
- `stack-base/scripts/scope.py:394-399` — the empty-universe guard `stack.py` currently lacks.
- Issue #46 and its root-cause comment https://github.com/neurawork-git/howtobuildsoftware2026/issues/46#issuecomment-5507706469 — the proven causal chain and the reporter's explicit "filter, not a prune" requirement.

### Alternatives considered

- **Filter and let the entries drop, relying on git to restore them.** `stack.json` is tracked, `--scaffold` prints what it dropped, and `git show` recovers the file — so nothing is unrecoverable in the strict sense. Rejected because recovery is manual, out-of-band, and merges badly with a `stack.json` that has moved on since; and because it makes a config edit destructive, which is the failure mode the issue is about. The operator asked explicitly for a complete file where things are switched on and off and nothing is deleted.
- **An `enabled: false` flag on each entry in `choices`.** Symmetric with the existing `applicable: false` precedent, which keeps a scoped-out capability in place with a reason rather than omitting it. Rejected on seam cost: `applicable` is honoured at a handful of sites inside `stack.py` plus the three stack-base passes, while `choices`-as-universe is read at fifteen sites across two engines, and every one would need the new predicate. A missed site leaks a disabled framework back into a paid pass — the exact bug being fixed.
- **Prune the unwanted frameworks out of `capabilities.json`.** The reporter's manual workaround. Rejected by the issue itself: it destroys expensive LLM-derived data so that re-enabling a framework means re-deriving it.
- **Filter inside `stack-base/scripts/scope_lib.py` instead.** Rejected: it would give the identity set two owners and let `stack.json` and the scoped universe disagree, against `CLAUDE.md`'s "single schema owner" rule. `scope_lib` is the propagation path, not the defect.
- **Add a warning to `scope.py` when `stack.json` holds a framework absent from the config.** Deliberately out of scope. Once `stack.py` filters, `scope.py`'s universe is correct by construction; the warning would cover only the window between a config edit and the next `--scaffold`, and it would make `stack-base` read `compliance-base/config.json` — a new cross-engine dependency for a case the `--scaffold` output already reports.

## Root Cause

- **Observed failure:** With `compliance-base/config.json` set to `{"frameworks": ["gdpr"]}` and a three-framework `capabilities.json`, `stack.py --scaffold` writes all three frameworks' keys into `stack.json`. Reproduced twice with no LLM or network call: at unit level (`scaffold()` has no config parameter at all — signature `(catalog, existing=None, catalog_dir=None, generated=None, capabilities_hash='')`, scaffolded keys `['gdpr/…', 'iso27001/…', 'soc2/…']`) and at CLI level in a temp install under `COMPLIANCE_ROOT`, which printed `stack.json: 3 capabilities (0 choice(s) carried, 3 new)`.
- **Causal chain:** `stack.py` never calls `load_cfg()` (`:76`) → `main()` passes the raw catalog to `scaffold()` (`:641`) → `scaffold()` iterates `catalog["frameworks"]` unfiltered (`:188`) → every derived framework becomes a `stack.json` key → `scope_lib.capability_universe()` (`stack-base/scripts/scope_lib.py:53-79`) builds the scoping universe from those keys → `scope.py` fans out one paid agent per framework over a universe 2.7× larger than the operator asked for → a refutation on an out-of-scope capability aborts the whole run (`stack-base/scripts/scope.py:491`), and `apply_scope` refuses any partial write (`compliance-base/scripts/stack.py:304`).
- **Fix boundary:** `compliance-base/scripts/stack.py:636-641` — `main()` must read the config and partition the catalog once, before `scaffold()`, `gaps()` and `render_gap_report()` see it. The authoritative copy is `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/stack.py`; the two are byte-identical and pinned by `test_payload_drift.py`.
- **Regression proof:** A new `TestEnabledFrameworks` / extended `TestScaffold` in `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_stack.py`, plus one CLI-level test driving `main()` under `COMPLIANCE_ROOT`. Both fail today: the pure test because `scaffold()` takes no `enabled` argument, the CLI test because `--scaffold` emits every framework regardless of `config.json`.
- **Remaining uncertainty:** `compliance-base/CLAUDE.md:28` describes `frameworks` as "what gets extracted", which read literally would make today's behaviour correct. The operator has decided the key is the enabled set; the doc line is corrected as part of task 5. Not a design fork — the fix location is identical either way.

## Visuals

```
                        compliance-base/config.json
                            frameworks: ["gdpr"]
                                    │
catalog/capabilities.json           │  (never read today — the defect)
  gdpr     ──┐                      ▼
  soc2     ──┼──►  main(): partition by cfg["frameworks"]
  iso27001 ──┘            │                    │
   (never pruned;         │ enabled            │ disabled
    keeps everything      ▼                    ▼
    ever derived)   scaffold() ──► stack.json ──► "choices"  {gdpr/*}   ── the working universe
                                        │                                  scope / rank / select
                                        └──────► "disabled" {soc2/*,       ── retained verbatim,
                                                             iso27001/*}      no pass sees it

  re-enable = one config line + --scaffold; entries move back with every decision intact
  capabilities_hash = file_hash(capabilities.json) — unaffected by the partition, reopens nothing
```

## Implementation Context

### Mandatory reading

| File | Why it matters |
|---|---|
| `compliance-base/scripts/stack.py:1-65` | The module docstring is the schema contract for `stack.json` and must be extended, not contradicted. It documents machine-owned vs decision-owned fields and the report-only exit-0 rule. |
| `compliance-base/scripts/stack.py:176-214` | `scaffold()` — the partition happens here; `:185,193` is the carry-forward that must now read both maps, `:208-214` the returned document. |
| `compliance-base/scripts/stack.py:217-286` | `gaps()` — what `orphaned` means (`:284`), why `mandatory_total` counts only applicable capabilities, and that `stale` is advisory. |
| `compliance-base/scripts/stack.py:620-751` | `main()` — the load, the guard, `cap_hash`, the four CLI branches, and the always-run report. Exit conventions: `return 1` with a printed cause on refusal, `return 0` for the report path. |
| `compliance-base/scripts/precheck.py:159-174` | `known_capabilities()` — the precedent partition helper and the `{"frameworks": {...}}` shape to return. |
| `compliance-base/scripts/config.py:19,47-72` | `COMPLIANCE_ROOT`, `DEFAULT_CFG`, `load_cfg()`. |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_stack.py:1-62` | Test conventions: imports `stack` from `payload/scripts`, `_constraints(tmp)` builds a temp constraint catalog, `_capabilities()` returns a single-framework fixture. Both need multi-framework variants. |
| `plugins/neurawork-cc-harness/engines/stack-compiler/tests/test_selection.py:63-95` | The CLI-test precedent: `_run()` with `env = dict(os.environ, STACK_ROOT=...)`, and `_stack_dir()` which copies `payload/scripts/*.py` plus `engines/_shared` into a temp install because the script resolves `_shared` relative to its own parent. |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_hook_paths.py:58` | The same pattern with `COMPLIANCE_ROOT`, in the suite this change belongs to. |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_payload_drift.py` | Compares `payload/{scripts,hooks}` byte-for-byte against `compliance-base/`. Currently untracked — commit it with this change. |

### Existing patterns and primitives

- **Catalog partition by framework list:** `compliance-base/scripts/precheck.py:159-174` builds `filtered = {fw: all_fws[fw] for fw in frameworks if fw in all_fws}` and returns `{"frameworks": filtered}`. The new helper is this expression, split so both halves of the partition are available. `precheck` imports `stack`, so the helper must live in `stack.py` (or `utils.py`) and never in `precheck.py`.
- **Retain-rather-than-omit:** `compliance-base/scripts/stack.py:199-206` and its docstring at `:24-28` — "A capability that does not apply to the product at hand is recorded as such, with a reason — never silently omitted." The `disabled` map is the framework-level expression of the same principle.
- **Machine-owned vs decision-owned fields:** `scaffold()` recomputes `capability`, `framework`, `mandatory_linked`, `options` every run and carries the other eight. Which map an entry lands in is a machine-owned property; the eight decision fields survive the move untouched.
- **Refuse-with-a-named-cause:** every failure path in `main()` prints one line and returns 1 (`:634`, `:638`, `:660`, `:666`, `:675`). The empty-intersection guard follows that form.
- **`_write_json_atomic`:** `compliance-base/scripts/stack.py` — the only writer of `stack.json`; unchanged.

### Integration points

- `compliance-base/scripts/stack.py:636-641` — where the config read and partition are inserted.
- `compliance-base/scripts/stack.py:645-657` — the `--scaffold` reporting block, which gains the retained/restored counts.
- `compliance-base/scripts/stack.py:730-734` — the always-run `gaps()` + `render_gap_report()`, which receive the narrowed catalog.
- `stack-base/scripts/scope_lib.py:66`, `rank_lib.py:68,87`, `selection_lib.py:53`, `gate_lib.py:235,244,302`, `validate.py:96`, `precheck.py:187`, `validate.py:58` — the fifteen `choices` readers that stay unchanged **by design**. Task 2 verifies none of them reads unknown top-level keys.

## Scope

### In scope

- `stack.py` reads `config.json` and treats `frameworks` as the enabled set.
- `stack.json` gains a `disabled` map holding the retained records of switched-off frameworks; `choices` keeps its current meaning.
- Re-enabling a framework restores its decisions on the next `--scaffold`.
- An empty intersection is refused with a named cause and a non-zero exit.
- `--scaffold` and the gap report say what is retained and what was restored.
- Both copies of `stack.py` updated; regression tests in the compliance-compiler suite; VERSION and CHANGELOG.

### Not building

- No `--prune` and no change to `cap_lib.merge_preserving`: preserving unprocessed frameworks in `capabilities.json` is correct once the config is honoured downstream, and the issue explicitly rejects deleting derived frameworks.
- No warning in `stack-base/scripts/scope.py`: correct by construction once `stack.py` filters, and it would create a cross-engine config dependency.
- No change to `stack-base/scripts/gate_lib.py:135,190`, whose component index deliberately spans every catalog framework for name recognition and license checks. Ownership still comes from `stack.json.options`, so an unrecognised component degrades to `orphaned` rather than a false `on_stack`. Named in the root-cause analysis as unverified-harmless; leave it alone.
- No public LLM-free re-render entry point for `capabilities.md` (the issue's workaround step 2). A separate ergonomics gap, unaffected by this fix.
- No change to `validate_frameworks`, which stays an independent validator-only narrowing.

## Delivery Considerations

| Concern | Decision and owned work |
|---|---|
| Compatibility / migration | A `stack.json` written before this change has no `disabled` key; every read uses `.get("disabled") or {}`, so old files load unchanged. The first `--scaffold` after the change writes the key. No migration step and no schema version bump. Task 2 covers this with a test. |
| Rollout / reversibility | Behaviour changes only for a repo whose `config.json` narrows `frameworks` below what `capabilities.json` holds. In this repo both are `["gdpr","soc2","iso27001"]`, so the self-host is unaffected and the change is latent here — which also means the self-hosted `stack.json` must not change; task 6 checks that. Reverting the commit restores the old behaviour; a `stack.json` already carrying a `disabled` map is still read correctly by the old code, which ignores unknown top-level keys, but its retained entries would be invisible until re-scaffolded. |
| Observability | `--scaffold` prints the retained and restored counts and names the disabled frameworks; the gap report carries one summary line. This is what makes an unintended config narrowing visible instead of silent. |
| Documentation / communication | `compliance-base/CLAUDE.md:28` currently calls `frameworks` "what gets extracted" — corrected. `stack.py`'s module docstring documents the `disabled` map. `CHANGELOG.md` gets a dated section; `engines/compliance-compiler/VERSION` and `compliance-base/VERSION` both go 7 → 8 (`tests/test_selfhost_version.py` enforces the pair). |

## Implementation

### 1. Partition the catalog by the enabled frameworks

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/stack.py` — UPDATE, authoritative copy.
- `compliance-base/scripts/stack.py` — UPDATE, byte-identical mirror. Apply the same edit to both; `test_payload_drift.py` fails otherwise.

**Implementation**
- Add a pure helper beside the other pure logic (near `catalog_capabilities()`, `stack.py:165`), modelled on `precheck.known_capabilities`:
  `split_by_framework(catalog: dict, enabled: list[str]) -> tuple[dict, dict]` returning `({"frameworks": <enabled subset>}, {"frameworks": <the rest>})`. Preserve the catalog's other top-level keys (`generated`, `license_policy`) on the enabled half — `render_gap_report()` and `apply_selection()` read the catalog, and `stack-base` reads `license_policy` from `capabilities.json` directly, so only the `frameworks` map is partitioned. Order of `enabled` does not matter; membership does. An entry in `enabled` that the catalog does not contain is silently ignored here — task 3 owns the diagnostics.
- In `main()`, immediately after the existing non-empty guard at `:637-639`, add `cfg = load_cfg()` and compute `enabled = [fw for fw in cfg.get("frameworks") or [] if fw in catalog["frameworks"]]`. Import `load_cfg` alongside the existing names at `:76`.
- Leave `cap_hash = file_hash(CAPABILITIES_JSON)` exactly where it is: it hashes the file, not the dict, and must keep describing the file on disk so `gaps()`'s `stale` flag still means "your stack.json is behind this capabilities.json".
- Pass the enabled half to the post-run `gaps()` (`:730`) and `render_gap_report()` (`:733`), and to `apply_selection()` (`:719`). Keep the **full** catalog for the pre-scaffold `before = gaps(catalog, stack, ...)` at `:646`: `orphaned` there means "the catalog no longer describes this capability", which is a catalog-membership question, not a config one. Mislabelling a config-disabled key as orphaned is the specific mistake this split avoids.

**Tests**
- `split_by_framework` on a three-framework catalog with `enabled=["gdpr"]` returns exactly the gdpr capabilities on one side and soc2 + iso27001 on the other, with `generated` and `license_policy` preserved on the enabled half.
- An `enabled` name absent from the catalog does not appear in either half and does not raise.
- `enabled=[]` returns an empty enabled half and everything on the disabled side (the guard in task 3 is what rejects it).

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest compliance-compiler.tests.test_stack` — new helper tests pass.

### 2. Retain the disabled frameworks' decisions in stack.json

**Files and integration points**
- Both copies of `stack.py`, `scaffold()` at `:176-214` and the `--scaffold` block in `main()` at `:645-657`.

**Implementation**
- Give `scaffold()` an `enabled: list[str] | None = None` parameter. `None` means every framework in the catalog is enabled — that is today's behaviour and keeps every existing call and test valid.
- `scaffold()` receives the **full** catalog and partitions internally, so it can see both halves and nothing is lost: build the enabled frameworks' records into `choices` exactly as now, and the disabled frameworks' records into a new `disabled` map with the identical record shape.
- Read previous decisions from both maps: `prev_choices = {**(existing.get("disabled") or {}), **(existing.get("choices") or {})}`. This one line is what makes re-enabling free — a key coming back from `disabled` finds its old record and carries all eight decision fields.
- Emit `"disabled": {k: ... for k in sorted(...)}` in the returned document next to `"choices"`, sorted the same way for a stable diff. Omit the key entirely when the map is empty, so a repo with every framework enabled produces byte-identical output to today.
- A key must never appear in both maps. It cannot by construction — a capability belongs to exactly one framework and each framework lands on exactly one side — but assert it and raise `ValueError` if violated, next to the existing `duplicate capability key` raise at `:191`.
- True orphans still disappear from both maps: a capability the catalog no longer describes is not rebuilt on either side. That is today's behaviour and the issue endorses it.
- Extend the `--scaffold` output. Keep the existing `stack.json: N capabilities (M choice(s) carried, K new)` line describing `choices`, and add, only when non-empty: the number of retained entries and the disabled framework names, and the number of entries **restored** from `disabled` into `choices` this run (keys that were in `existing["disabled"]` and are now in `choices`). Keep the existing `dropped N orphaned key(s)` line, which now genuinely means orphaned.
- Extend the module docstring (`:1-65`) to document the `disabled` map, the config key that drives it, and the guarantee that a move is lossless in both directions.

**Tests**
- Scaffolding a two-framework catalog with `enabled=["gdpr"]` puts exactly the gdpr keys in `choices` and exactly the soc2 keys in `disabled`.
- A soc2 entry carrying `chosen`, `rationale`, `chosen_from`, `applicable: False`, `applicability_reason`, `scoped_from`, `ranked` and `ranked_from` keeps every one of those values verbatim after being moved to `disabled`.
- Re-scaffolding the result with `enabled=["gdpr","soc2"]` returns that entry to `choices` with all eight fields intact — the round trip is the regression proof for the operator's requirement.
- A capability removed from the catalog while its framework is disabled is dropped from `disabled`, not resurrected.
- `enabled=None` produces a document byte-identical to today's for the same input, and no `disabled` key.
- An existing `stack.json` with no `disabled` key scaffolds without error (backward compatibility).
- `machine-owned fields are refreshed for a retained entry too`: an entry in `disabled` picks up a changed `options` list from the catalog on the next scaffold, so re-enabling never returns a stale pool.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest compliance-compiler.tests.test_stack` — the existing `TestScaffold` cases still pass unchanged, proving the default path is untouched.
- `grep -rn 'get("disabled")' compliance-base/scripts stack-base/scripts` — only `stack.py` reads it; confirms no consumer had to learn the new key.

### 3. Refuse an empty enabled set instead of emptying the file

**Files and integration points**
- Both copies of `stack.py`, `main()` right after the `enabled` computation from task 1.

**Implementation**
- If `enabled` is empty, print one line naming both sides — the configured frameworks and the frameworks the catalog actually holds — and `return 1` before anything is written. Match the existing refusal wording style, e.g. `Refusing to scaffold: config frameworks [...] match nothing in capabilities.json (has: ...)`. Name `compliance-base/config.json` so the operator knows which file to edit.
- Cover the two ways to reach it: `frameworks` set to `[]`, and `frameworks` naming only frameworks absent from the catalog.
- This guard runs before every mode, not just `--scaffold`: a report run over an empty universe is equally meaningless, and `stack-base/scripts/scope.py:394-399` already refuses the same state downstream.
- Do not change the report path's exit-0 rule for any non-empty universe — an unfilled stack stays the normal starting state.

**Tests**
- `frameworks: []` exits 1, writes no `stack.json`, and names both the config path and the catalog's frameworks.
- `frameworks: ["nonexistent"]` against a gdpr catalog exits 1 with the same shape.
- A pre-existing `stack.json` is left byte-for-byte untouched by a refused run — the invariant that a failed guard writes nothing.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest compliance-compiler.tests.test_stack`

### 4. Prove the wiring end to end

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_stack.py` — UPDATE. Add a `TestScaffoldCLI` class; the file is pure-logic today and has no `main()` coverage, which is exactly how a missing `load_cfg()` call survived.

**Implementation**
- Follow `stack-compiler/tests/test_selection.py:63-95`: a `_install(tmp)` helper copying `payload/scripts/*.py` into `<tmp>/compliance-base/scripts/` and `engines/_shared` into `<tmp>/compliance-base/_shared` (excluding `tests` and `__pycache__`), because `stack.py` resolves `_shared.repo_guard` relative to its own parent. Run it with `subprocess.run([sys.executable, root/"scripts"/"stack.py", "--scaffold"], env=dict(os.environ, COMPLIANCE_ROOT=str(root)), capture_output=True, text=True, timeout=60)` — the same shape as `test_hook_paths.py:58`.
- The fixture writes `<root>/config.json`, `<root>/catalog/capabilities.json` with three frameworks, and the per-framework constraint files `gdpr.json`/`soc2.json`/`iso27001.json` that `load_constraints` needs for `mandatory_linked_keys`. Extend the existing `_capabilities()` fixture into a multi-framework variant rather than duplicating it.
- No LLM and no network: `--scaffold` is stdlib-only end to end.

**Tests**
- With `frameworks: ["gdpr"]`, `--scaffold` exits 0 and the written `stack.json` has only gdpr keys in `choices` and the other two frameworks' keys in `disabled`. **This is the test that fails today** — currently all three land in `choices`.
- Its stdout names the retained count and the disabled frameworks.
- A second run with `frameworks` widened to all three moves the entries back and reports the restored count; a decision seeded into the soc2 entry before the narrowing survives the full narrow-then-widen cycle.
- With `frameworks: []`, exit 1 and no `stack.json` written.
- With `frameworks` naming all three (this repo's own configuration), the output is what it is today — the no-op case that proves the change is latent for an unnarrowed repo.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest compliance-compiler.tests.test_stack` — including the new CLI class.

### 5. Correct the documentation the fix contradicts

**Files and integration points**
- `compliance-base/CLAUDE.md:28` — UPDATE. Says `frameworks` is "what gets extracted"; it is now the enabled set for the whole pipeline, extraction through scaffolding.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/AGENTS.md` and `compliance-base/AGENTS.md` — UPDATE only if either describes the `frameworks` key or the `stack.json` schema; check before editing, and mirror both copies if so (`test_payload_drift.py` compares `AGENTS.md`).
- Root `CLAUDE.md` — UPDATE the `compliance-base/` bullet only if it describes the `frameworks` key. It currently does not; do not touch it otherwise.

**Implementation**
- State in one sentence per surface that `config.json`'s `frameworks` selects which frameworks are in play everywhere downstream, that `capabilities.json` keeps every framework ever derived, and that `stack.json` retains a disabled framework's decisions under `disabled` so re-enabling costs nothing.
- Keep the existing distinction from `validate_frameworks` intact.
- Do not restate the schema in prose beyond that; `stack.py`'s docstring (task 2) is the schema's home.

**Tests**
- None — documentation.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests` — `test_payload_drift.py` proves the mirrored files still match.

### 6. Version, changelog and the self-host

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/compliance-compiler/VERSION` and `compliance-base/VERSION` — both 7 → 8.
- `plugins/neurawork-cc-harness/CHANGELOG.md` — new dated section.
- `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` — bump the plugin version; `engines/_shared/tests/test_manifest.py` fails a manifest version with no matching CHANGELOG section.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_payload_drift.py` and `plugins/neurawork-cc-harness/tests/test_selfhost_version.py` — currently untracked; `git add` both with this change.

**Implementation**
- Both VERSION files move together — `test_selfhost_version.py` asserts the pair, added after a release bumped only one side.
- The CHANGELOG entry names the behaviour change and the new `disabled` map, and says explicitly that no existing `stack.json` needs migrating.
- The self-hosted `compliance-base/catalog/stack.json` must not change: this repo's `config.json` enables all three frameworks, so `enabled` covers the whole catalog and the output is byte-identical. Verify with `git diff --stat compliance-base/catalog/stack.json` after running `uv run --directory compliance-base python scripts/stack.py --scaffold` — an empty diff is the check. A non-empty one means the partition is not a no-op for the unnarrowed case and task 2 is wrong.
- Do not commit a regenerated `reports/` file; that directory is gitignored.

**Tests**
- Covered by `test_selfhost_version.py`, `test_payload_drift.py` and `test_manifest.py`.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests`
- `uv run --directory compliance-base python scripts/stack.py --scaffold && git diff --stat compliance-base/catalog/stack.json` — no change to the tracked file.

## Acceptance

1. **AC1 — the config selects what is in play.** Given a `capabilities.json` holding gdpr, soc2 and iso27001 and a `config.json` with `frameworks: ["gdpr"]`, when `stack.py --scaffold` runs, then `stack.json`'s `choices` contains exactly the gdpr capability keys and no others.
2. **AC2 — switching off destroys nothing.** Given a soc2 entry carrying recorded `chosen`, `rationale`, `chosen_from`, `applicable`, `applicability_reason`, `scoped_from`, `ranked` and `ranked_from`, when soc2 is removed from `frameworks` and `--scaffold` runs, then that entry is present under `disabled` with all eight values unchanged, and `capabilities.json` is not modified.
3. **AC3 — switching back on is free.** Given that state, when soc2 is returned to `frameworks` and `--scaffold` runs, then the entry is back in `choices` with all eight decision values intact and its machine-owned fields refreshed from the current catalog — with no LLM call.
4. **AC4 — an empty selection is refused, not obeyed.** Given a `frameworks` list that intersects the catalog in nothing, when any `stack.py` mode runs, then it prints a cause naming the configured frameworks, the catalog's frameworks and `compliance-base/config.json`, exits non-zero, and leaves any existing `stack.json` byte-for-byte unchanged.
5. **AC5 — the unnarrowed case is unchanged.** Given a `config.json` whose `frameworks` covers every framework in the catalog, when `--scaffold` runs, then the written `stack.json` is byte-identical to what the current code produces and carries no `disabled` key — including this repo's own tracked `compliance-base/catalog/stack.json`.
6. **AC6 — the downstream contract is untouched.** No file under `stack-base/scripts/` changes, and `stack["choices"]` still means the working universe at all fifteen existing read sites.
7. **AC7 — both copies stay in sync.** `payload/scripts/stack.py` and `compliance-base/scripts/stack.py` remain byte-identical, and the compliance-compiler and stack-compiler VERSION files match their self-hosts.

## Validation

| Gate | Command or procedure | Proves |
|---|---|---|
| Focused behavior | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest compliance-compiler.tests.test_stack` | AC1–AC5; the CLI class proves the `main()` wiring the pure tests cannot |
| Engine suite | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests` | AC7 via `test_payload_drift.py`; no regression in the capability/precheck paths |
| Downstream engine suite | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s stack-compiler/tests` | AC6 — scope, rank, selection and the gate still pass with no change |
| Shared + plugin suites | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests` then `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | AC7 version pairing and the manifest/CHANGELOG rule |
| Remaining suites | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s knowledge-compiler/tests` and `-s claudemd-lerner/tests` | The repo's full gate per root `CLAUDE.md` |
| Lint | `cd plugins/neurawork-cc-harness/engines/compliance-compiler && uvx ruff check` | `line-length = 100` and style |
| Self-host no-op | `uv run --directory compliance-base python scripts/stack.py --scaffold && git diff --stat compliance-base/catalog/stack.json` | AC5 on the real tracked artifact — an empty diff |

## Risks and Decisions

| Decision or risk | Recommendation | Evidence / mitigation | Consequence if different |
|---|---|---|---|
| A sibling `disabled` map vs. an `enabled: false` flag inside `choices` | The sibling map | Fifteen sites across two engines read `stack["choices"]` as the working universe (`scope_lib.py:66`, `rank_lib.py:68,87`, `selection_lib.py:53`, `gate_lib.py:235,244,302`, `validate.py:96,58`, `precheck.py:187`, and six inside `stack.py`); the map leaves all of them correct, a flag needs each one to honour it | A flag is more symmetric with the existing `applicable: false` precedent, but any site that forgets it re-leaks a disabled framework into a paid pass — the bug being fixed |
| The pre-scaffold `before = gaps(...)` receives the full catalog while the post-run one receives the narrowed catalog | Keep the split | `orphaned` is `set(choices) - catalog_keys` (`stack.py:284`); narrowing that input would label every config-disabled key "orphaned" and print a dropped-keys warning for entries that were in fact retained | The `--scaffold` output would contradict what the file actually contains |
| `compliance-base/CLAUDE.md:28` calls `frameworks` "what gets extracted" | Correct the doc (task 5); the operator has confirmed the key is the enabled set | `shards.py:127`, `extract.py:214`, `capabilities.py:391` and `utils.py:108` already treat it as the enabled set | A separate `stack_frameworks` key would be a third framework key in one config; rejected by the operator |
| A stale `capabilities.json` that predates the config edit | Out of scope, already handled | `gaps()`'s `stale` flag compares the stored `capabilities_hash` against the current file hash and prints "re-run with --scaffold" (`stack.py:749-751`) | Nothing; the partition works on whatever the catalog currently holds |
| `stack-base/scripts/gate_lib.py`'s component index spans every catalog framework | Leave unchanged | Ownership comes from `stack.json.options`, so a component whose only owner is now disabled degrades to `orphaned`, and `verdict()` (`gate_lib.py:338`) fails on `off_stack` and `violations` only — never on `orphaned` | Narrowing it would need `stack-base` to read the compliance config; a separate change with its own justification |

## Agent Notes

The knowledge base has nothing on any of this — two separate `kb-researcher` passes over `knowledge-base/knowledge/` (index plus backlinks) found zero articles touching compliance-compiler or stack-compiler internals, `stack.json`, `capabilities_hash`, `merge_preserving`, or payload drift. Plan from source, not from prior sessions.

Unrelated observation from that research, worth someone's attention but not this plan's: `knowledge-base/knowledge/index.md` is dated 2026-08-27 and omits the six concept articles and one connection article compiled from `daily/2026-09-02.md`. Anything relying on the index alone currently misses them.

Two test files in the working tree are untracked and belong in this commit: `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_payload_drift.py` and `plugins/neurawork-cc-harness/tests/test_selfhost_version.py`. The first is what makes AC7 enforceable for this change.
