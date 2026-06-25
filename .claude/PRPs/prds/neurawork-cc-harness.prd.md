# neurawork-cc-harness

> NeuraWork Claude Code Harness — a Claude Code plugin that keeps a repo's project knowledge fresh: it learns from every session to maintain the CLAUDE.md hierarchy + `docs/`, and compiles session logs into a per-repo knowledge base. Built as an *exemplary* artifact so any repo (incl. existing ones) can be upgraded by installing it.

## Problem Statement

NeuraWork and its customers re-explain the same context to Claude in every new session, suffer **code/doc drift** (CLAUDE.md and docs go stale, no one maintains them), and explain the same things twice across sessions and repos. The cost: wasted time re-priming the agent, inconsistent agent behavior across repos, slow onboarding, and knowledge that evaporates at session end.

## Evidence

- User (NeuraWork) statement: "wir müssen immer alles neu erklären … code drift … vieles doppelt erklärt." — direct pain, observed in daily use across own + customer repos.
- Existing global tooling (`coding-suite:continuous-learner`, `coding-suite:knowledge-compiler`) partially addresses this but does NOT cover: Python/claude-agent-sdk stack, interactive recon, or **seeding existing repos** — leaving the core "apply to a brownfield repo" gap open.
- Market scan: many Claude Code memory tools exist (claude-mem, memem, native auto-memory) but all are *personal/global vector stores*; none are *repo-local, doc-maintaining, and teachable*. → niche is open. (See Research Summary.)
- coleam00/claude-memory-compiler (the chosen basis) explicitly LACKS a seed/bootstrap for existing codebases — it is only open feature-request #1 there. So "recon = first analysis of an existing repo" is genuine net-new value.

## Proposed Solution

Build **`neurawork-cc-harness`**, a Claude Code plugin bundling two **independently installable** skills, each with its own install slash-command, interactive recon, and SessionEnd/PreCompact/SessionStart hooks:

1. **`knowledge-compiler`** — a clean re-implementation of the coleam00/claude-memory-compiler concept (Python + `claude-agent-sdk`): captures session transcripts → `daily/` logs → LLM-compiled per-repo knowledge base (`knowledge/concepts/`, `knowledge/connections/`, `knowledge/index.md`).
2. **`claudemd-lerner`** — learns from each session (git-diff + conversation) and keeps the **CLAUDE.md hierarchy + `docs/`** current. It compiles/searches the same kind of session logs but produces **no** knowledge wiki — only updated CLAUDE.md files and docs.

Both share two differentiators over the basis repo: an **interactive recon** at install (e.g. CLAUDE.md level-depth, docs structure, language, excluded dirs) and a **seed/bootstrap pass** that analyzes an existing repo on first install. Knowledge/docs always live **inside the repo** (per-repo), **never** in `.claude/`. Chosen over forking coleam00 directly because that repo has **no license** (cannot legally copy) and no recon/seed.

## Key Hypothesis

We believe a **repo-local, self-maintaining knowledge + CLAUDE.md harness with interactive recon and brownfield seeding** will **eliminate re-explanation and doc drift** for NeuraWork and its customers.
We'll know we're right when, after install, CLAUDE.md/docs stay current without manual edits, sessions stop re-explaining established context, and an existing repo can be seeded to a working state in minutes.

## What We're NOT Building

- **Global / cross-repo memory store** — knowledge is strictly per-repo, never in `~/.claude/`. (Explicit user constraint.)
- **Vector/RAG retrieval** — index-based markdown retrieval only (follows coleam00 design rationale; revisit only at ~2000+ articles).
- **A fork/copy of coleam00 code** — no license there; we reimplement the concept clean.
- **TechStack Validator & Compliance Validator** — defined and scoped here but deferred to **Session 2** (Phases 5–6 below). Not cut, just sequenced after the two core skills ship.

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Doc freshness (no drift) | CLAUDE.md/docs updated within 1 session of relevant change; 0 stale-doc complaints | lint check (stale-source detection) + manual spot-check |
| Re-explanation reduction | Measurable drop in repeated context-priming per session | qualitative session review; SessionStart-injected context present |
| Brownfield seed time | Existing repo seeded + usable knowledge/CLAUDE.md in < 10 min | timed install+recon+seed run |
| Adoption | N internal + customer repos installed (target TBD with user) | install count / repo list |
| Install success | One-command install per skill, recon completes, hooks fire on next session | smoke test on a fresh + an existing repo |

## Open Questions

