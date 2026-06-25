---
name: claudemd-lerner
description: Install a per-repo learner that keeps the CLAUDE.md hierarchy and docs/ tree current from Claude Code sessions. Captures sessions into daily logs and, on a manual command or a 6-hour SessionStart gate, edits CLAUDE.md + docs/ in place (no knowledge wiki). Trigger when the user says "claudemd lerner", "install claudemd lerner", "keep CLAUDE.md current", "update my project docs automatically", "CLAUDE.md aktuell halten", "docs aktuell halten", or wants session-driven CLAUDE.md + docs/ maintenance that can seed an existing repo.
---

# claudemd-lerner — Install Skill

Installs the claudemd-lerner engine into the current repo: SessionEnd/PreCompact
hooks capture each session into `<ldir>/daily/`, and an updater applies those logs
to the repo's **CLAUDE.md hierarchy + `docs/` tree** (editing them in place).
SessionStart injects the current CLAUDE.md + docs/ listing. Updates run on a manual
command or a 6-hour SessionStart gate.

The lerner dir (`<ldir>/`) holds ONLY machinery (hooks/scripts/_shared/daily). The
actual outputs — CLAUDE.md files and `docs/` — live at the **repo root**, the files
the agent already reads. Nothing is ever written under `.claude/`. There is **no**
knowledge wiki (that is the separate `knowledge-compiler` skill).

## Authentication

The updater uses the Claude Agent SDK, which needs `ANTHROPIC_API_KEY` (or
`CLAUDE_CODE_OAUTH_TOKEN`) in the environment. Subscription credentials are NOT
sanctioned for third-party plugins — public/customer installs must set an API key.
Capture (hooks/scaffold) works without it; only update/seed make API calls.

## Naming / collision note

Invoke this as `neurawork-cc-harness:claudemd-lerner`. The name is collision-free,
but use the fully-qualified form by convention. This skill **coexists** with
`neurawork-cc-harness:knowledge-compiler` in one repo: its hooks use `cl-`-prefixed
filenames, so its `.claude/settings.json` entries never overwrite the compiler's.

## Phase A — Recon (read-only)

Run the recon script and read its `RECON_JSON` blob:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/claudemd-lerner/recon.py"
```

- `status: NOT_A_GIT_REPO` → stop; tell the user to run inside a git repo (offer
  `git init`).
- `existing_ldir` set → this is an ADOPT (refresh) install; reuse that name.
- Note `suggested_depth`, `language`, `has_docs`, `seed_recommended`, `timezone`,
  and `clean`.

## Phase B — Ask

Use AskUserQuestion to confirm:
1. **Lerner dir name** — default `claudemd-lerner` (or the detected `existing_ldir`).
2. **CLAUDE.md depth** — default `suggested_depth` (1 = root CLAUDE.md only; 2 = root
   + immediate subdirs).
3. **Docs dir** — default `docs`.
4. **Language** — confirm the detected `language` (`en`/`de`).
5. **Excluded dirs** — confirm the suggested list (node_modules, .venv, dist, build, .git).
6. **Timezone** — confirm the detected one (display only; no hardcoding).
7. **Seed now?** — offer only when `seed_recommended` is true AND the tree is clean.
   Seeding builds/updates the initial CLAUDE.md + docs/ from the repo and makes API calls.

Write the chosen depth/docs/language/excluded into `<ldir>/config.json` after install
(install seeds defaults; edit the file to match the answers).

## Phase C — Execute

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/claudemd-lerner/install.py" \
  --lerner-dir <NAME> [--seed]
uv sync --directory <NAME>
```

Then tell the user to commit `<NAME>/`, `.claude/settings.json`, and any CLAUDE.md /
docs changes the seed produced. After install:
- Sessions now capture automatically.
- Manual update: `/neurawork-cc-harness:cl-update`.
