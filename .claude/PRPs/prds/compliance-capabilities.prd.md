# Compliance Capabilities

> Turn the tracked compliance **constraint** catalog (GDPR / SOC 2 / ISO 27001) into per-framework **capabilities** — concrete technical building blocks — and map each capability onto a greenfield 2026 software stack, so "what must we build to be compliant?" is answered from the catalog instead of re-read from raw regulation text.

## Problem Statement

`compliance-base/` holds 359 machine-checkable constraints (127 GDPR / 160 SOC 2 / 72 ISO 27001, 279 mandatory), and `validate.py` checks a PRP plan against them. But a constraint is a *requirement to prove* ("maintain an asset inventory with a named owner"), not a *thing to build*. To choose a stack, an engineer must re-read hundreds of overlapping constraints and infer the handful of systems that actually satisfy them. That inference is done ad-hoc, un-tracked, and re-done every time the stack is discussed — the exact re-explanation / drift problem the harness exists to kill, one layer up from code.

## Evidence

- **Direct user statement (this session):** "aus den Constraints der Compliance-Aufforderungen unsere Capabilities bauen" and bring them "zu meinem Software-Stack, den ich hier festlegen möchte." The stack is explicitly *to be defined from* the constraints.
- **Structural evidence:** the 359 constraints collapse hard. An ultracode extraction run (83 agents, this session) distilled them to **68 capabilities** (25 GDPR / 25 SOC 2 / 18 ISO) — a ~5× compression — proving many constraints share one building block (one "immutable audit logging" capability answers dozens of controls).
- **Coverage proof:** an adversarial verify pass confirmed **100% of mandatory constraints are covered** by the derived capabilities (GDPR 109/109, SOC 2 111/111, ISO 59/59, 0 uncovered) — the capability layer loses nothing.
- **Deferred-scope pointer:** the harness PRD (`neurawork-cc-harness.prd.md`, "What We're NOT Building") explicitly parked the **Compliance Validator** for a later session. `compliance-compiler` shipped the constraint half; this PRD is the capability half.

## Proposed Solution

Add a **capability layer** to `compliance-base`: a repeatable engine that reads `catalog/*.json` (constraints) and emits `catalog/capabilities.json` + `capabilities.md` — per-framework capability lists (overlap kept, so each framework stays independently auditable), each capability carrying (a) the constraint ids it satisfies and (b) recommended greenfield-2026 stack components. A coverage gate fails the build if any *mandatory* constraint is orphaned by no capability. Later, `validate.py` is extended so a plan/stack declares which capabilities it delivers and is gated on mandatory-capability coverage.

The v1 catalog **already exists** — produced this session by the `compliance-capabilities` ultracode workflow (extract → merge → stack → verify). This PRD's remaining work is to make that one-off run a **repeatable, idempotent engine** and wire it into the existing hook/command surface, mirroring `extract.py`'s parallel-SDK-agent pattern.

Chosen over: (a) hand-authoring capabilities — doesn't scale, drifts from the catalog; (b) cross-framework unified dedup — rejected by the user because SOC 2 / ISO / GDPR are audited *separately*, so a per-framework list is what an auditor consumes.

## Key Hypothesis

We believe a **catalog-derived, coverage-verified capability layer that maps compliance constraints to concrete greenfield-2026 stack components** will let NeuraWork **choose and defend a compliant stack directly from the tracked catalog** instead of re-reading raw regulation.
We'll know we're right when a stack decision cites `capabilities.json`, every mandatory constraint traces to a capability and a chosen component, and re-running the engine after a catalog change surfaces exactly the newly-uncovered constraints.

## What We're NOT Building