- [ ] **License of coleam00/claude-memory-compiler is absent** — we must clean-room reimplement (no code copy) OR get explicit permission. Confirm legal approach before writing compiler code. (Public repo → highest priority.)
- [ ] Which license for `neurawork-cc-harness` itself? (public repo — MIT/Apache-2.0?)
- [ ] Exact adoption target N (internal + customer repos)?
- [ ] Should the two skills, when both installed, dedup their session-capture (shared `daily/`) or keep fully separate stores? (Default: separate, since independently installable.)
- [ ] Cost ceiling per compile/seed acceptable? (coleam00: ~$0.45–0.65/compile, seed likely higher on large repos.)
- [ ] Recon language default de/en, and is `claude-agent-sdk` auth via `~/.claude/.credentials.json` acceptable for customers (vs. API key)?

---

## Users & Context

**Primary User**
- **Who**: NeuraWork engineers + NeuraWork customers running Claude Code in their own repos — solo devs and small teams across many repos (greenfield AND existing/brownfield).
- **Current behavior**: Re-explain project context each session; CLAUDE.md/docs drift or don't exist; knowledge lost at session end.
- **Trigger**: Starting/continuing work in a repo where the agent lacks current project context; onboarding a new repo; wanting a repo to "remember."
- **Success state**: Install once → recon + seed → from then on the repo's CLAUDE.md/docs stay current and a knowledge base accrues, with no manual upkeep.

**Job to Be Done**
When I (or a customer) start work in a repo, I want the agent to already know the project's conventions and accumulated knowledge and keep them current automatically, so I can stop re-explaining and stop fighting doc drift.

