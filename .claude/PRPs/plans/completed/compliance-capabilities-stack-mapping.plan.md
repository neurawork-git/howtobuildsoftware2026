# Feature: Capability→stack mapping (`stack.py` + `catalog/stack.json`)

## Summary

Add the human-owned half of the capability layer: a tracked `compliance-base/catalog/stack.json` that
records, per capability, **which** component the architect actually chose, plus a **gap report** naming
every mandatory-linked capability that still has no chosen component. A single new stdlib-only script
`scripts/stack.py` does both jobs — `--scaffold` (re)generates the skeleton from `catalog/capabilities.json`
(one entry per capability, `chosen: null`, the catalog's recommended components inlined as `options`,
existing human choices preserved), and the default run computes and reports the gaps to
`reports/stack-gaps-<date>.md` plus a one-line stdout summary. It is **report-only, exit 0** — enforcement
is PRD Phase 3's job. No LLM, no SDK, no new dependency: it is pure JSON set math over an artifact that
already exists.

## User Story

As a NeuraWork engineer/architect standing up a compliant greenfield service
I want to fix one concrete component per compliance capability in a tracked file and see exactly which mandatory-linked capabilities are still unchosen
So that I can defend a stack to an auditor from the catalog instead of re-reading regulations, and know at a glance what is still undecided.

## Problem Statement

`catalog/capabilities.json` holds 68 capabilities, each carrying 2–5 *recommended* components in its
`stack` array (247 component records total). It records **options, never a decision**. Nothing in the repo
says "for `gdpr/immutable-audit-logging` we run OpenSearch", and nothing can tell you that 12 of the 62
mandatory-linked capabilities have no decision at all. Testable failure today: there is no file to read
and no command to run that answers "which compliance capabilities have we not yet picked a component for?"

## Solution Statement

One new script, `compliance-base/scripts/stack.py` (mirrored byte-identically into the plugin payload):

- **Key**: `"<framework>/<capability_slug(name)>"` — reuses `cap_lib.capability_slug` (`cap_lib.py:35-43`),
  the join key the engine already trusts. `capabilities.json` capabilities have **no `id` field**; a
  framework-prefixed slug is the stable identity.
- **`--scaffold`**: read `capabilities.json`, emit/refresh `catalog/stack.json`. Machine-owned fields
  (`capability`, `framework`, `mandatory_linked`, `options`) are recomputed every run; human-owned fields
  (`chosen`, `rationale`) are carried over by key. New capabilities appear with `chosen: null`; capabilities
  the catalog dropped are reported as orphaned, never silently deleted.
- **default run**: compute gaps — mandatory-linked capabilities with no `chosen`; plus informational lists
  (optional-only unchosen, off-catalog choices, orphaned keys, stale-scaffold warning via
  `file_hash(capabilities.json)`) — write `reports/stack-gaps-<date>.md`, print one summary line, **exit 0**.

No SDK import anywhere, so `stack.py` is directly unit-testable (unlike `capabilities.py`, which needed the
`cap_lib.py` split precisely to keep the SDK out of tests).

## Metadata

| Field            | Value                                                                            |
| ---------------- | -------------------------------------------------------------------------------- |
| Type             | NEW_CAPABILITY                                                                    |
| Complexity       | LOW–MEDIUM (pure stdlib JSON transforms; no LLM, no network, no new dependency)  |
| Systems Affected | `compliance-compiler` engine (self-host `compliance-base/` + `payload/`), tests   |
| Dependencies     | none new — stdlib `json`/`argparse`/`pathlib`; Python ≥3.12; `uv`                |
| Estimated Tasks  | 6                                                                                 |

---

## UX Design

### Before State

```
┌───────────────────────────┐
│ catalog/capabilities.json │  68 capabilities
│  cap.stack = [            │  247 component records — ALL of them RECOMMENDATIONS
│    {name: "Klaro!", …},   │
│    {name: "Orejime", …},  │  ← which one do we actually run? nothing records it
│    {name: "cookieconsent"}│
│  ]                        │
└───────────────────────────┘
             │
             ▼
   engineer reads capabilities.md (51 KB), decides in their head / in a chat
             │
             ▼
   DECISION IS NOWHERE.  Next session re-derives it.

USER_FLOW: open capabilities.md → scroll 68 sections → mentally pick → decision evaporates.
PAIN_POINT: no tracked decision record; no way to ask "what is still undecided?"
DATA_FLOW: catalog/*.json → capabilities.py → capabilities.json (+ .md) → human brain → ∅
```

### After State

