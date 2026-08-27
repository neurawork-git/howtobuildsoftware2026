# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-kb-researcher-on-prd-research/.claude/PRPs/plans/kb-researcher-on-prd-research.plan.md`
**Branch:** `feature/kb-researcher-on-prd-research` (worktree `/home/felix/projects/howtobuildsoftware2026-kb-researcher-on-prd-research`)
**Status:** `COMPLETE`

## Outcome

A PRP research workflow now spawns a fourth research axis without the operator asking
for it. Two new `knowledge-compiler` payload hooks inject one shared directive naming
`neurawork-cc-harness:kb-researcher` and the resolved absolute knowledge dir:

- `payload/hooks/user-prompt-submit.py` — the typed `/prp-prd|plan|debug` path.
- `payload/hooks/pre-skill.py` — the model-invoked `Skill` path, registered under a
  `matcher: "Skill"` group so it does not fire on every tool call.

Both render from `payload/scripts/research_directive.py`, so the two paths cannot drift.
`_shared/settings.py` grew optional matcher support (5-tuple; 4-tuples unchanged) to make
that group reachable from an installer. `plugins/neurawork-cc-harness/agents/kb-researcher.md`
is the plugin's first exported agent: read-only (`Read, Grep, Glob`), retrieving
index-first and then **by backlinks** — the only route to this corpus's `connections/`
layer. Three config keys (`research_directive`, `research_skill_match`,
`research_prompt_match`) make the trigger and its kill switch editable live.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s _shared/tests` | passed | Ran 44 tests, OK (3 new matcher-group tests) |
| `python3 -m unittest discover -s knowledge-compiler/tests` | passed | Ran 36 tests, OK (18 new: directive, both hook decisions, install) |
| `python3 -m unittest discover -s claudemd-lerner/tests` | passed | Ran 30 tests, OK |
| `python3 -m unittest discover -s compliance-compiler/tests` | passed | Ran 131 tests, OK |
| `python3 -m unittest discover -s stack-compiler/tests` | passed | Ran 189 tests, OK |
| `python3 -m unittest discover -s tests` (plugin root) | passed | Ran 15 tests, OK |
| `uvx ruff check` (from `engines/`) | see deviation 3 | 144 errors vs. a 142-error baseline on `main`; both new are `RUF100` on the repo-wide `# noqa: E402` idiom |
| `pre-skill.py` ← `{"tool_name":"Skill","tool_input":{"skill":"prp-core:prp-prd"}}` | passed | one JSON object naming `neurawork-cc-harness:kb-researcher` and the absolute kdir; exit 0 |
| `pre-skill.py` ← `prp-core:prp-prd-update` / `tool_name: "Bash"` / `skill: ""` | passed | no output, exit 0 in all three |
| `user-prompt-submit.py` ← `{"prompt":"/prp-prd a new thing"}` | passed | one `UserPromptSubmit` JSON object |
| `user-prompt-submit.py` ← `/prp-commit` / `see /prp-prd for context` | passed | no output, exit 0 |
| `"research_directive": false` in `knowledge-base/config.json`, both hooks re-fed | passed | no output from either, exit 0; restored afterwards |
| `git diff .claude/settings.json` | passed | additive only — no removed lines; new `PreToolUse` group has `matcher: "Skill"`; existing groups verbatim |
| `uv run --directory knowledge-base python scripts/lint.py --structural-only` | passed | `Broken links: 0`, `Orphan pages: 2` — corpus unchanged |
| Backlink route (AC3 mechanism) | passed | forward links from `concepts/api-key-vs-subscription-for-account-apps.md` reach only two concepts + a daily log; `grep -rl '\[\[concepts/api-key-vs-subscription-for-account-apps\]\]'` additionally returns `connections/sdk-subprocess-forces-api-key.md` |
| Task 11 manual probes (typed path, model-invoked path, agent-level AC3, negative control) | **not run** | see Completion Gate |

## Deviations and Decisions

1. **The two match patterns live in `research_directive.py`, not as literals in
   `config.py`.** The plan put them in `DEFAULT_CFG`. `research_enabled()` needs a
   module-level fallback for an uncompilable user regex, so two literals in two modules
   would be a drift pair. `config.py` imports them; `config.default.json` still carries
   the JSON copy a fresh install writes, and a new test asserts every shipped
   `config.default.json` value equals its `DEFAULT_CFG` counterpart.