**Non-Users**
- People wanting a personal/global cross-project memory (that's claude-mem / native auto-memory — out of scope).
- Repos that must keep knowledge outside the repo (we only write in-repo).

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | `knowledge-compiler` skill: capture → `daily/` → LLM compile → `knowledge/{concepts,connections,index.md}` (Python + claude-agent-sdk) | Core value; clean reimpl of coleam00 concept |
| Must | `claudemd-lerner` skill: session (git-diff + convo) → maintain CLAUDE.md hierarchy + `docs/`, **no** knowledge wiki | Core value; the doc-drift fix |
| Must | Per-skill install slash-command | User requirement: each independently installable |
| Must | Interactive **recon** per skill (e.g. CLAUDE.md level-depth, docs layout, language, excluded dirs, compile time) | Net-new over coleam00; tailors to repo |
| Must | **Seed/bootstrap** pass: analyze an existing repo on first install | Required to "upgrade existing repos"; coleam00 lacks this |
| Must | Compile trigger: **manual slash-command** + **auto on SessionStart when dailys > 6h old** | User-specified; fixes coleam00's rigid 18:00 trigger |
| Must | All knowledge/docs written **inside the repo**, never `.claude/` | Hard user constraint |
| Must | Independent installs → **separate hooks per skill**, plugin-namespaced (`neurawork-cc-harness:knowledge-compiler`, `:claudemd-lerner`) to avoid clash with global `coding-suite:*` | User flagged collision risk |
| Should | Shared session-capture infra (opt-in) when both installed | Avoid duplicate hooks if user wants |
| Should | `lint`/health-check (broken links, stale, orphans) for knowledge base | From coleam00; quality guard |
| Won't (Session 2) | 🧩 TechStack Validator — checks plans/code vs. chosen stack allowlist | Deferred; separate phase |
| Won't (Session 2) | 🛡️ Compliance Validator — checks plans/PRDs vs. chosen constraints | Deferred; separate phase |

### MVP Scope

Full v1 = **both skills, fully featured**: install commands + interactive recon + brownfield seed + the specified compile triggers + in-repo per-repo stores + plugin-namespaced separate hooks. Nothing in the two-skill scope is cut. Validators are documented (Phases 5–6) but ship in Session 2.

### User Flow

Shortest path to value (per skill):
1. User runs install slash-command (e.g. `/neurawork-cc-harness:install-knowledge-compiler`).
2. **Recon**: interactive Q&A (CLAUDE.md depth / docs layout / language / excluded dirs / compile time) — answers stored in plugin `.local` config.
3. **Seed**: plugin analyzes the existing repo, writes initial `knowledge/` (compiler) or initial CLAUDE.md hierarchy + `docs/` (lerner).
4. Hooks installed → next sessions auto-capture; SessionStart injects current context; compile runs on-demand or when dailys > 6h.
5. User sees CLAUDE.md/docs/knowledge staying current with zero manual edits.

---

## Technical Approach

**Feasibility**: **HIGH** — coleam00 proves the mechanism (hooks + claude-agent-sdk + markdown stores) works; we reimplement clean and add recon + seed. Plugin scaffolding via `plugin-dev` + `skill-creator` skills.

**Architecture Notes**
- **Stack**: Python 3.12+, `uv`, `claude-agent-sdk`; Claude Code hooks `SessionEnd` / `PreCompact` / `SessionStart`. (Matches user's "übernehmen python + claude sdk".)
- **Stores (per-repo, in-repo)**:
  - knowledge-compiler → `daily/`, `knowledge/{concepts,connections,index.md,log.md}`, runtime `state.json`.
  - claudemd-lerner → `daily/` (or shared), maintains existing CLAUDE.md files (multi-level per recon) + `docs/` tree. No `knowledge/`.
- **Recon + seed** = net-new modules (coleam00 has neither). Seed = one-time repo analysis pass producing the initial store.
- **Namespacing**: ship under plugin `neurawork-cc-harness`; skills `knowledge-compiler` + `claudemd-lerner`. `claudemd-lerner` name is collision-free; `knowledge-compiler` collides with `coding-suite:knowledge-compiler` on bare invoke → always document/invoke via FQN. (User accepted plugin-namespace approach.)
- **Triggers**: manual compile command + SessionStart auto-compile guarded by a >6h daily-age check.
- **Auth**: claude-agent-sdk via `~/.claude/.credentials.json` (Max/Team/Enterprise) — confirm for customers.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| coleam00 has **no license** — copying code is unlawful | H | Clean-room reimplement from concept/architecture only; never paste their code; document provenance |
| Skill-name collision with `coding-suite:knowledge-compiler` | M | Plugin namespace + always FQN invoke; clear docs; consider unique label if confusion persists |
| Token cost / large brownfield seed blows up | M | Chunk seed; cap turns; warn + estimate in recon; reuse coleam00 cost guards |
| `claudemd-lerner` overlaps `coding-suite:continuous-learner` | M | Differentiate: Python-SDK + recon + seed + multi-level CLAUDE.md; document when to use which |
| Hooks fire recursively (agent invokes hook) | L | `CLAUDE_INVOKED_BY` recursion guard (proven in coleam00) |
| Writing into wrong dir (`.claude/`) | L | Hard guard: refuse to write knowledge/docs under `.claude/` |

---

## Implementation Phases

<!--
  STATUS: pending | in-progress | complete
  PARALLEL: phases that can run concurrently
  DEPENDS: phases that must complete first
  PRP: link to generated plan file once created
-->

| # | Phase | Description | Status | Parallel | Depends | PRP Plan |
|---|-------|-------------|--------|----------|---------|----------|
| 1 | Plugin scaffold & shared infra | `neurawork-cc-harness` plugin skeleton (plugin.json, dirs), shared session-capture + hook patterns, namespacing, in-repo write-guard | complete | - | - | [scaffold plan](../plans/completed/neurawork-cc-harness-scaffold.plan.md) |
| 2 | knowledge-compiler skill | Clean reimpl of compile/flush/query/lint + install command + recon + seed + triggers | complete | with 3 | 1 | [kc plan](../plans/completed/neurawork-cc-harness-knowledge-compiler.plan.md) |
| 3 | claudemd-lerner skill | Session→CLAUDE.md hierarchy + docs maintenance (no wiki) + install command + recon + seed + triggers | complete | with 2 | 1 | [cl plan](../plans/completed/neurawork-cc-harness-claudemd-lerner.plan.md) |
| 4 | Exemplary docs & self-host | Apply both skills to THIS repo as the worked example; write install/upgrade guide; choose license | pending | - | 2, 3 | - |
| 5 | TechStack Validator (Session 2) | Checks plans/code vs. chosen stack allowlist | pending | with 6 | 4 | - |
| 6 | Compliance Validator (Session 2) | Checks plans/PRDs vs. chosen constraints | pending | with 5 | 4 | - |

### Phase Details

**Phase 1: Plugin scaffold & shared infra**
- **Goal**: A valid Claude Code plugin shell that both skills plug into, with naming/collision strategy and the in-repo write-guard baked in.
- **Scope**: `plugin.json`, dir layout, shared transcript-capture helper, hook templates (SessionEnd/PreCompact/SessionStart), recursion guard, plugin `.local` config pattern for recon answers. Built via `plugin-dev`.
- **Success signal**: Plugin installs/loads; both skills resolvable as `neurawork-cc-harness:*`; no clash with `coding-suite:*`.

**Phase 2: knowledge-compiler skill**
- **Goal**: Per-repo knowledge base that builds itself from sessions.
- **Scope**: Python `compile`/`flush`/`query`/`lint` (clean-room), `daily/` + `knowledge/` stores, install slash-command, interactive recon, brownfield seed, manual + >6h-SessionStart triggers. Built via `skill-creator`.
- **Success signal**: On a test repo, a session produces a `daily/` log; compile yields `knowledge/concepts` + `connections` + `index.md`; SessionStart injects index; seed bootstraps an existing repo.

**Phase 3: claudemd-lerner skill**
- **Goal**: CLAUDE.md hierarchy + `docs/` stay current automatically; no knowledge wiki.
- **Scope**: Session capture (git-diff + convo) → extract rules/patterns → update multi-level CLAUDE.md (depth from recon) + `docs/` tree; install slash-command, recon (level-depth, docs layout, language, excluded dirs), brownfield seed, same triggers. Built via `skill-creator`.
- **Success signal**: A change in a test repo results in an updated CLAUDE.md/doc within one session; existing repo seeded with a sane CLAUDE.md hierarchy; nothing written under `.claude/`.

**Phase 4: Exemplary docs & self-host**
- **Goal**: Make it the teachable, copyable example.
- **Scope**: Install both skills on `howtobuildsoftware2026` itself; write upgrade/install guide; pick + add license; document FQN invocation + when-to-use vs. coding-suite.
- **Success signal**: A second repo can be upgraded by following the guide; license present; this repo self-hosts the harness.

**Phase 5–6: Validators (Session 2)**
- **Goal**: Gate plans/code/PRDs against chosen stack allowlist (TechStack) and constraints (Compliance).
- **Scope**: TBD in Session 2 — define allowlist/constraint config format, where checks hook in (plan/PRD review, pre-commit?).
- **Success signal**: A plan using a disallowed stack item / violating a constraint is flagged.

### Parallelism Notes

Phases 2 and 3 can run in parallel (separate worktrees) — both depend only on Phase 1's shared infra and touch independent skill dirs (`knowledge-compiler/` vs. `claudemd-lerner/`). Phases 5 and 6 likewise parallel in Session 2. Phase 4 is a barrier after 2+3.

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Routing | PRD first, then build | Build directly; short PRD | User chose full PRD |
| Naming / collision | Keep names, rely on plugin namespace | Unique prefixes (`nw-*`); rename | User accepted; `claudemd-lerner` is collision-free, `knowledge-compiler` via FQN |
| Basis usage | Fetch + analyze coleam00, reimplement clean | Copy code; concept-only without reading | User chose fetch+analyze; coleam00 has NO license → must reimplement |
| Stack | Python + claude-agent-sdk | bash/node like coding-suite | User: "übernehmen python + claude sdk" |
| Knowledge location | Per-repo, in-repo only | Global `~/.claude/` | Hard user constraint |
| MVP scope | Both skills fully featured (incl. seed) | Trim seed to "should" | User: "mvp soll alles haben, lasse nichts aus" |
| Compile trigger | Manual + auto on SessionStart if dailys > 6h | Fixed 18:00 (coleam00) | User-specified; fixes coleam00 rigidity |
| Install model | Independent installs, separate hooks per skill | Single shared install | User: "unabhängig installierbar" |
| Release | Public repo | Internal-only | User: "ist öffentliches repo" |
| Validators | Deferred to Session 2 (documented, not cut) | In v1 | User repeatedly scoped them to Session 2 |

---

## Research Summary

**Market Context**
- Crowded Claude Code memory space (claude-mem, claude-mem-lite, memem, claude-obsidian-memory, memory-mcp, native auto-memory/Dreaming) — but all are personal/global, mostly vector/SQLite. None are repo-local + doc-maintaining + teachable. Niche open.
- `coding-suite:continuous-learner` + `:knowledge-compiler` (already global on this machine) are the closest, but bash-based, no recon, no brownfield seed, no Python-SDK. Direct collision risk on the bare `knowledge-compiler` name → mitigated by plugin namespace + FQN.

**Technical Context (coleam00/claude-memory-compiler)**
- Python 3.12 + `uv` + `claude-agent-sdk`. Hooks: `SessionEnd`/`PreCompact` extract last ~30 turns from JSONL transcript → spawn `flush.py` → append to `daily/YYYY-MM-DD.md`; `compile.py` (after 18:00 or on demand) → LLM writes `knowledge/concepts`, `connections`, updates `index.md`; `session-start.py` injects `index.md` + recent daily as `additionalContext`. Markdown + Obsidian wikilinks; no RAG. Costs ~$0.02–0.05 flush, ~$0.45–0.65 compile.
- **Gaps we improve on**: no interactive recon, no seed/bootstrap for existing repos (only feature-request #1), rigid 18:00 trigger, **no license**.

---

*Generated: 2026-06-18*
*Status: DRAFT - needs validation*
