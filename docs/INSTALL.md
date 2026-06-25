# Install & Upgrade Guide — neurawork-cc-harness

`neurawork-cc-harness` is a Claude Code plugin that keeps a repo's project
knowledge fresh. It bundles two **independently installable** skills:

- **`neurawork-cc-harness:knowledge-compiler`** — captures Claude Code sessions
  into `<dir>/daily/` logs and compiles them into a per-repo knowledge base
  (`knowledge/concepts/`, `knowledge/connections/`, `knowledge/index.md`),
  re-injected at session start.
- **`neurawork-cc-harness:claudemd-lerner`** — learns from each session and keeps
  your **`CLAUDE.md` hierarchy + `docs/`** current. No knowledge wiki.
  *(Ships in Phase 3 — if the skill is not yet present in your plugin copy, only
  `knowledge-compiler` is installable.)*

Both run an interactive **recon** on install, can **seed** an existing
(brownfield) repo, and write everything **inside the repo — never under
`.claude/`**.

---

## Requirements

| Need | Why |
|------|-----|
| `git` | Install refuses outside a git repo; recon/capture key off the repo root. |
| [`uv`](https://docs.astral.sh/uv/) | Runs the Python engines and resolves their dependencies. |
| Python ≥ 3.12 | Engine runtime (`uv` provides it). |
| `ANTHROPIC_API_KEY` **or** `CLAUDE_CODE_OAUTH_TOKEN` | Needed for the LLM calls (compile / query / seed / flush). **Capture and scaffolding work without it** — only the SDK calls need a key. |

> **Auth posture:** subscription credentials (`~/.claude/.credentials.json`) are
> **not** sanctioned for third-party plugins. Public / customer installs must set
> an API key in the environment.

---

## Install the harness in your repo (the upgrade path)

The plugin lives in a **subdirectory** of this repo
(`plugins/neurawork-cc-harness/`), so it is distributed via a marketplace using a
`git-subdir` source.

### 1. Add the marketplace and install the plugin

From inside the repo you want to upgrade, in a Claude Code session:

```text
/plugin marketplace add neurawork-git/howtobuildsoftware2026
/plugin install neurawork-cc-harness@neurawork-harness
```

- `neurawork-git/howtobuildsoftware2026` is the GitHub `owner/repo`.
- `neurawork-harness` is the marketplace name (from
  `.claude-plugin/marketplace.json`).
- The marketplace entry omits an explicit `version`, so installs track the latest
  commit on the default branch — run `/plugin marketplace update` to pull updates.

### 2. Install a skill into the repo

Each skill is installed independently by invoking it (always use the **fully
qualified** name — see *FQN / collision* below):

```text
/neurawork-cc-harness:knowledge-compiler
```

The skill runs a **three-phase** flow:

1. **Recon (read-only)** — detects the repo root, whether a previous install
   exists (ADOPT vs FRESH), whether a seed is recommended, and your timezone.
2. **Ask** — confirms the install dir name (default `knowledge-base`), the
   timezone, and whether to seed now (offered only when recommended and the tree
   is clean).
3. **Execute** — copies the engine + shared helpers into `<dir>/`, scaffolds
   `daily/` + `knowledge/` + `config.json`, and merges three hooks
   (`SessionStart`, `PreCompact`, `SessionEnd`) into `.claude/settings.json`.

When it finishes, the installer prints:

```text
Next steps:
  uv sync --directory <dir>
  git add <dir> .claude/settings.json && git commit -m 'Add knowledge-compiler'
```

Run `uv sync --directory <dir>` to resolve the engine's dependencies, then commit
`<dir>/` and `.claude/settings.json`. From then on:

- Sessions capture automatically (the three hooks).
- Manual compile: `/neurawork-cc-harness:kc-compile`.
- Query: `uv run --directory <dir> python scripts/query.py "..."`.

### 3. (Phase 3) Install `claudemd-lerner`

Once the `claudemd-lerner` skill is present in the plugin, install it the same
way:

```text
/neurawork-cc-harness:claudemd-lerner
```

It uses its own install dir (default `claudemd-lerner`) and `cl-`-prefixed hooks,
so it coexists with `knowledge-compiler` in the same repo — both hook sets land in
`.claude/settings.json` without clobbering each other.

---

## Local development (working ON the plugin)

If you are developing the plugin from a checkout of *this* repo, you do not need a
marketplace — load it as a **skills-directory plugin** by symlinking it into the
repo's (or your user) skills dir:

```bash
# repo-local (only this repo), loads as neurawork-cc-harness@skills-dir
ln -s ../plugins/neurawork-cc-harness .claude/skills/neurawork-cc-harness
```

- It auto-loads on the next session — no `/plugin install` needed.
- Run `/reload-plugins` after editing non-`SKILL.md` components (hooks, scripts).
- **Gotcha:** a marketplace-installed copy is cached under
  `~/.claude/plugins/cache/`; edits to your repo source are NOT reflected there.
  Use the symlink method while developing, the marketplace for distribution.

---

## FQN / collision

Always invoke the skills by their **fully qualified** plugin-namespaced names:

- `neurawork-cc-harness:knowledge-compiler` — the bare name `knowledge-compiler`
  **also exists** in the `coding-suite` plugin, so the FQN avoids ambiguity.
- `neurawork-cc-harness:claudemd-lerner` — collision-free, but use the FQN anyway
  for consistency.

See [docs/WHEN-TO-USE.md](WHEN-TO-USE.md) for choosing between this harness and the
`coding-suite` skills.

---

## Upgrading

```text
/plugin marketplace update
```

Because the marketplace entry tracks the commit SHA (no pinned `version`), this
pulls the latest plugin code. To refresh an already-installed skill's engine in a
repo, re-invoke the install skill — recon detects the existing dir as an **ADOPT**
and refreshes the code/hooks **without clobbering** your `daily/` logs or
`knowledge/`.
