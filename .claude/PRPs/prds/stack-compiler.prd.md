# stack-compiler

> Turn a product idea + its requirements into a **fixed, tracked OSS stack** chosen from
> the components already in the compliance capability catalog — then gate every new PRD
> and plan against that stack. The fourth skill of `neurawork-cc-harness`.

## Problem Statement

`compliance-base/catalog/capabilities.json` holds **68 capabilities** and **163 distinct
OSS components** (247 capability→component mappings, split `in-product` / `internal-infra`).
It answers *"what could satisfy this constraint?"* — it does **not** answer *"what does
**this** product need, and which component did we actually pick?"*

`compliance-capabilities.prd.md` Phase 2 (in progress) adds the *storage* half:
`catalog/stack.json` with one entry per capability, `chosen: null`, plus a gap report.
Two things are still missing on top of it:

1. **Nobody narrows the catalog to the product.** All 68 capabilities apply to every
   product by default. A service that stores no personal data still gets 25 GDPR entries
   to fill. Narrowing happens in someone's head, untracked — and an untracked narrowing
   is indistinguishable from an oversight.
2. **Nothing enforces the choice.** Once components are fixed, a new PRD or plan can
   still propose anything. Same drift the harness kills for docs and constraints, one
   layer up.

## Evidence

- **Direct user statement (this session):** "aus dem schon vorhandenen oss stack der in
  den capabilities drin ist die richtigen mappen, durch die constraints der gewählten
  compliance richtlinien und durch die idee selber … die dann vorgeschlagen werden und
  die ich im auswählprozess … festschreibe." Plus: "immer wenn ein plan oder ein prd
  erzeugt wird soll der hook auslösen und den plan und den prd auf unsere constraints
  prüfen."
- **Catalog data:** 68 capabilities / 163 components / 247 mappings — far more than any
  single product needs, with no applicability layer anywhere.
