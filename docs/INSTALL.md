# Install & Upgrade Guide — neurawork-cc-harness

`neurawork-cc-harness` is a Claude Code plugin that keeps a repo's project
knowledge fresh. It bundles four **independently installable** skills:

- **`neurawork-cc-harness:knowledge-compiler`** — captures Claude Code sessions
  into `<dir>/daily/` logs and compiles them into a per-repo knowledge base
  (`knowledge/concepts/`, `knowledge/connections/`, `knowledge/index.md`),
  re-injected at session start.
- **`neurawork-cc-harness:claudemd-lerner`** — learns from each session and keeps
  your **`CLAUDE.md` hierarchy + `docs/`** current. No knowledge wiki.
- **`neurawork-cc-harness:compliance-compiler`** — ~30 parallel agents distil
  GDPR/SOC2/ISO27001 into a tracked constraint **catalog** (+ derived
  capabilities); a `PostToolUse` hook validates each PRP plan against it as it is
  written.
- **`neurawork-cc-harness:stack-compiler`** — narrows that catalog to one product:
  which capabilities apply, which component was chosen for each from a closed pool,
  and a `PostToolUse` hook that gates every PRD and plan write against those choices.

Each runs an interactive **recon** on install, can **seed** an existing
(brownfield) repo, and writes everything **inside the repo — never under
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
   `daily/` + `knowledge/` + `config.json`, and merges five hooks into
   `.claude/settings.json`: `SessionStart`, `PreCompact` and `SessionEnd` for
   capture and index injection, plus `UserPromptSubmit` and `PreToolUse`
   (matcher `Skill`), which spawn the `kb-researcher` agent when a PRP research
   workflow starts.

When it finishes, the installer prints:

```text
Next steps:
  uv sync --directory <dir>
  git add <dir> .claude/settings.json && git commit -m 'Add knowledge-compiler'
```

Run `uv sync --directory <dir>` to resolve the engine's dependencies, then commit
`<dir>/` and `.claude/settings.json`. From then on:

- Sessions capture automatically (the three capture hooks).
- A PRD, plan or debug workflow spawns `neurawork-cc-harness:kb-researcher` as a
  fourth research axis. Disable with `"research_directive": false` in
  `<dir>/config.json` — read live, no re-install.
- Manual compile: `/neurawork-cc-harness:kc-compile`.
- Query: `uv run --directory <dir> python scripts/query.py "..."`.

### 3. Install `claudemd-lerner`

Install it the same way:

```text
/neurawork-cc-harness:claudemd-lerner
```

It uses its own install dir (default `claudemd-lerner`) and `cl-`-prefixed hooks,
so it coexists with `knowledge-compiler` in the same repo — both hook sets land in
`.claude/settings.json` without clobbering each other. Manual update:
`/neurawork-cc-harness:cl-update`.

### 4. Install `compliance-compiler`

```text
/neurawork-cc-harness:compliance-compiler
```

It installs into its own dir (default `compliance-base`) and wires a **single**
`co-`-prefixed `PostToolUse` hook — no `SessionStart`/`SessionEnd` — so it coexists
with the other two. A fresh install lands a **prebuilt catalog** — the plugin ships
`catalog/{gdpr,soc2,iso27001}.json` + `index.md` + the derived `capabilities.{json,md}`
and copies them in, so the repo has a working catalog with no LLM run and no API key.
The install then derives `catalog/stack.json` from those capabilities (deterministic,
no API key) and sets `env.PRP_HOME` to `.claude/PRPs` in `.claude/settings.json`, so
PRP artifacts land inside the repo where the validator can see them — an existing
`PRP_HOME` is never overwritten. Choosing to extract instead fans out ~30 parallel SDK
agents. From then on:

- Every PRP plan write is validated automatically: a fast inline structural precheck
  plus a detached deep LLM report under `compliance-base/reports/`. Both plan
  locations count — `.claude/PRPs/plans/*.plan.md` and the `PRP_HOME` store layout
  `.claude/PRPs/<repo>-<hash>/plans/*.plan.md`; archived plans under `completed/` do not.
- Rebuild the constraint catalog on demand: `/neurawork-cc-harness:co-extract`.
- Re-derive the **capability layer** and refresh the stack scaffold:
  `/neurawork-cc-harness:co-capabilities`. It clusters the constraints into concrete
  building blocks (`catalog/capabilities.{json,md}`), fails if a mandatory constraint
  ends up covered by none, and updates `catalog/stack.json` — the tracked record of
  which component you actually chose per capability — plus a gap report under
  `compliance-base/reports/` naming the capabilities still undecided.
- Validate a plan manually: `/neurawork-cc-harness:co-validate <path-to-plan>`.

The catalog stores only official control/article identifiers, short titles, and
*paraphrased* requirements — never verbatim text of the copyrighted standards.
Extraction and deep validation need an API key (see Requirements); install,
scaffolding, and the inline precheck run without it.

### 5. Install `stack-compiler`

```text
/neurawork-cc-harness:stack-compiler
```

It installs into its own dir (default `stack-base`) and wires a **single**
`st-`-prefixed `PostToolUse` hook under the same `Write|Edit|MultiEdit` matcher as the
compliance gate — the two share that group, so all four engines coexist. It owns **no
data artifact**: every write goes through `compliance-base/scripts/stack.py`, the single
schema owner for `catalog/stack.json`. `compliance-compiler` must therefore be installed
and its catalog built for the passes and the gate to have anything to read; the install
itself succeeds either way and says which of the two you are in.