2. **Running the installer also refreshed pre-existing drift in the self-host install.**
   `_copy_code()` refreshes all of `_shared/`, which brought `knowledge-base/_shared/`
   up to date — including two `_shared/tests/` files (`test_manifest.py`,
   `test_version_check.py`) the installed copy never had. Unrelated to this change,
   correct per the "single source of truth" rule, and included so payload and self-host
   do not drift.

3. **`uvx ruff check` from `engines/` was never clean.** Baseline on `main` is 142
   errors; this branch is 144. Both additions are `RUF100 unused-noqa` on the
   `# noqa: E402` idiom the repo uses in 16 other places — the invocation does not pick
   up the per-directory `pyproject.toml` configs. No new error of any other kind, and
   nothing in the changed non-test files (`settings.py`, `config.py`,
   `research_directive.py`, both hooks).

4. **Documentation touched six files, not four.** The plan named
   `skills/knowledge-compiler/SKILL.md`, `knowledge-base/CLAUDE.md`, root `CLAUDE.md`
   and `docs/ARCHITECTURE.md`. `docs/INSTALL.md` ("merges three hooks", "the three
   hooks") and `plugins/CLAUDE.md` (layout listing, which had no `agents/` entry) were
   made false by the change and were corrected too.

5. **The orphaned `connections/` articles were left alone**, per the plan's Agent Notes.
   `lint --structural-only` still reports `Orphan pages: 2` — the state AC3 depends on.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` for tasks 1-10. Task 11 is manual by construction.
- **Acceptance criteria satisfied:** `AC4, AC5, AC6, AC7 fully. AC1, AC2, AC3 at the
  mechanism level; their end-to-end probes are pending.`
- **Unresolved blocker:** `None for the code. Task 11 cannot run in this session: it
  requires a session where the plugin exports the new agent. The plugin loads from
  ~/.claude/plugins/cache/neurawork-harness/neurawork-cc-harness/0.2.0/, so
  agents/kb-researcher.md is not resolvable as neurawork-cc-harness:kb-researcher until
  this branch is merged and the marketplace install updated — not a /reload-plugins away.`
- **Recovery:** `After merge, update the plugin install, then run the four probes from
  plan task 11 in a fresh session in the main checkout: (1) type "/prp-prd a throwaway
  idea" and confirm the directive appears and the fan-out includes
  neurawork-cc-harness:kb-researcher in the same message; (2) ask in prose for a
  prp-plan so the model invokes the Skill tool, same directive; (3) spawn the agent on
  "what do we know about using an API key versus a subscription login" and require
  knowledge-base/knowledge/connections/sdk-subprocess-forces-api-key.md plus the
  concept whose backlinks led there; (4) type "/prp-commit" and confirm no directive.
  If probe 3 fails, fix agents/kb-researcher.md step 4, not the hooks.`

## Intended Commit Scope

One coherent outcome: the kb-researcher spawn directive and the agent it names.

- `engines/_shared/settings.py` + its tests — optional matcher support.
- `engines/knowledge-compiler/payload/{hooks/user-prompt-submit.py,hooks/pre-skill.py,scripts/research_directive.py}` and `payload/scripts/config.py`.
- `engines/knowledge-compiler/{install.py,config.default.json}` + `tests/{test_install_recon.py,test_research_directive.py}`.
- `plugins/neurawork-cc-harness/agents/kb-researcher.md`.
- Self-host refresh: `knowledge-base/{hooks,scripts,_shared}/…` and `.claude/settings.json`.
- Docs: root `CLAUDE.md`, `plugins/CLAUDE.md`, `knowledge-base/CLAUDE.md`,
  `docs/ARCHITECTURE.md`, `docs/INSTALL.md`,
  `plugins/neurawork-cc-harness/skills/knowledge-compiler/SKILL.md`.

## Delivery

- **Commits:** `4d757a7 — feat(knowledge-compiler): a PRP research workflow now consults the knowledge base`
- **Pull Request:** `https://github.com/neurawork-git/howtobuildsoftware2026/pull/37`
- **Base / Head:** `main <- feature/kb-researcher-on-prd-research`
- **Source PRD:** `None`
- **Tracked follow-ups:** `None`