- **Cross-framework unified capabilities** — user chose per-framework lists; overlap is kept on purpose (separate audits).
- **Actual implementation of the stack components** — this defines *which* capabilities/components; building the audit-log store, IAM, etc. is downstream product work, not this engine.
- **Runtime/continuous compliance monitoring** (evidence collection, control testing) — out of scope; this is a design-time derivation layer.
- **New frameworks** (HIPAA, PCI-DSS, …) — v1 is the three already in the catalog.
- **Auto-picking one component** — the engine *recommends* 2-4 options per capability; the human fixes the choice in the stack file.

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Mandatory constraint coverage | 100% of mandatory constraints map to ≥1 capability | verify pass in the engine (currently 279/279) |
| Constraint→capability compression | ≥3× fewer capabilities than constraints | count (currently 359→68 ≈ 5.3×) |
| Capability→component gap | Every mandatory-linked capability has ≥1 chosen component in the stack file | stack-mapping gap report |
| Re-run idempotency | No-catalog-change re-run produces byte-identical catalog | diff on re-run |
| Validator enforcement | A plan omitting a mandatory capability fails `validate.py` | test with a deliberately-incomplete plan |

## Open Questions

- [x] **Stack file format & location** — resolved 2026-08-13: `compliance-base/catalog/stack.json` (tracked JSON, stdlib-parseable, owned by `compliance-base`), scaffolded by `scripts/stack.py --scaffold` with `chosen`/`rationale` human-owned; gap report is report-only (exit 0) into gitignored `reports/`.
- [ ] Should the capability engine be **deterministic-idempotent** like `compile.py` (skip if catalog unchanged) or always re-run? LLM extraction is non-deterministic — likely need a content hash + pinned output, human-reviewed.
- [x] Does `validate.py` gate on **capabilities** (coarse) or stay on **constraints** (fine), or both layers? — resolved 2026-08-13: **both, split by document type.** A **PRD** is checked at capability/component level (it never carries constraint IDs); a **plan** additionally at constraint level, as today. Component-allowlist and license checks live in the separate `st-` hook — see [`stack-compiler.prd.md`](stack-compiler.prd.md). Extending the `co-` hook from plans to PRDs is `neurawork-cc-harness.prd.md` Phase 7.
- [ ] Greenfield stack recs came from model knowledge (Jan 2026 cutoff), not live research on every capability — do we want a periodic web-research refresh of component currency?

---

## Users & Context

**Primary User**
- **Who**: NeuraWork engineer/architect standing up a new (greenfield) service that must pass SOC 2 / ISO 27001 and satisfy GDPR.
- **Current behavior**: reads regulation summaries + the constraint catalog, mentally clusters them, guesses a stack, hopes nothing is missed.
- **Trigger**: "we're building X and it must be compliant — what do we actually need to build/buy?"
- **Success state**: opens `capabilities.md`, sees the 25/25/18 capabilities, the constraints each covers, and 2-4 stack options each; fixes choices in the stack file; validator confirms nothing mandatory is uncovered.

**Job to Be Done**
When starting a compliant greenfield build, I want to see the concrete capabilities and stack components my compliance obligations require, so I can choose a stack I can defend to an auditor without re-reading the regulations.

