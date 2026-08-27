# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026/.claude/PRPs/plans/root-readme-landing-page.plan.md`
**Branch:** `feature/root-readme-landing-page`
**Status:** `COMPLETE`

## Outcome

`README.md` is now the harness's landing page rather than a partial install sheet. It is
restructured into reading order — what it is → install → before you start → the standard
workflow → command reference → deeper docs → sources → contributing → license — and the
inventory is complete against the tree:

- All **four** installable skills, each with its install directory, hook count and hook
  prefix, in one table.
- All **thirteen** command surfaces: nine install-skill commands (including the four
  `/st-*` passes) and four workflow surfaces (`/nw-worktree`, `/nw-ship-pr`,
  `/nw-rules-init`, `/nw-doctor`), plus the note that `nw-worktree` and `nw-rules-init`
  ship as skills with no `commands/` file, so only the fully qualified name always
  resolves.
- The `kb-researcher` agent gets its own subsection: read-only tool set, index-first then
  **backlink** walk (with the reason forward traversal cannot reach `connections/`), the
  two hooks that spawn it, the bounded trigger set (`/prp-plan`, `/prp-prd`, `/prp-debug`
  only, typed or model-invoked) and the `"research_directive": false` off-switch.
- A `## Before you start` section stating `prp-core` and the `gh` CLI as **requirements**
  with the concrete reason each is load-bearing, and the API-key requirement stated once,
  separating LLM paths from key-free paths.
- A six-stage workflow narrative plus the mermaid diagram showing the feedback edge — the
  knowledge a later `/prp-plan` reads was produced by earlier sessions.

No content from `docs/INSTALL.md` or `docs/ARCHITECTURE.md` is restated; both are linked.
The two prior recorded README decisions are preserved: the `/plugin` install commands stay
inline, and the user-install / contributor-clone split remains.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `grep -o -E '<20 surface tokens>' README.md \| sort -u` | passed | All 20 present: every command, `kb-researcher`, `stack-compiler`, `stack-base`, `backlink`, `research_directive`, `PRPs-agentic-eng`, `prp-core@prp-marketplace` |
| `grep -c '```mermaid' README.md` | passed | `1` |
| `grep -c 'ANTHROPIC_API_KEY' README.md` | passed | `1` — stated once |
| `grep -c 'github@claude-plugins-official' README.md` | passed | `0` — the false prerequisite is absent |
| `test -e docs/INSTALL.md && test -e docs/ARCHITECTURE.md && test -e LICENSE && test -e .claude/PRPs/prds/neurawork-cc-harness.prd.md` | passed | `links OK` |
| Anchor check | passed | `docs/INSTALL.md:264` `## Local development (working ON the plugin)`; `docs/ARCHITECTURE.md:124` `## Runtime: the fourth research axis` |
| `git diff --name-only` | passed | exactly `README.md` |
| `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | passed | `Ran 78 tests ... OK` |
| Manual truth pass against `ls plugins/neurawork-cc-harness/{skills,commands,agents,workflows,engines}` and `.claude/settings.json` | passed | 11 files in `commands/`, 6 in `skills/`, 1 agent, 1 workflow, 5 engine dirs incl. `_shared`; 10 hooks in `settings.json` (knowledge-base 5, claudemd-lerner 3, compliance-base 1, stack-base 1) |

Facts verified at write time rather than taken from the plan: `gh` invocation count in
`commands/nw-ship-pr.md` (18, zero `mcp__github`), `Wirasm/PRPs-agentic-eng` present in
`~/.claude/plugins/known_marketplaces.json`, `stack-base/scripts/selection.py` imports no
SDK (its `selection_lib.py` docstring states stdlib-only), plugin version `0.5.1`, and the
`research_directive.py` regexes at lines 32 and 39.

## Deviations and Decisions

1. **`stack-compiler` is installable now; the planned "Not installable yet" section was
   dropped.** The plan (Task 3, and its Scope section) was written when
   `engines/stack-compiler/` had no `install.py` and no `recon.py`, and instructed the
   README to say so. The tree now has both, plus `skills/stack-compiler/` and four
   `commands/st-*.md` — PRD Phase 5 shipped in PR #43. Writing the planned section would
   have put a false claim on the landing page, which is the exact failure the plan exists
   to end. `stack-compiler` is documented as the fourth installable skill instead, in the
   same install table and command table as the other three. The plan's outcome, invariant
   and acceptance intent are preserved; only the stale premise changed.
2. **Surface counts recomputed, as the plan required.** The plan predicted "four
   install-free surfaces against five install-skill commands". The tree now has four
   install-free surfaces and **nine** install-skill commands (the four `/st-*` passes are
   new). The sentence above the command table carries both numbers, in one place only.
3. **The plan's `## Status` recommendation was folded into `## Overview`** rather than kept
   as a standalone "🚧 Early stage" section: one line naming the shipping version (`0.5.1`)
   and linking the PRD phase table, which is the live record. No phase numbers are restated
   in the README.
4. **No marker block added to `README.md`** — per the plan's *Alternatives considered*.
   `claudemd-lerner`'s `markers.py` snapshots only `claudemds + docs`; a marker here would
   be restored by nothing.
5. **Hook matchers are not stated in the README.** The plan's Agent Notes flagged a
   disagreement about compliance's `co-` matcher; `.claude/settings.json` now shows both
   `co-` and `st-` under `Write|Edit|MultiEdit`, but the README states hook *counts and
   prefixes* only, so the question does not arise.

No contradiction found against
`.claude/PRPs/plans/harness-self-description-and-install-reach.plan.md:466-503` (the plugin
README's planned content); that file is untouched.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` (Tasks 1-4; Task 3's `stack-compiler` section delivered
  under the corrected premise — see Deviations)
- **Acceptance criteria satisfied:** `Yes` — AC1 (with the corrected engine count), AC2,
  AC3, AC4, AC5, AC6, AC7
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

`README.md` only — the full restructure into the landing page described above.

## Delivery

- **Commits:** `Not created`
- **Pull Request:** `Not opened`
- **Base / Head:** `main <- feature/root-readme-landing-page`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