```
┌───────────────────────────┐
│ catalog/capabilities.json │ (unchanged — options stay the engine's output)
└─────────────┬─────────────┘
              │  scripts/stack.py --scaffold   (pure Python, no LLM)
              ▼
┌──────────────────────────────────────────────────────────────┐
│ catalog/stack.json                            TRACKED in git │
│ { "generated": "2026-08-13",                                 │
│   "capabilities_hash": "3f9a…",   ← staleness detector       │
│   "choices": {                                               │
│     "gdpr/privacy-notice-transparency-delivery": {           │
│       "capability": "Privacy notice & transparency delivery",│  ← machine, refreshed
│       "framework": "gdpr", "mandatory_linked": true,         │  ← machine, refreshed
│       "options": ["Klaro!", "Orejime", "cookieconsent"],     │  ← machine, refreshed
│       "chosen": "Klaro!",                                    │  ← HUMAN
│       "rationale": "already self-hosted"                     │  ← HUMAN
│     }, … 68 entries …                                        │
│   } }                                                         │
└─────────────┬────────────────────────────────────────────────┘
              │  scripts/stack.py            (default run)
              ▼
   mandatory_linked ∧ chosen∈{null,""}  ─────►  ┌────────────────────────────────┐
   + off-catalog choices                        │ reports/stack-gaps-<date>.md   │ gitignored
   + orphaned keys                              └────────────────────────────────┘
   + stale-hash warning                          stdout: "Stack gaps: 12 of 62
                                                  mandatory-linked capabilities
                                                  have no chosen component"  exit 0

USER_FLOW: `--scaffold` once → edit `chosen`/`rationale` in stack.json → re-run → gap count drops to 0.
VALUE_ADD: the stack decision is a tracked, reviewable, diffable artifact; "what's left?" is one command.
DATA_FLOW: capabilities.json → stack.py --scaffold → stack.json (human edits) → stack.py → gap report.
```

### Interaction Changes

| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| `compliance-base/catalog/stack.json` | absent | tracked decision record, 68 keyed entries | Stack choice survives the session; shows up in PR diffs |
| `scripts/stack.py --scaffold` | n/a | writes/refreshes the skeleton, preserving choices | Never re-type 68 entries; new capabilities auto-appear |
| `scripts/stack.py` (default) | n/a | gap report + one stdout line, exit 0 | "What's still undecided?" answered in <1s, no LLM cost |
| `reports/stack-gaps-<date>.md` | n/a | full per-framework gap tables (gitignored) | Detail on demand without catalog churn |
| Capability renamed upstream | n/a | old key reported as `orphaned`, choice retained | Rename never silently drops a recorded decision |

---

## Mandatory Reading

