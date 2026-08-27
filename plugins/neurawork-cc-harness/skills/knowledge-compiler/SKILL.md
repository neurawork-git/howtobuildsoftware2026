---
name: knowledge-compiler
description: Install a per-repo, self-building knowledge base into the current repository. Captures Claude Code sessions into daily logs and compiles them into a queryable knowledge/ wiki (concepts + connections + index), injected back at session start. Trigger when the user says "knowledge compiler", "install knowledge compiler", "set up a knowledge base", "knowledge compiler einrichten", "distil my sessions into knowledge", or wants per-repo memory that builds itself and can seed from an existing repo.
---

# Knowledge Compiler — Install Skill

Installs the knowledge-compiler engine into the current repo: SessionEnd/PreCompact
hooks capture each session into `<kdir>/daily/`, a compiler distils those into
`<kdir>/knowledge/` (concepts, connections, index), and SessionStart injects the
index back. Compilation runs on a manual command or a 6-hour SessionStart gate.

Knowledge always lives inside the repo, never under `.claude/`.

## The five hooks

The install merges **five** hooks into `.claude/settings.json`:

| Event | Hook | Job |
|---|---|---|
| `SessionStart` | `hooks/session-start.py` | inject the index; maybe spawn a compile |
| `PreCompact` | `hooks/pre-compact.py` | capture before context is compacted |
| `SessionEnd` | `hooks/session-end.py` | capture the session into `daily/` |
| `UserPromptSubmit` | `hooks/user-prompt-submit.py` | spawn directive on a **typed** `/prp-prd\|plan\|debug` |
| `PreToolUse` (matcher `Skill`) | `hooks/pre-skill.py` | spawn directive on a **model-invoked** research skill |

The last two inject one shared directive (`scripts/research_directive.py`) telling the
session to spawn `neurawork-cc-harness:kb-researcher` — the **fourth research axis**,
next to `prp-core`'s `codebase-explorer`, `codebase-analyst` and `web-researcher` — so a
PRD or plan starts from what the repo already learned. Two hooks, because a skill is
entered by two paths and no single event sees both.

**`PreToolUse` must never exit non-zero: exit code 2 on that event blocks the tool
call.** Both hooks fail open — any exception yields no output and exit 0. The
`matcher: "Skill"` group is what keeps `pre-skill.py` from spawning a process on every
tool call; it never joins a `matcher: ""` group, and never collides with
`compliance-compiler`, which owns `PostToolUse`.

Three config keys in `<kdir>/config.json`, read live (no installer re-run):

- `research_directive` (default `true`) — the kill switch for both hooks.
- `research_skill_match` — matched against the plugin-qualified skill name.
- `research_prompt_match` — matched against the raw prompt, anchored at its start.

To remove the feature entirely instead of disabling it, delete the two hook entries
from `.claude/settings.json`.

## Authentication

The compiler uses the Claude Agent SDK, which needs `ANTHROPIC_API_KEY` (or
`CLAUDE_CODE_OAUTH_TOKEN`) in the environment. Subscription credentials are NOT
sanctioned for third-party plugins — public/customer installs must set an API key.
Capture (hooks/scaffold) works without it; only compile/query/seed make API calls.

## Naming note

Invoke this as `neurawork-cc-harness:knowledge-compiler` (the fully-qualified name)
so it always resolves to this plugin regardless of what else is enabled.

## Phase A — Recon (read-only)

Run the recon script and read its `RECON_JSON` blob:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/knowledge-compiler/recon.py"
```

- `status: NOT_A_GIT_REPO` → stop; tell the user to run inside a git repo (offer
  `git init`).
- `existing_kdir` set → this is an ADOPT (refresh) install; reuse that name.
- Note `seed_recommended`, `timezone`, and `clean`.

## Phase B — Ask

Use AskUserQuestion to confirm:
1. **Knowledge dir name** — default `knowledge-base` (or the detected `existing_kdir`).
2. **Timezone** — confirm the detected one (used only for display; no hardcoding).
3. **Seed now?** — offer only when `seed_recommended` is true AND the tree is clean.
   Seeding builds initial articles from the repo's README/docs and makes API calls.

## Phase C — Execute

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/knowledge-compiler/install.py" \
  --knowledge-dir <NAME> [--seed]
uv sync --directory <NAME>
```

Then tell the user to commit `<NAME>/` and `.claude/settings.json`. After install:
- Sessions now capture automatically.
- Manual compile: `/neurawork-cc-harness:kc-compile`.
- Query: `uv run --directory <NAME> python scripts/query.py "..."`.