- **Split specification:** the same deliverable was parked in two PRDs —
  `neurawork-cc-harness.prd.md` Phase 5 ("TechStack Validator — checks plans/code vs.
  chosen stack allowlist") and `compliance-capabilities.prd.md` Phase 2. Neither
  referenced the other. This PRD consolidates the un-owned remainder.
- **Proven hook surface:** `compliance-compiler` already validates plan writes via
  `PostToolUse` (`co-post-tooluse.py` → inline `precheck.py` + detached `validate.py`).
  The stack gate is the same mechanism at a different level.

## Vocabulary

Four things in this repo are called "stack". Fixed meanings, used consistently from here on:

| Term | Meaning | Artifact | Schema owner |
|------|---------|----------|--------------|
| **capability** | A compliance-derived technical building block ("immutable audit logging") | `compliance-base/catalog/capabilities.json` | `compliance-compiler` |
| **component** | A concrete OSS project that can deliver a capability (Keycloak, Temporal) | `stack[]` entries inside `capabilities.json` | `compliance-compiler` |
| **stack.json** | The components **chosen** for this product, plus per-capability applicability | `compliance-base/catalog/stack.json` | `compliance-compiler` (`scripts/stack.py`) — **written by both skills** |
| **inventory** | Which version of what runs **where**, right now | `docs/inventory.json` (external `stack-tools` plugin) | not this repo |

`stack-compiler` never touches inventory; `stack-tools` never touches `stack.json`.

## Proposed Solution

A fourth independently installable skill, **`stack-compiler`**, engine dir `stack-base/`,
hook prefix `st-` — same install shape as the three shipped skills. It owns *machinery
only*; the data artifact stays in `compliance-base/catalog/stack.json` (decision
2026-08-13: one file, no second stack artifact).

Four stages:

1. **Scope** — the engineer describes the product (idea + requirements). The engine
   decides which frameworks apply and, per capability, whether it is **applicable**, with
   a recorded reason. Written into `stack.json` through `stack.py` as additive fields.
   Filtering a capability *out* is a tracked decision, never a silent omission.
2. **Map & rank** — for every applicable capability, rank the components **already in the
   catalog** against the product requirements plus the existing license/role policy
   (`in-product` must be product-embeddable; `internal-infra` may be copyleft/free-tier).
   Component pool is **closed**: no invention.
3. **Select** — interactive confirmation. Human picks one component per applicable
   capability; the choice lands in `stack.json`'s existing `chosen` field. The gap report
   from `compliance-capabilities` Phase 2 then reads 0.
4. **Gate** — an `st-post-tooluse` hook fires on every **PRD** and **plan** write and
   checks the document against `stack.json`: components outside the allowlist, applicable
   capabilities the document ignores, license-policy violations.

Chosen over extending `compliance-compiler` because stack *choice* is not purely a
compliance concern (product requirements drive it too), and a user who wants only the
constraint catalog should not inherit the scoping and gate machinery. The *data* stays
with compliance-base because two stack files would recreate the drift this exists to kill.

### Boundary with `compliance-compiler`

| Concern | Owner |
|---------|-------|
| Constraint catalog, capability catalog | `compliance-compiler` |
| `stack.json` schema, `--scaffold`, gap report | `compliance-compiler` (`scripts/stack.py`, cap-PRD Phase 2) |
| Constraint-level validation of plans (+ PRDs, harness Phase 7) | `compliance-compiler` (`co-` hook) |
| Mandatory **capability**-coverage gate | `compliance-compiler` (cap-PRD Phase 3) |
| Product scoping / applicability decisions | **`stack-compiler`** |
| Component ranking + interactive selection | **`stack-compiler`** |
| Component-allowlist + license gate on PRD/plan writes | **`stack-compiler`** (`st-` hook) |

## Key Hypothesis

We believe a **product-scoped, human-fixed stack with a write-time gate** will make the
stack decision **made once, tracked, and defensible** instead of re-argued every session.
We'll know we're right when a new plan cites `stack.json` instead of naming components
ad-hoc, an off-stack proposal is flagged at write time, and a catalog change surfaces
exactly which choices became stale.

## What We're NOT Building

- **A second stack file** — one artifact, `compliance-base/catalog/stack.json`, schema
  owned by `compliance-compiler`. `stack-compiler` writes through `stack.py`.
- **New components outside the catalog** — v1 chooses only from the 163 components in
  `capabilities.json`. Extending the pool is a `compliance-compiler` concern.
- **Product-domain technology gating** — vector DBs, frontend frameworks, the product's
  own queue: not in the compliance catalog, therefore not mapped and not gated in v1. The
  idea drives *filtering and ranking* of the compliance pool, not generation of a full
  product stack. (See Open Questions.)
- **Runtime version / CVE auditing** — that is the external `stack-tools` plugin operating
  on `inventory`. Different artifact, different question.
- **Auto-picking a component** — the engine proposes, the human fixes. Inherited from
  `compliance-capabilities.prd.md`.
- **Constraint-level validation** — already shipped in `compliance-compiler`; the `st-`
  gate sits at the component level and runs beside it.

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Applicability accountability | 100% of non-applicable capabilities carry a recorded reason | schema check on `stack.json`; 0 unexplained omissions |
| Mandatory safety | 0 mandatory constraints dropped without a justified applicability decision | every mandatory constraint is *covered by a chosen component* OR *traced to a justified non-applicable capability* |
| Stack completeness | Every applicable capability has exactly one chosen component | Phase-2 gap report reads 0 |
| Gate effectiveness | A PRD/plan naming an off-stack component is flagged on write | test document with a deliberate off-stack component |
| Gate noise | ≤1 LLM validation run per document per meaningful change | debounce hit-rate on repeated edits |
| Staleness detection | A catalog change invalidates affected choices, not the whole file | hash check reports only affected capabilities |

## Open Questions

- [x] **Schema extension coordination** — resolved 2026-08-13, right after cap-PRD
      Phase 2 merged (PR #22). `stack.json` now carries `applicable: true` /
      `applicability_reason: ""` / `scoped_from: null` per capability, and
      `stack.py:scaffold()` carries all three over by key. Without that carry-over a
      later `--scaffold` run would have silently erased every scoping decision, since
      scaffold rebuilds each entry from the catalog and copies only listed fields.
- [ ] **Product-domain components (v2?)** — should the catalog eventually carry
      product-capability components (vector DB, API gateway, frontend) so the gate covers
      the whole stack, or does `stack.json` stay compliance-scoped forever?
- [ ] **One component per capability, or a set?** Some capabilities plausibly need two
      (IAM: Keycloak *and* OpenFGA). Phase 2's schema decides: `chosen: string` vs `string[]`.
- [ ] **Component currency** — recommendations come from Jan-2026 model knowledge
      (inherited open question). Live research on the shortlist at selection time, or
      accept the catalog and refresh it upstream?
- [ ] **Re-scoping an existing product** — is scope re-runnable against a changed idea,
      and does that diff `stack.json` or start over?
- [ ] **Gate on `Write` only, or also `Edit`?** Edit-heavy interactive PRD authoring is
      the noise source; debounce may be enough, or PRDs may need write-only.

---

## Users & Context

**Primary User**
- **Who**: NeuraWork engineer/architect starting a new product that must satisfy
  GDPR / SOC 2 / ISO 27001.
- **Current behavior**: reads `capabilities.md`, mentally filters, picks components by
  feel, writes nothing down; next session repeats.
- **Trigger**: "we're building X — which of these 163 components do we actually take?"
- **Success state**: describes the product once, reviews a ranked shortlist per applicable
  capability, confirms choices, and from then on every PRD and plan is checked against them.

**Job to Be Done**
When I start a compliant product, I want the component choice made once from the tracked
catalog and enforced afterwards, so the stack stops drifting between sessions and I can
show an auditor why each piece is there.

**Non-Users**
- Teams on a fixed legacy stack (they need gap analysis, not greenfield selection).
- Operators asking "which version runs where" — that is `stack-tools` / inventory.

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | Product scoping: idea + requirements → applicable frameworks + per-capability applicability **with recorded reasons** | Without it the catalog can't be narrowed; without reasons narrowing is a silent compliance hole |
| Must | Mandatory-safety gate: covered by a choice OR justified as non-applicable | The single highest-risk failure mode of this skill |
| Must | Ranking of catalog components against product requirements + license/role policy | The mapping step the user asked for; closed pool |
| Must | Interactive selection writing `chosen` into `compliance-base/catalog/stack.json` via `stack.py` | The decision artifact; one file, no duplicate |
| Must | `st-post-tooluse` gate on **PRD and plan** writes (off-allowlist component, ignored applicable capability, license violation) | The enforcement half; user requirement that PRDs are checked too |
| Must | Debounce (content hash of last validated text) before spawning any LLM validation | Interactive PRD authoring would otherwise spawn an agent per save |
| Must | All machinery output inside the repo, never under `.claude/` | Harness-wide hard constraint (`_shared/repo_guard.py`) |
| Should | Staleness check: catalog hash change → list affected capabilities only | Keeps re-selection incremental |
| Should | Graceful degrade when `compliance-base` is absent | Hard data dependency must fail loud and cheap |
| Could | Live research on the shortlist at selection time | Defends the choice with current facts, not Jan-2026 knowledge |
| Could | `/st-*` slash commands mirroring `co-extract` / `co-validate` ergonomics | Parity |
| Won't | A second stack file; inventing components outside the catalog | One artifact, closed pool |
| Won't | Product-domain tech gating; runtime/CVE auditing | Out of scope, see NOT Building |

### MVP Scope

MVP = Phases 1–4: scope → map/rank → select → gate. A stack file that exists but is not
enforced is another doc that drifts; an enforcement hook without decisions has nothing to
enforce. Commands and docs (Phase 5) are ergonomics.

### User Flow

1. `/neurawork-cc-harness:st-init` installs `stack-base/` (recon: frameworks, where PRDs
   and plans live, warn vs. block).
2. `/st-scope` — engineer describes the product; engine writes applicability decisions +
   reasons into `stack.json`.
3. `/st-select` — per applicable capability, a ranked shortlist from the catalog; human
   confirms; `chosen` written; cap-PRD Phase 2 gap report drops to 0.
4. Any PRD or plan write → `st-post-tooluse` checks it against `stack.json`, emits an
   advisory summary, writes a report, blocks only if configured to.
5. Catalog changes → staleness check names the affected capabilities; re-run `/st-select`
   for those only.

---

## Technical Approach

**Feasibility**: **HIGH** — every mechanism exists in this repo already. Parallel SDK
agents with `asyncio.gather` + semaphore (`extract.py`, `capabilities.py`), catalog-hash
idempotency with a coverage gate (commit `8fc9a21`), a `PostToolUse` validator with inline
deterministic precheck + detached LLM run (`co-post-tooluse.py`), install/ADOPT engine
split with additive hook merging, and the in-repo write guard.

**Architecture Notes**
- **Install**: `plugins/neurawork-cc-harness/engines/stack-compiler/` with `install.py`,
  `recon.py`, `payload/`, `tests/`; target dir `stack-base/`; hook `hooks/st-post-tooluse.py`.
  Settings merge is additive — `co-` and `st-` `PostToolUse` entries coexist (proven).
- **Data dependency**: reads `compliance-base/catalog/{capabilities,stack}.json`; writes
  `stack.json` through `compliance-base/scripts/stack.py` so there is exactly one schema
  owner. If `compliance-base` is absent, `stack-compiler` gates nothing and says so.
  Independent *installability* is preserved; independent *operation* is not claimed.
- **Schema extension** (additive, needs coordination with cap-PRD Phase 2): per capability
  `applicable: bool`, `applicability_reason: str`, `scoped_from: <product-scope hash>`.
  `chosen`, `options`, `rationale` stay as Phase 2 defines them.
- **Gate levels** (answers `compliance-capabilities.prd.md` open question 3): coarse at the
  top, fine at the bottom — a **PRD** is checked at capability/component level, a **plan**
  additionally at constraint level (existing `co-` gate). Both engines run; each writes its
  own report.
- **Precheck vs. LLM**: deterministic inline check (allowlist membership via an alias table
  — Postgres/PostgreSQL/pg —, license role, applicable-but-unmentioned capabilities) under
  1s; semantic check delegated to a detached agent, guarded by a debounce hash in
  `stack-base/reports/.state.json`.
- **Mode**: `validate_mode` per target — PRDs default `warn` (blocking a PRD write breaks
  the interactive PRD generator), plans configurable.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Applicability filter silently drops mandatory constraints** | **H** | Accept only "covered by a choice" or "justified non-applicable"; unexplained omission fails the run. Highest-priority test case. |
| ~~Schema conflict with the in-flight cap-PRD Phase 2 plan~~ | resolved | Closed 2026-08-13: the three fields and their scaffold carry-over shipped right after PR #22 |
| LLM re-runs churn `stack.json` | M | Human-confirmed selection is the only writer of `chosen`; engine output is a proposal |
| Two PostToolUse validators × Write+Edit = agent storm | M | Debounce hash + inline precheck before any spawn; measured by the gate-noise metric |
| Catalog changes invalidate the whole stack | M | Per-capability hash comparison, not whole-file |
| Component recommendations stale (Jan-2026) | M | Optional shortlist research (Could); date-stamp the decision |
| Word "stack" collides with the external `stack-tools` plugin | M | Vocabulary table above; distinct skill name, `st-` prefix, distinct artifacts |
| Product-domain tech expected to be gated but isn't | M | Stated in NOT Building; the gate reports its own scope in every summary |

---

## Implementation Phases

<!--
  STATUS: pending | in-progress | complete
  PARALLEL: phases that can run concurrently
  DEPENDS: phases that must complete first
  PRP: link to generated plan file once created
-->

| # | Phase | Description | Status | Parallel | Depends | Plan | Report | PR |
|---|-------|-------------|--------|----------|---------|------|--------|----|
| 0 | PRD reconciliation | Harness PRD: Phase 5 superseded by this PRD, Phase 6 → complete, skill registry, vocabulary, new Phase 7 (co- hook on PRD writes). Cap-PRD: cross-link, answer open question 3 | in-progress | - | - | - | - | - |
| 1 | Scope engine | Idea + requirements → applicable frameworks + per-capability applicability with reasons; mandatory-safety gate. Schema fields shipped 2026-08-13; `gaps()` still counts non-applicable capabilities as gaps and must learn to skip them here | complete | - | 0, cap-PRD 2 | [scope engine plan](/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/completed/stack-compiler-scope-engine.plan.md) | [implementation report](/home/felix/.prp/howtobuildsoftware2026-35325a96/reports/stack-compiler-scope-engine-report.md) | [#25](https://github.com/neurawork-git/howtobuildsoftware2026/pull/25) |
| 2 | Map & rank | Rank closed-pool components per applicable capability against requirements + license/role policy | complete | - | 1 | [map & rank plan](/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/completed/stack-compiler-map-rank.plan.md) | [implementation report](/home/felix/.prp/howtobuildsoftware2026-35325a96/reports/stack-compiler-map-rank-report.md) | [#27](https://github.com/neurawork-git/howtobuildsoftware2026/pull/27) |
| 3 | Selection | Interactive confirmation writing `chosen` via `stack.py`; staleness check on catalog hash | in-progress | with 4 | 2 | [selection plan](/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/stack-compiler-selection.plan.md) | - | - |
| 4 | `st-` gate | `st-post-tooluse` on PRD + plan writes: allowlist / applicable-capability / license checks, precheck + debounced LLM report, warn\|block | pending | with 3 | 2 | - | - | - |
| 5 | Wire & document | `install.py` / `recon.py` / payload / tests, `/st-init`, `/st-scope`, `/st-select`, `/st-validate`, self-host, docs + CLAUDE.md | pending | - | 3, 4 | - | - | - |

### Phase Details

**Phase 0: PRD reconciliation**
- **Goal**: One owner per deliverable before any code.
- **Scope**: `neurawork-cc-harness.prd.md` — skill registry, vocabulary block, Phase 6 →
  `complete` (compliance-compiler shipped it), Phase 5 → superseded by this PRD, new
  Phase 7 for extending the `co-` hook to PRD writes.
  `compliance-capabilities.prd.md` — cross-link to this PRD; open question 3 answered
  (PRD = capability level, plan = constraint level).
- **Success signal**: no deliverable appears in two PRDs; every PRD status matches reality.

**Phase 1: Scope engine**
- **Goal**: Narrow 68 capabilities to the ones this product needs, accountably.
- **Scope**: product description intake; per-capability applicability decision + reason;
  the mandatory-safety gate (covered OR justified) failing the run on unexplained
  omission. Parallel SDK agents per capability group, mirroring `capabilities.py`.
- **Success signal**: a deliberately under-scoped product ("no personal data" while the
  description clearly stores user emails) fails the gate.

**Phase 2: Map & rank**
- **Goal**: The mapping the user asked for — idea + constraints → concrete components.
- **Scope**: for each applicable capability, rank its existing `stack[]` entries by fit
  against the stated requirements; enforce the `in-product` license policy; return 2–4
  ranked options each with a rationale. Closed pool — proposing a component absent from
  the catalog is an error, not a feature.
- **Success signal**: every proposal traces to a `stack[].name` in `capabilities.json`;
  no `not_in_product` license appears in an `in-product` slot.

**Phase 3: Selection**
- **Goal**: Fix the decision in the tracked file.
- **Scope**: interactive confirmation per capability; write `chosen` + `rationale` via
  `stack.py`; staleness check comparing per-capability hashes when the catalog changes.
- **Success signal**: the Phase-2 gap report reads 0 after a complete pass; changing one
  capability in the catalog marks exactly that one stale.

**Phase 4: `st-` gate**
- **Goal**: Enforcement on every PRD and plan write.
- **Scope**: `st-post-tooluse.py` matching both `.claude/PRPs/prds/*.prd.md` and
  `.claude/PRPs/plans/**/*.plan.md` (excluding `completed/`); inline deterministic
  precheck (off-allowlist component via alias table, applicable capability the document
  ignores, license violation); debounce hash before spawning the LLM report; `warn`
  default for PRDs.
- **Success signal**: a PRD naming an off-stack component is flagged on write; repeated
  saves with no content change spawn no second agent.

**Phase 5: Wire & document**
- **Goal**: Same install ergonomics as the three shipped skills.
- **Scope**: engine dir + payload + recon + tests; four slash commands; self-host into
  this repo; `docs/` + CLAUDE.md updates; plugin manifest entry.
- **Success signal**: a second repo installs `stack-compiler` from the marketplace and the
  gate fires there on the next PRD write.

### Parallelism Notes

Phase 1 depends on `compliance-capabilities` Phase 2 landing the `stack.json` schema.
Phases 1→2 are sequential. Phases 3 and 4 both need only Phase 2's output and touch
different files (selection flow vs. hook) — parallel. Phase 5 is a barrier.

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Placement | Fourth skill `stack-compiler`, dir `stack-base/`, prefix `st-` | Extend `compliance-compiler` | Stack choice is driven by product requirements too; compliance-only users shouldn't inherit it (user) |
| `stack.json` location | **One file**, `compliance-base/catalog/stack.json`, schema owned by `compliance-compiler` | Own file in `stack-base/`; two layered files; stop the in-flight plan | Decided 2026-08-13 after a parallel session began implementing cap-PRD Phase 2 there; two stack files would recreate the drift this feature removes (user) |
| Component pool | Closed — only components already in `capabilities.json` | LLM proposes freely; hybrid | "aus dem schon vorhandenen oss stack … die richtigen mappen" (user); every proposal stays catalog-traceable |
| Role of the product idea | Filter + ranking signal over the compliance pool | Generator of a full product stack | Follows from the closed pool; product-domain tech is not in the catalog |
| Gate levels | PRD → capability/component (coarse); plan → additionally constraints (fine) | Constraints everywhere; capabilities everywhere | Answers cap-PRD open question 3; PRDs never carry constraint IDs, so ID-matching there is pure noise |
| Gate scope | Both PRDs and plans | Plans only (status quo) | User requirement this session |
| PRD gate mode | `warn` by default | `block` | Blocking a PRD write breaks the interactive PRD generator |
| Word "inventory" | Reserved for `stack-tools` running versions | Use it for the chosen set | Avoids a three-way collision; the chosen set is `stack.json` |
| Selection | Human confirms every capability | Auto-pick top-ranked | Inherited from the capability PRD; auditable choice |

---

## Research Summary

**In-repo context**
- `capabilities.json`: 68 capabilities across three frameworks, 163 distinct components,
  247 capability→component entries, `role` split 131 `in-product` / 116 `internal-infra`,
  license policy already encoded (`embeddable` / `not_in_product` /
  `internal_infra_exception`). The gate gets license enforcement almost for free.
- `co-post-tooluse.py` + `precheck.py`: the working template for the `st-` gate —
  defensive payload reading, recursion guard, worktree redirect, inline precheck, detached
  validator, `warn`/`block` switch. Note `precheck.is_plan_path()` currently matches only
  `.claude/PRPs/plans/**/*.plan.md`; PRD matching is new in both engines.
- `capabilities.py` / `extract.py`: the parallel-agent template for Phases 1–2.

**Adjacent tooling**
- The external `stack-tools` plugin answers the *runtime* question (versions, CVEs, drift)
  from `docs/inventory.json`. Complementary and deliberately separate: `stack-compiler`
  decides what may be used, `stack-tools` reports what is actually running. A future
  cross-check ("something is running that is not in `stack.json`") is plausible, out of
  scope here.

---

*Generated: 2026-08-13*
*Status: DRAFT — needs validation*
