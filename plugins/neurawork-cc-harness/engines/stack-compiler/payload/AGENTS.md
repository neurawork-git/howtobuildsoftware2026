# AGENTS.md — Stack Compiler Constitution

The rules every scoping, challenge and ranking agent follows. `scripts/scope.py`
and `scripts/rank.py` read this file verbatim into each agent prompt, so this
document *is* the specification — not a description of one.

## The model

The compliance capability catalog (`<compliance_dir>/catalog/capabilities.json`)
describes what *any* compliant product might need. A given product needs a subset.
This engine records that subset — and, just as importantly, records what was left
out and why.

Three fixed terms:

- **capability** — a compliance-derived technical building block ("immutable audit
  logging"). Owned by `compliance-compiler`.
- **component** — a concrete OSS project that can deliver a capability. Owned by
  `compliance-compiler`. **Not this engine's concern at the scoping stage**; at the
  ranking stage it becomes one, but only to order the components the catalog
  already lists — never to add, remove or invent one.
- **applicability** — whether *this* product must implement a capability at all.
  The scoping pass's output.
- **ranking** — the order in which an applicable capability's components fit *this*
  product, with a reason per position. The ranking pass's output. It is an
  ordering, never a selection: the human fixes `chosen` afterwards.

## Scoping rules

1. **The key set is closed.** Every capability handed to an agent carries a `key`
   from `catalog/stack.json`. Decide on exactly those keys — every one of them,
   and no others. Inventing a key, dropping a key, or renaming one fails the run.
2. **Every capability gets an explicit decision.** There is no "skip", no "unclear",
   no empty answer. A capability with no decision is the silent omission this
   engine exists to prevent.
3. **A "not applicable" needs a reason grounded in the product description.** The
   reason must name the property of *this product* that makes the capability
   unnecessary — "the service never stores personal data", "there is no end-user
   login", "no data leaves the operator's own machine". Not "probably out of
   scope", not "can be added later", not "expensive".
4. **When in doubt, applicable.** An unnecessary capability costs a component
   choice. A wrongly-dropped one costs a compliance breach. The asymmetry is the
   whole point.
5. **Cost, effort and team size are never grounds for a drop.** They are reasons to
   sequence work, not to leave a mandatory constraint uncovered.
6. **Never decide from the capability name alone.** Read its description and the
   product description, and decide against what the product actually does with data
   and users.
7. **A mandatory-linked capability is ruled out only when the product genuinely
   cannot trigger the underlying obligation** — not when the obligation is merely
   inconvenient or currently unimplemented. "We have not built it yet" means
   applicable, not inapplicable.

## Challenge rules

The challenge pass re-reads the product description against every "not applicable"
decision. Its job is to catch a well-worded reason that the description itself
contradicts.

1. **Refute only from the product description.** Outside knowledge about the
   regulation is not evidence about this product.
2. **Quote the contradicting sentence.** A refutation without a verbatim quote from
   the product description is not a refutation. `evidence` carries that quote.
3. **A vague or general reason is not by itself a refutation.** Refute when the text
   says something incompatible with the claim — the description stores user emails
   while the reason says no personal data is processed — not when the reason is
   merely thin.
4. **Do not re-litigate applicable decisions.** Only "not applicable" claims are in
   the challenge set.
5. **Refuting is cheap; being wrong is not.** A refuted run writes nothing and the
   engineer fixes either the description or the decision. Prefer refuting a claim
   you cannot verify from the text over letting a false one through.

## Ranking rules

The ranking pass runs after scoping, over the capabilities that survived it. For
each one it orders that capability's components best-fit-first for this product.

1. **The component pool is closed and complete.** Every component listed under a
   capability must appear in its ranking, exactly once, spelled exactly as given.
   Adding one, dropping one, or renaming one fails the run. Narrowing the pool is
   the catalog's decision and the human's at selection time — never the agent's.
2. **Rank on fit to *this* product.** Deployment shape, the data actually held, the
   integrations named, the stated non-goals. General popularity, GitHub stars and
   "industry standard" are not reasons; they say nothing about this product.
3. **Every position needs a reason.** One factual sentence naming why that component
   sits where it does *for this product*. Restating the component's catalog `why`
   text back is not a reason. A blank rationale fails the run.
4. **`verdict: "replaced"` means superseded, not rejected.** During the license audit
   that component took the place of the one in `replaced_from`. It is a live
   candidate like any other and is ranked on its merits.
5. **Never silently drop a component that looks license-incompatible.** Licenses are
   checked deterministically after the run, against the catalog's own
   `license_policy`. Rank such a component last and say so in its reason; the gate
   decides whether it is a real violation or a recorded exception.
6. **Do not re-litigate applicability.** A capability reaching the ranking pass has
   already been decided as applicable. Rank it; do not argue it away.

## Gate rules

The gate pass runs after a PRD or PRP plan is written, over the components that
document names. It reads the recorded stack back; it never decides it.

1. **The component pool is closed.** Only components the precheck lists exist for
   this pass. Never name one the catalog does not carry, and never invent a
   spelling — a name that is not in the precheck is not a finding.
2. **A mention is not a proposal.** A comparison, a prior-art note, an example, or
   a description of what the repository already runs names a component without
   proposing it. Only a proposal counts, and only proposals reach the verdict.
3. **Never re-litigate a recorded decision.** Applicability was decided by the
   scoping pass and the chosen component by a human at selection. Report the
   contradiction — "this document proposes X where `<key>` records Y" — and stop
   there; do not argue that Y was the wrong choice.
4. **Name an ignored capability by its key.** Only keys from the applicable list in
   the prompt, copied verbatim. A capability the document plainly needs and never
   addresses is the finding; a capability it had no reason to touch is not.
5. **Write exactly the two files named in the prompt** — the markdown report and
   the JSON verdict — and nothing else. (The single-JSON-file rule below governs the
   scoping and ranking passes.)
6. **This pass changes nothing.** It never edits `stack.json` or
   `capabilities.json`, and it never proposes a component itself: it reads a
   document and reports what the recorded stack says about it.

## Output rules

- Write **exactly one** JSON file, to exactly the path named in the prompt, with
  the Write tool. No prose, no extra files, no commentary in the file.
- Valid JSON: double quotes, no trailing commas, no comments.
- Reasons are one sentence, factual, and specific to this product. No hedging, no
  restating the capability description back.

## Boundaries

- This engine **never** writes `stack.json` directly. Decisions are applied through
  `<compliance_dir>/scripts/stack.py` — `--apply-scope` for applicability,
  `--apply-ranking` for the component order, `--apply-selection` for the chosen
  component — the one schema owner.
- **No agent ever picks a component.** Ranking proposes an order and stops there.
  `chosen` and `rationale` are written only by the selection pass
  (`scripts/selection.py`), which runs no agent at all: it renders the recorded
  ranking as a sheet, a human writes the choice, and a deterministic gate checks it
  against the closed pool before the write.
- This engine **never** edits `capabilities.json`. A component whose license the
  policy forbids is a catalog finding, reported by the ranking gate and fixed in
  `compliance-compiler`.
- Machinery output stays inside the repo, never under `.claude/`.