Three passes, then the gate:

- `/neurawork-cc-harness:st-scope` — decides per capability *whether* it applies to this
  product and why, from the tracked `stack-base/product.md`. The first run writes the
  `product.md` template and exits; fill it in and re-run. Needs an API key.
- `/neurawork-cc-harness:st-rank` — orders each still-applicable capability's catalog
  components best-fit-first, with a reason per position. Needs an API key.
- `/neurawork-cc-harness:st-select` — renders that ranking as an editable selection sheet
  and records the component a human wrote per capability (`--apply <sheet>`). Runs **no**
  agent and needs **no** API key.
- Every PRD and plan write is then gated automatically: a fast inline precheck plus a
  detached deep report under `stack-base/reports/`. `config.json`'s `validate_mode` sets
  `warn` | `block` per document type. Validate manually:
  `/neurawork-cc-harness:st-validate <path-to-prd-or-plan>`.

The component pool is closed — a ranking must name exactly that capability's `options`,
and a choice must come from them — and a deterministic gate (pool match plus the
catalog's own `license_policy`) runs before every write; a failed gate writes nothing.
Scoping and ranking are all-or-nothing; selection is deliberately partial, because an
undecided capability stays a counted gap rather than a silent omission.

### 6. Write the baseline coding rules (no install)

```text
/neurawork-cc-harness:nw-rules-init          # [--force] to refresh an existing block
```

Installs nothing. It reads the repo's root `CLAUDE.md`, detects the **test runner the
repo actually uses** (an existing command in the CLAUDE.md, then CI, `pyproject.toml`,
a `unittest` tests tree, `package.json`, `go.mod`/`Cargo.toml` — never a default), reports
per-cluster coverage (`already covered` / `conflicts` / `absent`), asks, and then writes
one marker-delimited block:

```text
BEGIN comment: neurawork-cc-harness:rules
### Coding Discipline
- Scope · Simplicity · Evaluation first (carrying the detected test command)
END comment: neurawork-cc-harness:rules
```

(Rendered with the real HTML-comment syntax in the file — spelled out here so this guide
does not itself look like a marker block to the guard below.)

The block is idempotent — a re-run offers Replace/Keep, `--force` refreshes silently, and
a second block is never written. It stays under 1,200 characters, enforced by a test.

If `claudemd-lerner` is installed, the block is also **protected**: every update and seed
run snapshots each `owner:name` marker span and restores it byte-for-byte afterwards,
printing a `Marker guard:` line when it had to. The guard is marker-generic, so a block
written by another tool (e.g. `coding-suite:coding-discipline-init`) is protected too.

---

## When the harness seems quiet — run the doctor first

```text
/neurawork-cc-harness:nw-doctor              # [--json] for the machine-readable form
```

Installs nothing, writes nothing. The engines run as **detached, fire-and-forget hooks
whose output goes to `DEVNULL`**, so a compile or update that dies leaves no trace at all:
daily logs keep accumulating while the gate stays shut behind a lock nobody cleared. The
doctor is the signal that state has none of its own. For every engine it reports:

- **discovery** — the install dir, found by hook marker *and* by directory signature. An
  install dir no hook names never fires; a hook naming a missing dir errors at every
  session start. Both are ERRORs, both name the install skill that fixes them.
- **version and `_shared/` drift** — installed vs shipped, including *ahead*, plus a
  byte comparison of the copied shared helpers against the plugin's.
- **integrity** — every payload file, `config.json`, `VERSION`, `.gitignore`, `.venv`.
- **queue** — pending daily logs (absent from `state.json`, or edited since), the age of
  the last successful run, and the lock. A fresh lock over an older completion stamp is
  the stall: it names when the run was spawned, when the gate reopens, and the foreground
  command that shows the real error.
- **environment** — `uv` on `PATH`, python ≥ 3.12, an API credential, and whether this
  checkout is a worktree (where both gates are suppressed by design, so queue lag there
  is a note, not a fault).

It runs under **system `python3`, not `uv run`** — a missing `uv` or an absent `.venv` is
one of the states it exists to report — and needs no API key. Exit code: `0` clean, `1`
warnings, `2` errors, so it also works in a script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --json
```

Every finding carries a fix command; the doctor never runs one. It removes no lock, spawns
no compile, and leaves the repo byte-identical.

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

## Fully qualified names

Always invoke the skills by their **fully qualified** plugin-namespaced names —
`neurawork-cc-harness:knowledge-compiler`, `neurawork-cc-harness:claudemd-lerner`,
`neurawork-cc-harness:compliance-compiler` — so an install always resolves to this
plugin regardless of what else is enabled.

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

**Staleness nudge.** `/plugin marketplace update` refreshes the *plugin* but not the
engine copy already installed in your repo (that copy is tracked in-repo, not in the
plugin cache). So after an update you must still re-run the installer to propagate an
engine change. A plugin-level `SessionStart` hook makes this visible: at session start
it compares each installed engine's stamped `VERSION` against the plugin's shipped
`VERSION` and, when an install is behind, prints a short note naming the stale install
and the exact re-run command (e.g. `re-run /neurawork-cc-harness:knowledge-compiler`).
It is informational only — it never modifies your repo — and stays silent when every
install is current or the repo has no harness install.