**Non-Users**
Auditors (they consume evidence, not this design artifact) and teams on already-fixed legacy stacks (they'd use gap-analysis mode, not greenfield derivation) — not the v1 target.

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | Repeatable capability-extraction engine (`capabilities.py`) | The one-off workflow must become a tracked, re-runnable script |
| Must | Mandatory-coverage verify gate | Guarantees the capability layer never silently drops a mandatory constraint |
| Must | `capabilities.json` + `capabilities.md` outputs | The consumable per-framework catalog (already produced v1) |
| Should | Capability→stack mapping file + gap report | Lets the human fix component choices and see uncovered capabilities |
| Should | `validate.py` capability-coverage check | Enforces capability completeness on plan writes |
| Could | `/co-capabilities` slash command (bootstrap comes from the shipped catalog seed, not a SessionStart hook) | Parity with `co-extract`/`co-validate` ergonomics |
| Could | Periodic web-research refresh of 2026 component currency | Keeps stack recs from going stale |
| Won't | Cross-framework unified capabilities | User chose per-framework |
| Won't | Building the actual components / runtime monitoring | Downstream, out of scope |

### MVP Scope

The **catalog already shipped this session** (`catalog/capabilities.json`, `capabilities.md`, index updated). MVP to *close* = Phase 1: wrap the extraction as `capabilities.py` with the coverage gate, so the artifact is reproducible rather than a one-off. Everything past that (stack file, validator) is incremental.

### User Flow

`catalog/*.json` → `capabilities.py` (parallel SDK agents: cluster → merge → map → verify) → `capabilities.json` + `.md` → engineer reads, fixes stack choices → `validate.py` gates a plan on mandatory-capability coverage.

---

## Technical Approach

**Feasibility**: **HIGH** — the extraction already ran end-to-end (83 agents, 0 errors, 100% coverage). `compliance-base` already runs ~30 parallel SDK agents in `extract.py` (`asyncio.gather` + semaphore); `capabilities.py` reuses that exact machinery with a different prompt and a verify stage.

**Architecture Notes**
- Reuse `extract.py`'s parallel-agent + `_shared` scaffolding; new output is `catalog/capabilities.json`, `catalog/.shards/` gitignored as today.
- Output stays **inside the repo, never under `.claude/`** — enforced by `_shared/repo_guard.py`.
- Extraction is non-deterministic (LLM) → pin output + content-hash the source constraints; re-run only on catalog change, human-review the diff (mirrors how `compile.py` is idempotent on already-processed logs).
- Coexists with the other engines via the `co-` hook prefix already in use.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM drops a mandatory constraint from every capability | M | Verify stage already gates on it; fail the run if uncovered_ids ≠ ∅ |
| Non-deterministic re-runs churn the tracked catalog | H | Content-hash source; skip unchanged; human-review diffs |
| Stack recs go stale (Jan-2026 model knowledge) | M | Optional web-research refresh (Could); date-stamp recs |
| Name drift between merge and stack stages breaks joins | M (seen this session) | Join on normalized prefix, not exact string — already fixed in the assembly step |

---

## Implementation Phases

<!--
  STATUS: pending | in-progress | complete
  PARALLEL: phases that can run concurrently (e.g., "with 3" or "-")
  DEPENDS: phases that must complete first (e.g., "1, 2" or "-")
  PRP: link to generated plan file once created
-->

| # | Phase | Description | Status | Parallel | Depends | Plan | Report | PR |
|---|-------|-------------|--------|----------|---------|------|--------|----|
| 0 | Bootstrap catalog | v1 `capabilities.json`+`.md` produced via ultracode; index updated | complete | - | - | - | - | - |
| 1 | Extraction engine | Wrap the workflow as reproducible `capabilities.py` with coverage-verify gate | complete | - | 0 | [engine plan](../plans/completed/compliance-capabilities-engine.plan.md) | - | - |
| 2 | Stack mapping | Capability→chosen-component file + uncovered-capability gap report. **Owns the `stack.json` schema** — the product-scoping, ranking and selection layer that fills it lives in [`stack-compiler.prd.md`](stack-compiler.prd.md) and writes through this script | complete | with 3 | 1 | [stack mapping plan](../plans/completed/compliance-capabilities-stack-mapping.plan.md) | - | - |
| 3 | Capability validator | Extend `validate.py`: documents declare capabilities, gate on mandatory coverage. Stays here (capability level); the component-allowlist gate is `stack-compiler` Phase 4 | complete | with 2 | 1 | [validator plan](/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/completed/compliance-capability-validator.plan.md) | [report](/home/felix/.prp/howtobuildsoftware2026-35325a96/reports/compliance-capability-validator-report.md) | [#24](https://github.com/neurawork-git/howtobuildsoftware2026/pull/24) |
| 4 | Wire & document | `/co-capabilities` command, hook nudge when the layer is absent, docs/CLAUDE.md (SessionStart bootstrap superseded by the shipped catalog seed) | in-progress | - | 2, 3 | [wire & document plan](/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/compliance-capabilities-wire-document.plan.md) | - | - |

### Phase Details

**Phase 0: Bootstrap catalog** *(complete)*
- **Goal**: Produce the first capability catalog so the design is grounded in real data.
- **Scope**: `catalog/capabilities.json` (68 caps, per-framework, satisfies + stack), `catalog/capabilities.md`, `catalog/index.md` capabilities section.
- **Success signal**: 100% mandatory coverage verified (279/279); done this session.

**Phase 1: Extraction engine**
- **Goal**: Make the one-off workflow a tracked, re-runnable script.
- **Scope**: `compliance-base/scripts/capabilities.py` reusing `extract.py`'s parallel-agent pattern (cluster → merge → stack → verify); content-hash source constraints for idempotency; write to `catalog/`.
- **Success signal**: `uv run --directory compliance-base python scripts/capabilities.py` reproduces the catalog and fails if any mandatory constraint is uncovered.

**Phase 2: Stack mapping**
- **Goal**: Let the human fix a concrete component per capability and see gaps.
- **Scope**: a `stack.json` (capability id → chosen component from the recommended set) + a gap report listing mandatory-linked capabilities with no chosen component.
- **Success signal**: gap report reads 0 when every mandatory-linked capability has a chosen component.

**Phase 3: Capability validator**
- **Goal**: Enforce capability completeness at plan-write time.
- **Scope**: extend `validate.py` so a plan declares delivered capabilities; gate on mandatory-capability coverage; a deliberately-incomplete plan fails.
- **Success signal**: incomplete plan fails, complete plan passes; runs in the existing `PostToolUse` hook.

**Phase 4: Wire & document**
- **Goal**: Parity with the shipped engines' ergonomics.
- **Scope**: `/neurawork-cc-harness:co-capabilities` command (deriving capabilities and refreshing the stack scaffold), an advisory nudge in the existing `co-` `PostToolUse` hook when the capability layer is absent, a new `compliance-base/CLAUDE.md`, and the doc surfaces that already list `co-extract`.
- **~~SessionStart bootstrap~~ — superseded 2026-08-20 (user decision).** The engine has no `SessionStart` hook by design and `install.py` (`REMOVED_TARGET_FILES` / `_prune_removed`) deletes any `co-session-start.py` plus its `.claude/settings.json` entry on every install. Bootstrapping is already carried by the shipped prebuilt catalog: `payload/catalog-seed/` holds `capabilities.{json,md}`, `install.py:_seed_catalog()` copies it into a fresh install, and `tests/test_catalog_seed.py` guards it against drift. The hook nudge replaces the bootstrap's remaining job — telling a repo without the layer how to build it.
- **Success signal**: a fresh install has the capability catalog from the shipped seed with no LLM run; `/neurawork-cc-harness:co-capabilities` re-derives it on demand; a repo without the layer is told so on its next plan write.

### Parallelism Notes

Phases 2 (stack mapping) and 3 (validator) both depend only on Phase 1's engine output and touch different files (`stack.json` vs `validate.py`) — they can run in parallel worktrees. Phase 4 waits on both.

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Capability structure | Per-framework lists, overlap kept | Cross-framework unified; domain-grouped | SOC 2 / ISO / GDPR are audited separately (user) |
| Stack target | Greenfield 2026, derive from capabilities | Existing named stack; opinionated reference | User is defining the stack now (user) |
| Framework scope v1 | All three (359 constraints) | ISO+SOC2 only; mandatory-only | Widest coverage (user) |
| Extraction method | Parallel SDK agents (ultracode) | Single-shot LLM; hand-authoring | Matches `extract.py`; 5× compression at 100% coverage |
| Component selection | Recommend 2-4, human fixes | Auto-pick one | Auditable human choice; avoids false precision |

---

## Research Summary

**Market / domain context**
- Compliance-to-control mapping is normally sold as GRC tooling (Vanta, Drata, Secureframe) that automates *evidence collection* against controls. This PRD is the *design-time* inverse: constraints → buildable capabilities → stack — an artifact those tools assume you already have.
- The ~5× compression (359 constraints → 68 capabilities) matches the known heavy overlap across the three frameworks' technical controls (access control, encryption, logging, incident response recur in all three).

**Technical context (this session's ultracode run)**
- 83 agents, 0 errors, 2.5M tokens, ~9.3 min. Extract (9 chunk agents) → Merge (3 per-framework) → Stack (68 component-rec agents) → Verify (3 adversarial coverage audits).
- Verify result: GDPR 109/109, SOC 2 111/111, ISO 59/59 mandatory covered, **0 uncovered**.
- Sample stack recs are concrete and current (e.g. external-reporting capability → HackerOne, security.txt/RFC 9116, Statuspage, Zammad), confirming greenfield-2026 component mapping is viable from model knowledge.

---

*Generated: 2026-07-23*
*Status: DRAFT — Phase 0 shipped; needs validation of the engine phases*
