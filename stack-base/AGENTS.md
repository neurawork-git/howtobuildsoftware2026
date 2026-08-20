# AGENTS.md — Stack Compiler Constitution

The rules every scoping and challenge agent follows. `scripts/scope.py` reads this
file verbatim into each agent prompt, so this document *is* the specification —
not a description of one.

## The model

The compliance capability catalog (`<compliance_dir>/catalog/capabilities.json`)
describes what *any* compliant product might need. A given product needs a subset.
This engine records that subset — and, just as importantly, records what was left
out and why.

Three fixed terms:

- **capability** — a compliance-derived technical building block ("immutable audit
  logging"). Owned by `compliance-compiler`.
- **component** — a concrete OSS project that can deliver a capability. Owned by
  `compliance-compiler`. **Not this engine's concern at the scoping stage.**
- **applicability** — whether *this* product must implement a capability at all.
  This engine's only output.

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

## Output rules

- Write **exactly one** JSON file, to exactly the path named in the prompt, with
  the Write tool. No prose, no extra files, no commentary in the file.
- Valid JSON: double quotes, no trailing commas, no comments.
- Reasons are one sentence, factual, and specific to this product. No hedging, no
  restating the capability description back.

## Boundaries

- This engine **never** writes `stack.json` directly. Decisions are applied through
  `<compliance_dir>/scripts/stack.py --apply-scope`, the one schema owner.
- This engine **never** picks a component and never touches `chosen` or
  `rationale`. Ranking and selection are separate passes with their own gates.
- Machinery output stays inside the repo, never under `.claude/`.
