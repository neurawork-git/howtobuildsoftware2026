# AGENTS.md — Compliance Compiler Constitution

This file is the specification the compliance agents follow when (1) **extracting**
a framework catalog into structured constraints and (2) **validating** a PRP plan
against that catalog. Read it in full before extracting or validating.

The compiler turns dense regulatory/standard prose into an atomic, machine-readable
catalog of *constraints* ("features"): the conditions software (and the plans that
describe it) must satisfy to meet GDPR/DSGVO, SOC 2, and ISO/IEC 27001.

## Copyright boundary (read first)

ISO/IEC 27001 and the AICPA SOC 2 Trust Services Criteria are **copyrighted**. Do
**not** copy their text verbatim into the catalog. Store the official *control /
article identifier and short title*, plus a **paraphrased** requirement in your own
words. GDPR (Regulation (EU) 2016/679) is public and may be quoted briefly, but
paraphrase there too for consistency. If you do not have access to the source text
for a shard, extract from your own knowledge of the framework's published control
identifiers and intent — never invent identifiers.

## The Model

```
frameworks    source        — GDPR / SOC 2 / ISO 27001 (prose, external)
shards        work units    — one bounded slice of one framework per agent
LLM           compiler      — reads a shard, emits constraints for it
catalog/      executable    — the structured, queryable constraint catalog
validate      runtime       — checks a PRP plan against the catalog
```

The catalog lives inside the repository, under the catalog directory
(`<repo>/<catalog_dir>/catalog/`). Never write under `.claude/`.

## Constraint schema

Each constraint is one atomic requirement. During extraction, an agent writes a
**JSON array** of these objects to its assigned shard file
(`catalog/.shards/<framework>-<key>.json`) — nothing else, no prose around it:

```json
[
  {
    "id": "GDPR-ART32-01",
    "framework": "gdpr",
    "title": "Encryption of personal data at rest and in transit",
    "requirement": "Personal data must be protected with appropriate technical measures such as encryption, matched to the risk of the processing.",
    "applies_when": "The system stores or transmits personal data (PII).",
    "check": "Verify the plan specifies encryption (or an equivalent risk-matched measure) for every store/transport of personal data.",
    "source_ref": "GDPR Art. 32(1)(a)",
    "mandatory": true
  }
]
```

Field rules:

- `id` — `<FW>-<SECTION>-<NN>`, uppercase, zero-padded ordinal within the section.
  Frameworks: `GDPR` (`GDPR-ART5-01`), `SOC2` (`SOC2-CC6-03`), `ISO` (`ISO-A8-12`).
  IDs are **stable**: the same requirement keeps the same id across re-extractions.
- `framework` — one of `gdpr`, `soc2`, `iso27001`.
- `title` — a short, imperative capability name (a "feature").
- `requirement` — one or two sentences, paraphrased, stating what must be true.
- `applies_when` — the precondition that makes this constraint relevant to a given
  system/plan. Write it so a validator can decide applicability (e.g. "handles PII",
  "exposes a public API", "runs multi-tenant"). Use `"Always"` for baseline duties.
- `check` — how to verify a plan/system satisfies it, phrased as an action.
- `source_ref` — the official article/control identifier (paraphrase, not full text).
- `mandatory` — `true` for baseline/legal duties; `false` for conditional or
  criteria that only apply to opted-in trust categories. Default `true` if unsure.

## Extraction rules (framework shard → constraints)

1. Read your shard's `title` and `scope_hint`; stay within that slice — other agents
   own the rest. Do not duplicate constraints outside your scope.
2. Produce **atomic** constraints: one testable requirement each. Split compound
   articles/controls into separate constraints.
3. Aim for **5–15** constraints per shard — coverage over volume, but no padding.
4. Assign ids sequentially within the section (`-01`, `-02`, …). Keep them stable.
5. Paraphrase; never paste verbatim standard text (see the copyright boundary).
6. Write **only** the JSON array to `catalog/.shards/<framework>-<key>.json` using
   the Write tool. Do not write any other file. Do not print the JSON as prose.
7. Emit valid JSON (double quotes, no trailing commas, no comments).

## Validation rules (PRP plan → report)

Given a plan file and the catalog, the validator agent:

1. Reads the plan and infers the system's characteristics (does it handle PII? is it
   multi-tenant? public API? stores audit logs?).
