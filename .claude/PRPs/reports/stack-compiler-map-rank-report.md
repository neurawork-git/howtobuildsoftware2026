# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-stack-compiler-map-rank/.claude/PRPs/plans/stack-compiler-map-rank.plan.md`
**Branch:** `feature/stack-compiler-map-rank`
**Status:** `COMPLETE`

## Outcome

`stack-compiler` gained its second pass. `stack-base/scripts/rank.py` reads the same
tracked `product.md` the scoping pass used, fans out one SDK agent per framework over the
41 capabilities that survived scoping, and orders each one's catalog components
best-fit-first with a product-specific reason per position. A purely deterministic gate
(`rank_lib.ranking_gate`) runs before any write; only a clean gate reaches
`compliance-base/scripts/stack.py --apply-ranking`, the single schema owner, which
validates the same invariants independently.

`compliance-base/catalog/stack.json` now carries `ranked` and `ranked_from` on all 68
entries — 151 ordered components across the 41 applicable capabilities, `null` on the 27
scoped-out ones. `chosen` and `rationale` are untouched, so Phase 3 opens on a pre-ordered,
pre-justified shortlist instead of the undifferentiated pool the catalog started with.

The live run recorded exactly one license exception (OWASP ASVS 5.0, `CC-BY-SA-4.0`, under
`iso27001/secure-development-lifecycle-secure-coding`) and zero violations, matching the
plan's measurement. The ranking agent followed the constitution's license rule: it placed
ASVS last and named the share-alike terms in its rationale rather than dropping it.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s compliance-compiler/tests` | `passed` | Ran 104 tests, OK (was 103 before; `TestApplyRanking` + 2 `TestScaffold` cases added) |
| `python3 -m unittest discover -s stack-compiler/tests` | `passed` | Ran 92 tests, OK (was 66; `test_rank.py` + `test_rank_lib.py` added) |
| `python3 -m unittest discover -s _shared/tests` | `passed` | Ran 34 tests, OK |
| `python3 -m unittest discover -s knowledge-compiler/tests` | `passed` | Ran 15 tests, OK |
| `python3 -m unittest discover -s claudemd-lerner/tests` | `passed` | Ran 13 tests, OK |
| `uvx ruff check scripts/rank.py scripts/rank_lib.py` (stack-base) | `passed` | All checks passed! |
| `uvx ruff check scripts/stack.py` (compliance-base) | `passed` | All checks passed! |
| `uv run python scripts/rank.py --dry-run` | `passed` | `151 components across 41 applicable capabilities in 3 framework(s)`; gdpr 9/32, iso27001 15/58, soc2 17/61; no SDK call, exit 0 |
| `uv run python scripts/rank.py` (integrated) | `passed` | `41 capabilities ranked, 151 components ordered. Cost: $1.88.` … `1 component(s) ranked under a recorded license exception`; exit 0 |
| AC1 + AC2 script over the written `stack.json` | `passed` | 41 applicable / 27 scoped out, 151 ordered, single `ranked_from` `dbc748613f86f0e7`; every `ranked` set equals its `options`, no duplicates, no blank rationale; `chosen`/`rationale`/`options`/`applicable`/`applicability_reason`/`scoped_from` byte-identical to HEAD on all 68 entries |
| Uniform-schema check | `passed` | `entries with both keys: 68 / 68`; scoped-out `ranked` values are exactly `{null}` |
| Mirror diff (payload ↔ self-host, both engines) | `passed` | `AC6: all mirrors byte-identical` |
| `git diff --stat compliance-base/catalog/stack.json` | `passed` | one file changed |

## Deviations and Decisions

**One defect found and fixed during the plan's own Task 6 review.** The first
`apply_ranking` wrote `ranked`/`ranked_from` only onto entries present in the payload, so
the artifact came out with the keys on 41 entries and absent on the other 27. Every other
field in the schema is present on every entry, and Phases 3 and 4 read this file as a
contract, so a consumer doing `entry["ranked"]` would have hit a `KeyError` on the
scoped-out ones. `apply_ranking` now `setdefault`s both fields on untouched entries —
explicit `null`, never a missing key — and the already-written `stack.json` was normalised
by re-applying the existing shard (`--apply-ranking ../stack-base/.shards/rankings.json`),
with no second LLM run. `setdefault` rather than assignment, so a ranking recorded before a
capability was later scoped out survives instead of being silently discarded; both
behaviours have tests.

**`ranked` is a permutation of `options`, not a subset** — planned and unchanged, but worth
carrying forward: the measurement behind it is that `options` already holds min 2 / max 4 /
mean 3.7 components per applicable capability, so the catalog performed the narrowing the
PRD's "return 2–4 ranked options" describes. Set equality is the gate; there is deliberately
no drop-justification mechanism because nothing may be dropped.

**No adversarial challenge agent**, unlike the scoping pass. Every checkable claim here
(pool match, license policy) is decidable by set math, and the subjective part — the order —
has no ground truth for a second LLM to refute. One agent pass per framework, three total.

**License handling** is normalisation plus the catalog's own `verdict: "keep-exception"`:
`CC0-1.0` → `CC0`, `LGPL-*` → `LGPL (dynamic)`, anything still unmatched in an `in-product`
role fails the run unless the catalog already recorded the deviation. Measured against the
live catalog this yields 0 violations and 1 exception; without honouring `keep-exception` the
first real run would have failed on three components the catalog had already adjudicated.

**Deferred, as planned:** the PRD's `chosen: string` vs `string[]` open question (Phase 3
owns it; nothing in ranking depends on the answer) and per-capability staleness detection
(Phase 3's scope; `gaps()["stale"]` already flags whole-file catalog drift).

**Pre-existing, untouched:** `uvx ruff check` at `stack-base/` reports two `PLW1510`
findings in `_shared/gitctx.py:26` and `_shared/recon.py:26`, neither in code this change
touches — consistent with commit `73cc078`'s convention of clearing findings only in the
code a PR touches.

## Completion Gate

- **Plan tasks complete:** `Yes` — all six, in order.
- **Acceptance criteria satisfied:** `Yes` — AC1–AC6 each proven by a named check above.
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

The Map & rank pass, end to end:

- `compliance-base/scripts/stack.py` (+ payload mirror) — `ranked`/`ranked_from` in the
  `scaffold()` carry-over, `apply_ranking()`, the `--apply-ranking` flag and its `main()`
  branch, and the module docstring's schema contract.
- `stack-base/scripts/rank_lib.py` (+ payload mirror) — NEW: license normalisation and
  policy check, the rankable universe, the deterministic ranking gate, the apply payload,
  the report renderer.
- `stack-base/scripts/rank.py` (+ payload mirror) — NEW: CLI, preflight, per-framework SDK
  fan-out, shard parsing, gate, report, write-through, state.
- `stack-base/AGENTS.md` (+ payload mirror) — the Ranking rules section, the vocabulary
  entry for *ranking*, and the updated Boundaries block.
- `plugins/…/compliance-compiler/tests/test_stack.py`, `…/stack-compiler/tests/test_rank.py`,
  `…/stack-compiler/tests/test_rank_lib.py` — the tests for all of the above.
- `compliance-base/catalog/stack.json` — the self-host run's output.
- `CLAUDE.md` — the `rank.py` command and the two-pass `stack-base/` description.
- `.claude/PRPs/plans/stack-compiler-map-rank.plan.md` and the PRD's Phase 2 row.

## Delivery

- **Commits:** `ff89eea` feat(stack-compiler): order each applicable capability's components for this product; `4bcf05d` docs(prd): record Phase 2 implementation report and PR
- **Pull Request:** https://github.com/neurawork-git/howtobuildsoftware2026/pull/27 — open, ready for review
- **Base / Head:** `main <- feature/stack-compiler-map-rank`
- **Source PRD:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/prds/stack-compiler.prd.md`, Phase 2 — `in-progress`, now linking this report and PR #27
- **Tracked follow-ups:** `None`