**CRITICAL: the implementing agent MUST read these before starting any task.**

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `compliance-base/scripts/cap_lib.py` | 1-53, 190-236 | `capability_slug` (the join/identity key) + `_component_label`/render style to MIRROR |
| P0 | `compliance-base/scripts/capabilities.py` | 1-58, 370-400, 536-593 | Module docstring/usage block, `_write_json_atomic`, `main()` shape, repo-guard call, exit-code convention |
| P0 | `compliance-base/catalog/capabilities.json` | first ~60 | Input schema ORACLE: top-level keys + one full capability object |
| P1 | `compliance-base/scripts/utils.py` | 40-42, 47-75 | `file_hash`, `catalog_file`, `load_constraints`, `mandatory_ids` — all reused verbatim |
| P1 | `compliance-base/scripts/config.py` | 18-32, 39-53, 69-77 | `CATALOG_DIR`, `REPORTS_DIR`, `FRAMEWORK_TITLES`, `load_cfg`, `today_iso` |
| P1 | `plugins/neurawork-cc-harness/engines/_shared/repo_guard.py` | all | `assert_in_repo_not_dotclaude(target, repo_root)` + `WriteGuardError` |
| P1 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_capabilities.py` | 1-30, 60-110 | Test template: `sys.path` shim into `payload/scripts`, `tempfile` catalog fixtures |
| P2 | `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py` | 53-65 | Existence-assertion block to extend |
| P2 | `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` | 60-73 | Confirms `payload/scripts/*.py` is globbed — **no `install.py` edit needed** |
| P2 | `compliance-base/.gitignore` | all | Confirms `catalog/*.json` tracked, `reports/` gitignored |
| P2 | `.claude/PRPs/plans/completed/compliance-capabilities-engine.plan.md` | all | Phase 1 plan — the precedent this one continues |

**External Documentation:** none. This phase adds **zero** third-party surface — stdlib `json`, `argparse`,
`pathlib` only, over a JSON file the repo already produces. A web-research pass was deliberately skipped:
there is no library version to pin, no API to check, no deprecation to dodge. (PRD open question 4 —
periodic web-research refresh of *component currency* — is a separate `Could`-priority item, not Phase 2.)

---

## Patterns to Mirror

**IDENTITY / JOIN KEY — reuse, do not reinvent:**
```python
# SOURCE: compliance-base/scripts/cap_lib.py:35-43 — IMPORT THIS, don't re-implement
def capability_slug(name: str) -> str:
    """Stable join/filename key for a capability name. ..."""
    base = _SLUG_SUFFIX_RE.sub("", name.strip().lower())
    return _SLUG_NONALNUM_RE.sub("-", base).strip("-")
```

**COVERAGE / SET-MATH GATE (the shape the gap computation must mirror):**
```python
# SOURCE: compliance-base/scripts/cap_lib.py:46-53 — MIRROR THIS SHAPE
def coverage_gap(capabilities: list[dict], constraints: list[dict]) -> list[str]:
    covered = {cid for c in capabilities for cid in c.get("satisfies", [])}
    return sorted(mandatory_ids(constraints) - covered)
```

**MANDATORY-ID SOURCE:**
```python
# SOURCE: compliance-base/scripts/utils.py:73-75 — CALL THIS
def mandatory_ids(constraints: list[dict]) -> set[str]:
    """IDs of constraints flagged mandatory (default True when unspecified)."""
    return {c["id"] for c in constraints if c.get("mandatory", True)}
```

**ATOMIC JSON WRITE (exact formatting — `indent=1`, `ensure_ascii=False`, trailing newline):**
```python
# SOURCE: compliance-base/scripts/capabilities.py:370-374 — COPY VERBATIM
def _write_json_atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
```

**REPO GUARD BEFORE ANY WRITE:**
```python
# SOURCE: compliance-base/scripts/capabilities.py:393-397 — MIRROR
try:
    assert_in_repo_not_dotclaude(CATALOG_DIR, ROOT_DIR.parent)
except WriteGuardError as e:
    print(f"Refusing to write catalog: {e}")
    return 1
```

**IMPORT BLOCK + `_shared` PATH SHIM:**
```python
# SOURCE: compliance-base/scripts/capabilities.py:22-49 — MIRROR
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

import cap_lib
from config import CATALOG_DIR, FRAMEWORK_TITLES, REPORTS_DIR, ROOT_DIR, today_iso
from utils import file_hash, load_constraints, mandatory_ids

from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude

CAPABILITIES_JSON = CATALOG_DIR / "capabilities.json"
STACK_JSON = CATALOG_DIR / "stack.json"
```

**MODULE DOCSTRING WITH USAGE BLOCK:**
```python
# SOURCE: compliance-base/scripts/capabilities.py:1-20 — MIRROR the shape
"""<one-line purpose>.

<2-3 paragraphs: what it reads, what it writes, what is human-owned.>

Usage:
    uv run python scripts/stack.py --scaffold   # create/refresh catalog/stack.json
    uv run python scripts/stack.py              # report gaps (report-only, exit 0)
"""
```

**MARKDOWN RENDER (line-list + one join, framework titles from config):**
```python
# SOURCE: compliance-base/scripts/cap_lib.py:200-236 — MIRROR
lines = ["# Capability Catalog", "", f"...{catalog['generated']}...", "",
         "| Framework | Capabilities | Mandatory covered | Uncovered |",
         "|-----------|--------------|-------------------|-----------|"]
for fw, f in fws.items():
    lines.append(f"| {FRAMEWORK_TITLES.get(fw, fw)} | {f['capability_count']} | ...")
return "\n".join(lines)
```

**MAIN / CLI:**
```python
# SOURCE: compliance-base/scripts/capabilities.py:377-397, 589 — MIRROR
def main() -> int:
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("--scaffold", action="store_true", help="...")
    args = parser.parse_args()
    ...
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
```

**TEST TEMPLATE (path shim into the payload tree + temp catalog fixture):**
```python
# SOURCE: tests/test_capabilities.py:11-28 — MIRROR
SCRIPTS = Path(__file__).resolve().parent.parent / "payload" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import cap_lib  # noqa: E402

def _catalog():   # writes {"framework": "gdpr", "constraints": [{"id":…, "mandatory":…}]}
    ...           # into a tempfile.TemporaryDirectory(), passed as catalog_dir=
```

---

## Files to Change

Every `scripts/` change is applied to **BOTH** trees, byte-identical:
`plugins/neurawork-cc-harness/engines/compliance-compiler/payload/` **and** `compliance-base/`.

| File | Action | Justification |
|------|--------|---------------|
| `…/payload/scripts/stack.py` | CREATE | The whole feature: scaffold + gap report + CLI (stdlib only) |
| `compliance-base/scripts/stack.py` | CREATE | Live self-host copy (byte-identical) |
| `…/tests/test_stack.py` | CREATE | Unit tests for every pure function in `stack.py` |
| `…/tests/test_install_recon.py` | UPDATE | Assert `stack.py` lands in a fresh install |
| `compliance-base/catalog/stack.json` | CREATE (generated, Task 5) | The tracked decision record — produced by `--scaffold`, then hand-edited |

**No edits needed to**: `install.py` (globs `payload/scripts/*.py`, `install.py:60-73`), `cap_lib.py`,
`capabilities.py`, `config.py`, `utils.py`, `AGENTS.md` (no LLM prompt involved), `config.default.json`
(no new config key), `sync_catalog_seed.py` / `test_catalog_seed.py` (see NOT Building).

---

## NOT Building (Scope Limits)

- **Enforcement / non-zero exit on gaps** — explicit product decision: report-only, exit 0. An unfilled
  stack is the normal *starting* state, not a regression. Gating belongs to PRD Phase 3 (`validate.py`).
  No `--strict` flag either — YAGNI until Phase 3/4 actually needs it.
- **Seeding `stack.json` into `payload/catalog-seed/`** — component *choices* are NeuraWork-specific;
  shipping them to every install would be a false default. `SEED_FILES` in `sync_catalog_seed.py` stays at
  its six files, and `test_catalog_seed.py` needs no change. Fresh installs scaffold their own.
- **Tracked gap summary in `catalog/index.md`** — chosen against; gap state churns on every human edit and
  would pollute catalog diffs. `cap_lib.render_index` is untouched.
- **A `/co-stack` slash command, SessionStart bootstrap, `CLAUDE.md`/`docs/` updates** — PRD Phase 4.
- **Auto-picking a component** — PRD "What We're NOT Building"; the engine only lists options.
- **YAML / repo-root stack file** — rejected: needs a non-stdlib parser, breaking the stdlib-only rule.
- **Editing `capabilities.json`** — stack choices live in a separate file so a capability re-derivation
  (`capabilities.py --all`) can never clobber a human decision.
- **LLM/SDK involvement of any kind** — the whole phase is deterministic set math.

---

## Step-by-Step Tasks

Execute in order. Every `scripts/` file must be written to **both** trees; Level 4 diffs them.

### Task 1: CREATE `scripts/stack.py` — pure logic half (both trees)

- **ACTION**: CREATE the module with its docstring/usage block and all SDK-free helper functions.
- **IMPLEMENT** (all take explicit optional `catalog_dir` so tests never touch the real catalog — mirror
  `cap_lib.assemble_catalog(…, catalog_dir=None, …)` at `cap_lib.py:56-61`):
  - `capability_key(framework: str, name: str) -> str` → `f"{framework}/{cap_lib.capability_slug(name)}"`.
  - `mandatory_linked_keys(catalog: dict, catalog_dir=None) -> set[str]` — for each framework, load its
    constraints (`load_constraints([fw], catalog_dir)`), take `mandatory_ids(...)`, and include a
    capability's key iff `set(cap["satisfies"]) & mand` is non-empty.
  - `component_options(cap: dict) -> list[str]` → `[c["name"] for c in cap.get("stack", []) if c.get("name")]`,
    order preserved, duplicates dropped (first wins).
  - `scaffold(catalog: dict, existing: dict | None, catalog_dir=None, generated=None) -> dict` — build
    `{"generated", "source", "capabilities_generated", "capabilities_hash", "choices": {...}}`; one entry
    per capability keyed by `capability_key`, sorted by key for stable diffs. Machine fields
    (`capability`, `framework`, `mandatory_linked`, `options`) always recomputed; human fields
    (`chosen`, `rationale`) copied from `existing["choices"][key]` when present, else `None` / `""`.
    Keys present in `existing` but absent from the catalog are **not** carried into the output (they are
    surfaced by `gaps()` as `orphaned` from the on-disk file — never silently deleted before the human sees
    the report; see Task 2's ordering note).
  - `gaps(catalog: dict, stack: dict, catalog_dir=None) -> dict` returning
    `{"mandatory_total", "mandatory_unchosen": [key…], "optional_unchosen": [key…],
      "off_catalog": [{"key","chosen","options"}…], "orphaned": [key…], "stale": bool}`.
    - `mandatory_unchosen`: key is mandatory-linked **and** its `chosen` is `None`/`""`/whitespace.
    - `off_catalog`: `chosen` set but not in `options` — **informational only**, never an error (a human
      may deliberately pick something the catalog did not list).
    - `orphaned`: keys in `stack["choices"]` with no matching capability in `catalog`.
    - `stale`: `stack.get("capabilities_hash")` differs from the current `capabilities.json` hash.
  - `render_gap_report(catalog: dict, stack: dict, result: dict, generated: str) -> str` — markdown:
    H1 + generated line; a summary table
    `| Framework | Capabilities | Mandatory-linked | Chosen | Unchosen |`; then per-framework
    `### <FRAMEWORK_TITLES[fw]>` sections listing each unchosen mandatory-linked capability as
    `- **<capability>** (`<key>`) — options: a; b; c`; then `## Informational` subsections for
    optional-unchosen, off-catalog, orphaned; a stale-scaffold warning line when `result["stale"]`.
- **MIRROR**: `cap_lib.py:35-53` (slug + set math), `cap_lib.py:200-236` (line-list markdown render),
  `capabilities.py:1-20` (docstring/usage block).
- **CONSTRAINT**: no `claude_agent_sdk` import, no network. Import `cap_lib` for `capability_slug` only.
- **GOTCHA — do NOT filter components by `verdict`**: `stack[].verdict` takes the values
  `keep` (89), `replaced` (113), `keep-exception` (45). `replaced` does **not** mean "rejected" — it means
  *this listed component replaced the one named in `replaced_from`* during the license audit. Every entry in
  `cap["stack"]` is a live recommendation. Filtering on `verdict` would strip the majority of options and
  leave 4 capabilities (`gdpr/DPIA & prior consultation workflow`,
  `gdpr/Processor & joint-controller contracting`, `gdpr/Special-category & children's data protection`,
  `soc2/Control environment: governance, ethics & personnel`) with zero options.
- **GOTCHA**: capabilities have **no `id` field** — the framework-prefixed slug IS the identity. Never
  index by list position.
- **GOTCHA**: `capability_slug` strips a trailing ` (...)`/` — …`/` - …` clause (`cap_lib.py:31`), so
  `"Control environment: governance, ethics & personnel"` keeps its colon but a parenthetical suffix is
  dropped — two capabilities in the same framework could collide on slug. Detect a duplicate key during
  `scaffold` and raise `ValueError(f"duplicate capability key: {key}")` rather than silently overwriting.
- **APPLY TO**: `…/payload/scripts/stack.py` and `compliance-base/scripts/stack.py` (byte-identical).
- **VALIDATE**:
  ```bash
  cd /home/felix/projects/howtobuildsoftware2026
  diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/stack.py compliance-base/scripts/stack.py
  python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import stack; print(stack.capability_key('gdpr','Privacy notice & transparency delivery'))"
  uvx ruff check compliance-base/scripts/stack.py
  ```
  **EXPECT**: no diff output; prints `gdpr/privacy-notice-transparency-delivery`; ruff clean.

### Task 2: ADD the CLI half to `scripts/stack.py` (both trees)

- **ACTION**: Add `_load_json`, `_write_json_atomic`, and `main()`.
- **IMPLEMENT**:
  - `_write_json_atomic(path, obj)` — **copy verbatim** from `capabilities.py:370-374` (`indent=1`,
    `ensure_ascii=False`, trailing newline, `tmp.replace(path)`).
  - `_load_json(path) -> dict` — return `{}` on missing/corrupt, mirroring `utils.load_state`'s
    never-raises posture (`utils.py:22-29`).
  - `main() -> int`:
    1. `argparse` with a single `--scaffold` flag (description mirrors `capabilities.py:377-386`).
    2. Repo guard: `assert_in_repo_not_dotclaude(CATALOG_DIR, ROOT_DIR.parent)` → on `WriteGuardError`
       print `f"Refusing to write catalog: {e}"`, return 1 (`capabilities.py:393-397`).
    3. Load `capabilities.json`. If absent/empty → print
       `"No capabilities.json — run scripts/capabilities.py first"`, return 1.
    4. Load existing `stack.json` (may be `{}`).
    5. `--scaffold`: compute `result = gaps(catalog, existing)` **before** rewriting so orphaned keys can be
       printed; `new = scaffold(catalog, existing, generated=today_iso())`; `_write_json_atomic(STACK_JSON, new)`;
       print `f"stack.json: {len(new['choices'])} capabilities ({carried} choices carried, {added} new)"`
       and, if `result["orphaned"]`, `f"  dropped {n} orphaned key(s): …"`. Then fall through to reporting
       against the freshly-written file.
    6. Default (and post-scaffold): `result = gaps(catalog, stack)`;
       `REPORTS_DIR.mkdir(parents=True, exist_ok=True)`;
       write `REPORTS_DIR / f"stack-gaps-{today_iso()}.md"` with `render_gap_report(...)`.
    7. stdout: `f"Stack gaps: {len(result['mandatory_unchosen'])} of {result['mandatory_total']} mandatory-linked capabilities have no chosen component"`,
       then `f"report: {report_path}"`; when `result["stale"]`, also print
       `"! stack.json was scaffolded against an older capabilities.json — re-run with --scaffold"`.
    8. `return 0` — **always**, unless step 2/3 failed. Gaps are never fatal.
  - `if __name__ == "__main__": raise SystemExit(main())`.
- **MIRROR**: `capabilities.py:377-397` (arg parse + guard), `capabilities.py:370-374` (atomic write).
- **GOTCHA**: `REPORTS_DIR` is gitignored (`compliance-base/.gitignore:4`) but may not exist in a fresh
  install — `mkdir(parents=True, exist_ok=True)` before writing.
- **GOTCHA**: `catalog/stack.json` is **tracked** (`.gitignore` excludes only `catalog/.shards/`) — that is
  intended; the decision record belongs in git.
- **APPLY TO**: both trees.
- **VALIDATE**:
  ```bash
  cd /home/felix/projects/howtobuildsoftware2026
  diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/stack.py compliance-base/scripts/stack.py
  uv run --directory compliance-base python scripts/stack.py --help
  uvx ruff check compliance-base/scripts/stack.py
  ```
  **EXPECT**: no diff; `--help` shows only `--scaffold`; ruff clean (line-length 100).

### Task 3: CREATE `tests/test_stack.py` — pure-logic unit tests

- **ACTION**: CREATE `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_stack.py`.
- **IMPLEMENT** (mirror the shim + fixture style of `test_capabilities.py:11-28`; import `stack` from
  `payload/scripts`; build a temp `catalog/` dir with a fabricated `gdpr.json` and pass it as `catalog_dir=`):
  - `test_capability_key` — `('gdpr', 'Audit logging (SOC2 CC7)')` → `gdpr/audit-logging`.
  - `test_mandatory_linked_only` — a capability satisfying only a `mandatory: false` constraint is **not**
    mandatory-linked; one satisfying a mandatory constraint is.
  - `test_component_options_preserves_order_and_verdict` — a `stack` list containing a `verdict: "replaced"`
    entry still yields that component in `options` (regression guard for the Task 1 gotcha).
  - `test_scaffold_fresh` — `existing=None` → every capability present, `chosen is None`, `rationale == ""`,
    keys sorted.
  - `test_scaffold_preserves_human_fields` — an existing entry with `chosen`/`rationale` keeps both while
    `options`/`mandatory_linked` are recomputed from the (changed) catalog.
  - `test_scaffold_adds_new_capability` — a capability absent from `existing` appears with `chosen: None`.
  - `test_scaffold_duplicate_key_raises` — two capabilities in one framework colliding on slug →
    `ValueError`.
  - `test_gaps_counts_only_mandatory_linked` — an unchosen optional-only capability lands in
    `optional_unchosen`, not `mandatory_unchosen`.
  - `test_gaps_blank_chosen_counts_as_unchosen` — `""` and `"   "` count as unchosen.
  - `test_gaps_off_catalog_choice` — `chosen` not in `options` → listed in `off_catalog`, still counts as
    chosen (absent from `mandatory_unchosen`).
  - `test_gaps_orphaned_key` — a `choices` key with no matching capability → `orphaned`.
  - `test_gaps_stale_hash` — mismatched `capabilities_hash` → `stale is True`.
  - `test_render_gap_report` — output contains the summary-table header and the key of an unchosen
    mandatory-linked capability.
- **MIRROR**: `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_capabilities.py`.
- **CONSTRAINT**: plain `unittest`, no network, no SDK, no writes outside `tempfile`.
- **VALIDATE**:
  ```bash
  cd /home/felix/projects/howtobuildsoftware2026/plugins/neurawork-cc-harness/engines
  python3 -m unittest discover -s compliance-compiler/tests -p 'test_stack.py'
  ```
  **EXPECT**: all tests pass, exit 0.

### Task 4: UPDATE `tests/test_install_recon.py` — assert `stack.py` ships

- **ACTION**: In the fresh-scaffold test, add an existence assertion beside the existing `scripts/*.py`
  checks (`test_install_recon.py:53-65`).
- **IMPLEMENT**:
  ```python
  self.assertTrue((cb / "scripts" / "stack.py").exists())
  ```
- **MIRROR**: the adjacent `capabilities.py` / `cap_lib.py` assertions in the same test.
- **VALIDATE**:
  ```bash
  cd /home/felix/projects/howtobuildsoftware2026/plugins/neurawork-cc-harness/engines
  python3 -m unittest discover -s compliance-compiler/tests -p 'test_install_recon.py'
  ```
  **EXPECT**: passes — `install.py` already globs `payload/scripts/*.py`, so no `install.py` edit.

### Task 5: GENERATE `compliance-base/catalog/stack.json` (first real scaffold)

- **ACTION**: Run the scaffold against the live 68-capability catalog and commit the result.
- **IMPLEMENT**:
  ```bash
  cd /home/felix/projects/howtobuildsoftware2026
  uv run --directory compliance-base python scripts/stack.py --scaffold
  ```
- **VALIDATE**:
  ```bash
  python3 - <<'EOF'
  import json
  s = json.load(open('compliance-base/catalog/stack.json'))
  ch = s["choices"]
  ml = [k for k, v in ch.items() if v["mandatory_linked"]]
  print(len(ch), "entries;", len(ml), "mandatory-linked;",
        sum(1 for v in ch.values() if not v["options"]), "with no options")
  assert len(ch) == 68, len(ch)
  assert len(ml) == 62, len(ml)              # gdpr 25 + soc2 21 + iso27001 16
  assert list(ch) == sorted(ch)              # stable, sorted keys
  assert all(v["chosen"] is None for v in ch.values())
  EOF
  uv run --directory compliance-base python scripts/stack.py
  ```
  **EXPECT**: assertions pass (68 entries / 62 mandatory-linked / 0 with no options); the second command
  prints `Stack gaps: 62 of 62 mandatory-linked capabilities have no chosen component` and exits 0.

### Task 6: Idempotency + choice-preservation proof (manual, no LLM)

- **ACTION**: Prove re-scaffold is byte-stable and never eats a human decision.
- **VALIDATE**:
  ```bash
  cd /home/felix/projects/howtobuildsoftware2026
  cp compliance-base/catalog/stack.json /tmp/stack-before.json
  uv run --directory compliance-base python scripts/stack.py --scaffold
  diff -q /tmp/stack-before.json compliance-base/catalog/stack.json && echo "IDEMPOTENT"

  # hand-edit one choice, re-scaffold, confirm it survives
  python3 - <<'EOF'
  import json, pathlib
  p = pathlib.Path('compliance-base/catalog/stack.json')
  d = json.loads(p.read_text())
  k = next(k for k, v in d["choices"].items() if v["mandatory_linked"] and v["options"])
  d["choices"][k]["chosen"] = d["choices"][k]["options"][0]
  d["choices"][k]["rationale"] = "smoke test"
  p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
  print("set", k, "->", d["choices"][k]["chosen"])
  EOF
  uv run --directory compliance-base python scripts/stack.py --scaffold
  uv run --directory compliance-base python scripts/stack.py
  ```
  **EXPECT**: `IDEMPOTENT` on the unchanged re-run (only `generated` may differ if the date rolls — if so,
  the diff must show **only** that line); after the edit + re-scaffold the choice and rationale are intact
  and the gap line reads `61 of 62`. Revert the smoke-test edit afterwards.

---

## Testing Strategy

### Unit Tests to Write

| Test File | Test Cases | Validates |
|-----------|------------|-----------|
| `tests/test_stack.py` | key derivation; mandatory-linked detection; option extraction incl. `verdict: replaced`; scaffold fresh / preserve / add / duplicate-key; gaps mandatory-vs-optional, blank-chosen, off-catalog, orphaned, stale; report render | every pure function in `stack.py` |
| `tests/test_install_recon.py` (extend) | `stack.py` exists after install | payload→target copy |

### Edge Cases Checklist

- [ ] `capabilities.json` missing → clear message, exit 1, no traceback
- [ ] `stack.json` missing on a default (non-scaffold) run → treated as all-unchosen, still exits 0
- [ ] `stack.json` corrupt JSON → treated as `{}` (never raises), scaffold rebuilds it
- [ ] `chosen: ""` / `"   "` counts as unchosen
- [ ] `chosen` not among `options` → `off_catalog`, still counts as a decision, never fatal
- [ ] Capability renamed upstream → old key `orphaned` and reported, new key added `chosen: null`
- [ ] Two capabilities in one framework colliding on slug → `ValueError`, not a silent overwrite
- [ ] Component with `verdict: "replaced"` still appears in `options`
- [ ] Capability with an empty `stack` array → `options: []`, still listed if mandatory-linked
- [ ] Re-scaffold with no catalog change → byte-identical output
- [ ] Stale `capabilities_hash` → warning printed, run still exits 0
- [ ] `reports/` absent → created before writing

---

## Validation Commands

### Level 1: STATIC_ANALYSIS
```bash
cd /home/felix/projects/howtobuildsoftware2026
uvx ruff check
python3 -c "import sys; sys.path.insert(0,'compliance-base/scripts'); import stack"
```
**EXPECT**: exit 0, no errors (line-length 100).

### Level 2: UNIT_TESTS
```bash
cd /home/felix/projects/howtobuildsoftware2026/plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: all pass (new `test_stack.py` + the four existing files).

### Level 3: FULL_SUITE (no regressions in sibling engines)
```bash
cd /home/felix/projects/howtobuildsoftware2026/plugins/neurawork-cc-harness/engines
python3 -m unittest discover -s _shared/tests
python3 -m unittest discover -s knowledge-compiler/tests
python3 -m unittest discover -s claudemd-lerner/tests
python3 -m unittest discover -s compliance-compiler/tests
```
**EXPECT**: all pass.

### Level 4: TREE PARITY
```bash
cd /home/felix/projects/howtobuildsoftware2026
diff -q plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/stack.py \
        compliance-base/scripts/stack.py || echo "DRIFT: stack.py"
python3 plugins/neurawork-cc-harness/engines/compliance-compiler/sync_catalog_seed.py --check
```
**EXPECT**: no `DRIFT` line; seed check still exits 0 (`stack.json` is deliberately not a seed file).

### Level 5: END-TO-END (no LLM, no network)
```bash
cd /home/felix/projects/howtobuildsoftware2026
uv run --directory compliance-base python scripts/stack.py --scaffold
uv run --directory compliance-base python scripts/stack.py
echo "exit=$?"
```
**EXPECT**: 68 entries written; gap line printed; `exit=0`; report file exists under
`compliance-base/reports/stack-gaps-<date>.md`.

### Level 6: MANUAL_VALIDATION
Task 6 — idempotent re-scaffold + human-choice preservation. Then confirm git sees exactly one new tracked
file (`compliance-base/catalog/stack.json`) and nothing under `reports/`:
```bash
cd /home/felix/projects/howtobuildsoftware2026 && git status --porcelain
```

---

## Acceptance Criteria

- [ ] `scripts/stack.py` exists in both trees, byte-identical (Level 4 clean)
- [ ] `--scaffold` produces 68 entries / 62 mandatory-linked, keys sorted, all `chosen: null`
- [ ] Default run writes `reports/stack-gaps-<date>.md`, prints the one-line summary, **exits 0**
- [ ] Re-scaffold is byte-idempotent and preserves every `chosen`/`rationale`
- [ ] Components with `verdict: "replaced"` appear in `options` (no capability left with 0 options)
- [ ] Orphaned keys are reported, never silently dropped without a report line
- [ ] Levels 1–5 pass; no regressions in the other three engines
- [ ] No new dependency, no new config key, no `AGENTS.md`/`install.py`/`cap_lib.py` edit
- [ ] `catalog/stack.json` is tracked; the gap report is not

## Completion Checklist

- [ ] Tasks 1–6 executed in order, each validated immediately
- [ ] Level 1 static analysis passes
- [ ] Level 2 unit tests pass
- [ ] Level 3 full suite passes (all four engines)
- [ ] Level 4 tree parity clean + seed check clean
- [ ] Level 5 end-to-end clean, exit 0
- [ ] Level 6 manual idempotency/preservation proof done, smoke-test edit reverted

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Filtering options on `verdict` strips most components | MED | HIGH | Explicit Task-1 gotcha + `test_component_options_preserves_order_and_verdict` regression test |
| Re-scaffold eats a human `chosen` | LOW | HIGH | Human fields carried by key; `test_scaffold_preserves_human_fields` + Task 6 manual proof |
| Capability rename silently drops a decision | MED | MED | Old key reported as `orphaned` before the rewrite; never removed without a report line |
| Payload/self-host drift (one tree edited) | MED | MED | Level 4 diff gate; every task says "both trees" |
| Slug collision overwrites an entry | LOW | MED | `scaffold` raises `ValueError` on a duplicate key (unit-tested) |
| `stack.json` scaffolded against a stale catalog | MED | LOW | `capabilities_hash` stamp + `stale` warning on every run |
| Scope creep into enforcement | MED | LOW | Report-only, exit 0, no `--strict`; enforcement explicitly deferred to Phase 3 |

---

## Compliance

**Scope**: an internal, design-time batch tool — a stdlib Python script reading two local JSON files and
writing a third plus a local markdown report. It processes no personal data, exposes no interface, and
changes no runtime data flow, so the substantive runtime obligations of GDPR / SOC 2 / ISO 27001 do not
apply at this plan's scope.

**Relationship to the catalog is supportive, not substitutive**: Phase 1's deterministic gate
(`cap_lib.coverage_gap`) already guarantees all 279 mandatory constraints map to a capability
(GDPR 109/109, SOC 2 111/111, ISO 27001 59/59). This phase adds the *decision* layer on top and computes a
second, independent gap — the 62 mandatory-linked capabilities with no chosen component — so a mandatory
constraint can no longer be "covered" by a capability nobody ever decided to build. It weakens no existing
check: `capabilities.json` is read-only to `stack.py`.

**Self-application**: all output stays inside the repo, never under `.claude/` — enforced by
`repo_guard.assert_in_repo_not_dotclaude` before any write (Task 2), matching the ISO-style records
governance the catalog itself encodes.

## Notes

- **Why one file, not a `stack_lib.py` + `stack.py` split**: the `cap_lib`/`capabilities` split exists
  solely to keep `claude_agent_sdk` out of the unit tests. `stack.py` imports no SDK, so tests import it
  directly and a second module would be an abstraction with one caller — against CLAUDE.md's
  "no abstractions for single-use code".
- **Why `"<framework>/<slug>"` as the key**: `capabilities.json` capabilities carry no `id`; the framework
  prefix is required because the catalog is deliberately per-framework with overlap kept (the same
  capability name legitimately appears under GDPR and SOC 2 and must stay independently choosable).
- **Why `options` is duplicated into `stack.json`**: hand-editing is the primary interaction — the human
  needs the menu next to the field they are filling. It is machine-owned and refreshed on every
  `--scaffold`, so it cannot drift; only `chosen`/`rationale` are human-authored.
- **Why report-only**: an empty stack file is the correct day-one state. A command that is red from the
  first run trains people to ignore it. Phase 3 adds the enforcing gate where enforcement belongs — at
  plan-write time.
- **`verdict` semantics** (verified against the live catalog, 247 component records): `keep` 89,
  `replaced` 113, `keep-exception` 45. `replaced` marks a component that *superseded* the one named in
  `replaced_from` during the ultracode license audit — all three verdicts denote current, valid options.
- **Confidence**: 9/10 — no LLM, no network, no new dependency; every pattern (slug join, set-math gate,
  atomic write, repo guard, test shim) is copied from code already shipped in this engine, and the only
  genuinely new logic is a dict merge and a markdown renderer, both fully unit-tested. The point deducted
  is the `verdict`-filter trap, which is the one place a reasonable implementer could silently go wrong.