2. Selects the constraints whose `applies_when` matches those characteristics.
3. For each applicable **mandatory** constraint, decides `addressed` /
   `unaddressed` / `unclear` by reasoning over the plan (its `check` field guides
   this), citing the plan section that satisfies it when addressed.
4. Writes a report to `reports/<plan-stem>.md`: a summary line, then a table of
   applicable mandatory constraints with status + evidence/gap, then a short list of
   recommended additions. Be specific and cite constraint ids.
5. Never fails a plan for an inapplicable constraint. Advisory, not a certification.

## Capability validation rules (PRP plan → capability verdict)

Beside the constraint report, the validator decides which derived **capabilities** a
plan makes applicable. Constraints answer "what must be proven"; capabilities answer
"what must be built", so a plan is checked at both levels.

A plan declares the capabilities it delivers with one line in its `## Compliance`
section, using the `<framework>/<capability-slug>` keys listed in `capabilities.md`:

```markdown
**Capabilities**: gdpr/immutable-audit-logging, soc2/change-management
```

A plan with no compliance surface declares that explicitly, with a reason:

```markdown
**Capabilities**: none — internal batch script, no personal data, no runtime surface
```

The declaration runs to the next blank line, so a long list may wrap. Everything else
in the section stays free prose.

Given the plan, the capability catalog, and the declared keys, the validator agent:

1. Decides which capability keys the plan makes applicable **from the plan's own
   content**, not from its declaration. A plan that stores personal data makes the
   data-protection capabilities applicable whether or not it says so; a plan that
   declares a capability it does not deliver does not make it applicable.
2. Copies every key **verbatim** from the supplied capability catalog. Inventing a key
   is an error — an unknown key is discarded before the verdict is computed.
3. Writes **only** this JSON to `reports/<plan-stem>.capabilities.json` using the Write
   tool: `{"applicable": ["<key>", …], "reasoning": "<one or two sentences>"}`. An
   empty list is a valid verdict.
4. Closes the markdown report with a short `Capabilities` section naming the applicable
   keys and which of them the plan does not declare.

`validate.py` — not the agent — then computes `applicable ∩ mandatory-linked −
declared` and exits non-zero when that set is non-empty. Judge applicability honestly:
the deterministic hook check is advisory, so this verdict is the enforcing one, and
softening it to avoid failing someone is the one way this check becomes worthless.

## Capability derivation (constraints → capabilities → stack)

`capabilities.py` distils the extracted constraints into per-framework
**capabilities** and maps them to a greenfield-2026 stack. Agents follow this:

1. A **capability** is a concrete technical building block a new system implements
   to satisfy constraints (e.g. "immutable audit logging", "data-subject request
   handling", "encryption in transit") — not a restatement of a control.
2. **Per-framework lists, overlap kept** — do not merge capabilities across
   frameworks; each framework is audited on its own.
3. Every constraint id maps to **exactly one** capability's `satisfies` list — drop
   none, duplicate none. A deterministic gate fails the run if any mandatory
   constraint is uncovered.
4. Each capability's `category` is one of: IAM, Data Protection, Logging &
   Monitoring, Incident & Vulnerability, Governance & Privacy Ops, Change & SDLC,
   Infrastructure & Network, Vendor & Third-Party, Business Continuity.
5. **Stack** recommendations are current (2025-2026) components — 2-4 per
   capability, each marked `open-source` or `managed`, with a one-line rationale.
6. Write **only** the JSON to `catalog/.shards/cap-<framework>.json` (cluster) or
   `catalog/.shards/stack-<slug>.json` (stack) using the Write tool. Nothing else.

## Index — `catalog/index.md`

Rebuilt by `extract.py` after a run (not hand-authored). One row per framework:

```markdown
# Compliance Catalog

| Framework | Constraints | Mandatory | Generated |
|-----------|-------------|-----------|-----------|
| gdpr | 42 | 39 | 2026-07-02 |
```

## Conventions

- Dates ISO 8601 (`YYYY-MM-DD`); timestamps full ISO with offset.
- File names lowercase, hyphenated.
- Writing style: factual, neutral, instructive.
- This tooling is advisory. It flags likely compliance gaps; it is not legal advice
  and does not constitute certification.
