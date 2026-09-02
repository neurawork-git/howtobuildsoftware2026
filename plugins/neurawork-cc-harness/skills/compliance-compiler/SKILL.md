---
name: compliance-compiler
description: Install a per-repo compliance catalog + PRP-plan validator into the current repository. Parallel agents distil GDPR/DSGVO, SOC 2, and ISO 27001 into a tracked catalog of atomic constraints ("features"); a PostToolUse hook then checks every PRP plan (.claude/PRPs/plans/*.plan.md) against it. Trigger when the user says "compliance compiler", "install compliance compiler", "compliance catalog", "GDPR/SOC2/ISO catalog", "compliance einrichten", "validate plans against compliance", or wants a repo-local, self-checking compliance baseline.
---

# Compliance Compiler — Install Skill

Installs the compliance-compiler engine into the current repo. Three parts:

1. **Extraction** — `scripts/extract.py` fans out ~30 parallel Claude Agent SDK
   agents (one per framework shard) that distil GDPR/DSGVO, SOC 2, and ISO 27001
   into `<catalog_dir>/catalog/{gdpr,soc2,iso27001}.json` — atomic constraints with
   an `applies_when` predicate and a `check`.
2. **Capability layer** — `scripts/capabilities.py` clusters those constraints into
   per-framework **capabilities** (concrete building blocks, each carrying the
   constraint ids it satisfies and 2-5 recommended stack components) in
   `<catalog_dir>/catalog/capabilities.{json,md}`, failing when a mandatory constraint
   is covered by none. `scripts/stack.py` keeps `catalog/stack.json` — which component
   was actually chosen per capability — plus a gap report of the undecided ones.
3. **Validation** — a `PostToolUse` hook checks each PRP plan file as it is written: a
   fast structural precheck inline, plus a detached deep LLM report in
   `<catalog_dir>/reports/`. Both the mandatory constraints and the plan's declared
   capabilities are checked. Two locations count — `.claude/PRPs/plans/*.plan.md` and
   the store layout `.claude/PRPs/<repo>-<hash>/plans/*.plan.md` — and the install wires
   the store into the repo (a symlink `~/.prp/<repo>-<hash>` → `<main-checkout>/.claude/PRPs`,
   `PRP_HOME` as the fallback) so prp-core writes there instead of `~/.prp`.

The catalog always lives inside the repo, never under `.claude/`.

## Authentication

Extraction and deep validation use the Claude Agent SDK, which needs
`ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`). Subscription credentials are NOT
sanctioned for third-party plugins — public/customer installs must set an API key.
Install, scaffolding, hooks, and the inline structural precheck work without it.

## Copyright note

ISO 27001 and SOC 2 standard text is copyrighted. The catalog stores official
control identifiers + short titles + a **paraphrased** requirement, never verbatim
text. Supply source text locally if you want higher-fidelity extraction.

## Naming / collision note

Invoke this as `neurawork-cc-harness:compliance-compiler`. Its hooks are `co-`
prefixed and it uses the `PostToolUse` event, so it coexists with the harness's
`knowledge-compiler` and `claudemd-lerner` in one `.claude/settings.json`.

## Phase A — Recon (read-only)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/compliance-compiler/recon.py"
```

- `status: NOT_A_GIT_REPO` → stop; tell the user to run inside a git repo.
- `existing_dir` set → ADOPT (refresh) install; reuse that name.
- Note `catalog_built`, `existing_hooks`, `timezone`, `clean`.

## Phase B — Ask

Use AskUserQuestion to confirm:
1. **Catalog dir name** — default `compliance-base` (or the detected `existing_dir`).
2. **Frameworks** — default all three (`gdpr`, `soc2`, `iso27001`); allow a subset.
3. **Extract now?** — offer only when the tree is clean; extraction makes API calls
   and runs ~30 agents.

## Phase C — Execute

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/compliance-compiler/install.py" \
  --catalog-dir <NAME> [--extract]
uv sync --directory <NAME>
```

Then tell the user to commit `<NAME>/` and `.claude/settings.json`. After install:
- The catalog, the derived capabilities and `catalog/stack.json` are all in place — no
  LLM run needed to reach a usable state; report any line the installer printed about a
  skipped stack scaffold, or about how the PRP store was wired (linked, or fallen back
  to `PRP_HOME` because the store key was occupied).
- Every PRP plan write is checked automatically.
- Manual extract: `/neurawork-cc-harness:co-extract`.
- Re-derive the capability layer + stack scaffold:
  `/neurawork-cc-harness:co-capabilities`.
- Manual validate: `/neurawork-cc-harness:co-validate <plan>`.
