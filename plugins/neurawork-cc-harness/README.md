# neurawork-cc-harness

A Claude Code plugin that keeps a repo's project knowledge fresh and carries a change from
worktree to merged PR. Everything it produces — knowledge, docs, the compliance catalog — is
written **inside the repo**, never under `.claude/`, so it is tracked and reviewable.

**Install & upgrade guide:** [`../../docs/INSTALL.md`](../../docs/INSTALL.md).
**Architecture:** [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md).
**Release notes:** [`CHANGELOG.md`](CHANGELOG.md).

## Four independently installable skills

Each installs into its own directory in the target repo, registers hooks under its own
filename prefix so the four coexist in one `.claude/settings.json`, runs an interactive
**recon** on install, and can **seed** from an existing repo. Re-running an installer is an
ADOPT: code and hooks are refreshed, existing data is left alone.

| Skill | Install dir (default) | Hook prefix | Produces |
|-------|-----------------------|-------------|----------|
| `knowledge-compiler` | `knowledge-base/` | *(none)* | `knowledge/concepts/`, `knowledge/connections/`, `knowledge/index.md` |
| `claudemd-lerner` | `claudemd-lerner/` | `cl-` | the repo-root `CLAUDE.md` hierarchy + `docs/` |
| `compliance-compiler` | `compliance-base/` | `co-` | `catalog/*.json` + `index.md`, `capabilities.{json,md}`, `stack.json` |
| `stack-compiler` | `stack-base/` | `st-` | no artifact of its own — it records the chosen components into `compliance-base/catalog/stack.json` |

- **`knowledge-compiler`** — captures session transcripts into per-repo `daily/` logs and
  compiles them into a knowledge wiki. Five hooks: `SessionStart` / `PreCompact` /
  `SessionEnd` capture and inject, and `UserPromptSubmit` + `PreToolUse` (matcher `Skill`)
  inject one directive that spawns the `kb-researcher` agent when a PRP research workflow
  starts. Two hooks for one directive because a typed `/prp-prd` is visible only to
  `UserPromptSubmit` and a model-invoked one only to `PreToolUse`.
- **`claudemd-lerner`** — learns from each session (git diff + conversation) and keeps the
  **CLAUDE.md hierarchy + `docs/`** current. No knowledge wiki. It snapshots every
  `owner:name` marker span before its run and restores it byte-for-byte afterwards, so a
  tool-owned block is never silently reworded.
- **`compliance-compiler`** — ~30 parallel SDK agents distil GDPR/SOC 2/ISO 27001 into a
  catalog of atomic constraints, derive the capabilities those constraints require, and
  scaffold the component stack. One `PostToolUse` hook (matcher `Write|Edit|MultiEdit`)
  validates each PRP plan write against the catalog. The catalog ships prebuilt, so a fresh
  install validates without an LLM run.
- **`stack-compiler`** — narrows that catalog to one product: parallel agents decide which
  capabilities apply and why (`scope`), order each one's components best-fit-first (`rank`),
  and a human records the chosen component from that closed pool (`selection`, no agent, no
  API key). One `PostToolUse` hook (matcher `Write|Edit|MultiEdit`) then gates every PRD and
  plan write against those choices. It owns no data artifact — every write goes through
  `compliance-base/scripts/stack.py`, the single schema owner.

## Three install-free workflow surfaces

Prompt-only. They copy nothing into a repo and have no engine.

- **`/nw-worktree`** — create and enter a Hand worktree (sibling of the repo root).
- **`/nw-ship-pr`** — commit → push → PR → parallel workflow review → validation gate →
  explanation → approval gate → follow-up capture → merge → branch cleanup. Its review
  fan-out is `workflows/nw-ship-pr-review.js`.
- **`/nw-rules-init`** — write the baseline coding rules (scope, simplicity,
  evaluation-first with the repo's own test command) into the root `CLAUDE.md` as a
  marker-delimited, idempotent block. `claudemd-lerner` guards that span.

## One agent

- **`neurawork-cc-harness:kb-researcher`** — read-only (`Read, Grep, Glob`). Retrieves from a
  compiled knowledge base index-first and then **by backlinks**, which is the only route into
  the `connections/` layer. It is the fourth research axis next to codebase-explorer,
  codebase-analyst and web-researcher.

## Slash commands

| Command | Does |
|---------|------|
| `/neurawork-cc-harness:kc-compile` | distil the pending `daily/` logs into `knowledge/` |
| `/neurawork-cc-harness:cl-update` | apply the pending `daily/` logs to `CLAUDE.md` + `docs/` |
| `/neurawork-cc-harness:co-extract` | rebuild the constraint catalog from the frameworks |
| `/neurawork-cc-harness:co-capabilities` | derive the capability layer + stack scaffold |
| `/neurawork-cc-harness:co-validate` | check a PRP plan against the catalog |
| `/neurawork-cc-harness:st-scope` | decide which capabilities apply to this product |
| `/neurawork-cc-harness:st-rank` | order each applicable capability's components |
| `/neurawork-cc-harness:st-select` | render the selection sheet, then record the choices |
| `/neurawork-cc-harness:st-validate` | check a PRD or plan against the chosen stack |
| `/neurawork-cc-harness:nw-ship-pr` | the PR lifecycle above |

`/nw-worktree` and `/nw-rules-init` are skills, invoked by name.

**Always invoke by the fully-qualified `neurawork-cc-harness:<name>` form** so an install
resolves to this plugin regardless of what else is enabled.

## Status

The live record is the phase table in each PRD, not this file:

- [`.claude/PRPs/prds/neurawork-cc-harness.prd.md`](../../.claude/PRPs/prds/neurawork-cc-harness.prd.md) — the three installable skills.
- [`.claude/PRPs/prds/stack-compiler.prd.md`](../../.claude/PRPs/prds/stack-compiler.prd.md) — `stack-compiler`, including the Phase 5 installer.

## Shared infrastructure

`engines/_shared/` is the single source of truth for the stdlib-only helpers every engine
reuses; each install refreshes its copied `_shared/` rather than diverging.

| Module | Purpose |
|--------|---------|
| `hookio.py` | Parse hook stdin (Windows-safe) + recursion guard |
| `transcript.py` | Read a JSONL transcript → recent markdown turns |
| `gitctx.py` | Worktree detection + state redirect to main checkout |
| `settings.py` | Idempotent `.claude/settings.json` hook merge + `.gitignore` merge |
| `repo_guard.py` | Enforce: knowledge/docs in-repo, never under `.claude/` |
| `recon.py` | Git-root resolution + `RECON_JSON` emit for install recon |

## License

MIT — see `LICENSE`.
