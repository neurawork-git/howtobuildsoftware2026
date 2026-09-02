# Architecture — neurawork-cc-harness

How the harness is put together: the plugin source, the four engines, the shared
infrastructure, the install flow, and how this repo self-hosts all four skills. For
*using* it see [INSTALL.md](INSTALL.md).

## The four skills

| Skill | Captures / reads | Produces | Constitution |
|-------|------------------|----------|--------------|
| `knowledge-compiler` | session transcripts → `<dir>/daily/` logs | `<dir>/knowledge/` wiki (`index.md`, `concepts/`, `connections/`) | `knowledge-base/AGENTS.md` |
| `claudemd-lerner` | session transcripts → `<dir>/daily/` logs | repo-root `CLAUDE.md` hierarchy + `docs/` (edited in place) | `claudemd-lerner/AGENTS.md` |
| `compliance-compiler` | GDPR/SOC2/ISO27001 standards (~30 parallel agents) | `<dir>/catalog/` constraint JSON + `index.md` + `capabilities.{json,md}` + `stack.json` | `compliance-base/AGENTS.md` |
| `stack-compiler` | the tracked `<dir>/product.md` + the capability catalog | no artifact of its own — the applicability, ranking and chosen-component fields of `compliance-base/catalog/stack.json` | `stack-base/AGENTS.md` |

The first two follow the same **LLM-as-compiler** model: sessions emit append-only
`daily/` logs (the "source code"); an LLM (the "compiler" / "learner") reads the logs
plus the live repo and synthesizes the executable output — never organised by hand.
The concept derives from Andrej Karpathy's LLM wiki and coleam00's
`claude-memory-compiler`; the implementation is independent NeuraWork work.
`compliance-compiler` applies the same distil-to-tracked-artifact idea to a
different source (the standards themselves), and adds a validation half: a
`PostToolUse` hook checks each PRP plan against the catalog as it is written.

## Plugin source layout (`plugins/neurawork-cc-harness/`)

```
.claude-plugin/plugin.json     plugin manifest (name, semver version, …)
skills/<skill>/SKILL.md        install skills (recon → ask → execute)
                               + nw-worktree/ (workflow skill, no engine)
commands/                      kc-compile.md, cl-update.md, co-extract.md,
                               co-capabilities.md, co-validate.md, st-scope.md,
                               st-rank.md, st-select.md, st-validate.md, nw-ship-pr.md
workflows/                     nw-ship-pr-review.js (auto-discovered by the runtime and
                               namespaced as neurawork-cc-harness:nw-ship-pr-review)
agents/                        kb-researcher.md (read-only; the fourth research axis,
                               namespaced as neurawork-cc-harness:kb-researcher)
tests/                         structural tests over the prompt-only assets
hooks/                         hooks.json + version-check.js (the only code that runs
                               FROM the plugin, with CLAUDE_PLUGIN_ROOT — the staleness nudge;
                               Node, not Python: it must bootstrap without uv)
engines/
  _shared/                     stdlib-only helpers (single source of truth)
  knowledge-compiler/
    install.py  recon.py  config.default.json  VERSION
    payload/                   code copied into the target repo
    tests/
  claudemd-lerner/             (same shape)
  compliance-compiler/         (same shape; payload has extract.py + validate.py + catalog scripts)
  stack-compiler/              (same shape; payload has scope/rank/selection + validate.py;
                               the self-host is pinned by test_payload_drift.py between installs)
```

The repo-root `.claude-plugin/marketplace.json` (marketplace `neurawork-harness`)
distributes `plugins/neurawork-cc-harness` via a `git-subdir` source; with no pinned
`version`, installs track the latest commit on the default branch.

### install skills vs. workflow skills

Two component categories live side by side. An **install skill** (`knowledge-compiler`,
`claudemd-lerner`, `compliance-compiler`, `stack-compiler`) exists to copy an `engines/<engine>/payload/`
into a target repo and merge hooks into `.claude/settings.json`; it owns an `install.py`,
a `recon.py`, a `VERSION`, and a data artifact in the repo. A **workflow skill**
(`nw-worktree`, and the `nw-ship-pr` command with its `nw-ship-pr-review.js`) copies
nothing and installs nothing — it is a prompt procedure that lazily writes one
`.claude/*.local.md` config on first run. It therefore has no engine, no payload, no
`VERSION`, and no entry in `hooks/version-check.js`'s `ENGINES` map (which keys off
installed hook commands — a component that installs no hook can never appear there).
That absence is intended, not an omission.

### engine vs. payload

`engines/<engine>/` is **install-time tooling** run from the plugin.
`engines/<engine>/payload/` is **what runs inside the target repo** after install:
hooks, scripts, `pyproject.toml`, and the engine's `AGENTS.md`. Payload scripts
resolve their `config`/`utils` modules via `sys.path` at `uv run` time (not as
importable packages), so static type checkers flag those imports as unresolved —
expected and harmless.

### `_shared/` helpers

Stdlib-only, reused by all engines and **refreshed on every install** so there is
one source of truth:

| Module | Purpose |
|--------|---------|
| `hookio.py` | Parse hook stdin (Windows-safe) + recursion guard |
| `transcript.py` | Read a JSONL transcript → recent markdown turns |
| `gitctx.py` | Worktree detection + state redirect to the main checkout |
| `settings.py` | Idempotent `.claude/settings.json` hook merge |
| `repo_guard.py` | Enforce: outputs in-repo, never under `.claude/` |
| `recon.py` | Git-root resolution + `RECON_JSON` emit for install recon |

## Install flow

Each skill's `SKILL.md` runs three phases:

1. **Recon (read-only)** — `recon.py` prints a `RECON_JSON` blob: git root, whether
   a prior install exists (ADOPT vs FRESH), seed recommendation, timezone, and (for
   the learner) suggested CLAUDE.md depth / language / docs presence.
2. **Ask** — `AskUserQuestion` confirms the install dir, and for the learner the
   depth, docs dir, language, excluded dirs, timezone, and whether to seed.
3. **Execute** — `install.py` copies `payload/` + `_shared/` into `<repo>/<dir>/`,
   scaffolds data dirs (only if absent — never clobbers), and **idempotently merges**
   both the engine's ignore rules into `<dir>/.gitignore` (append-only: a rule added in
   a later release reaches an install that already exists, and nothing the user wrote is
   moved or removed) and the hooks into `.claude/settings.json`.

`install.py` is **ADOPT-aware**: when it detects an existing install it refreshes
code (`payload/` + `_shared/`) without touching captured data (`daily/`, the wiki,
or the docs). Then `uv sync --directory <dir>` resolves engine deps; the user
commits `<dir>/` and `.claude/settings.json`.

## Runtime: capture and synthesis

Three hooks drive capture, merged into `.claude/settings.json`:

- **`SessionEnd`** / **`PreCompact`** — write the session into a `daily/` log.
- **`SessionStart`** — for `knowledge-compiler`, inject the current wiki index as
  additional context; `claudemd-lerner` injects nothing here (its `CLAUDE.md` +
  `docs/` are already read at session start). For both, if the last run is older than
  the 6-hour gate *and* there is new `daily/` content *and* no fresh lock, fire a
  detached compile/update (skipped inside a worktree).

## Runtime: the fourth research axis

`knowledge-compiler` installs two further hooks that capture nothing. When a PRP
research workflow starts, they inject a directive to spawn
`neurawork-cc-harness:kb-researcher` — the plugin's read-only knowledge-base agent —
**alongside** `prp-core`'s three research agents:

| Axis | Agent | Answers |
|---|---|---|
| where code lives | `prp-core:codebase-explorer` | which files and precedents exist |
| how it behaves | `prp-core:codebase-analyst` | control flow, state, side effects |
| what sources say | `prp-core:web-researcher` | external, cited facts |
| what we already learned | `neurawork-cc-harness:kb-researcher` | prior findings, decisions, gotchas |

Only the fourth has a subject that exists nowhere else: source code can be re-read and
the web re-searched, but a finding distilled from a session months ago lives only in
`<kdir>/knowledge/`. The agent retrieves **index-first, then by backlinks** — `grep`ing
for `[[<dir>/<slug>]]`. That second step is not stylistic: connection articles link
*down* to their concepts and nothing requires a concept to link back up, so forward
traversal from a concept hit can never reach the cross-cutting layer.

Two hooks, because a skill is entered by two paths and no single event sees both:

- **`UserPromptSubmit`** (`hooks/user-prompt-submit.py`) — a slash command the user
  types is expanded into the prompt, never routed as a tool call.
- **`PreToolUse`**, matcher `Skill` (`hooks/pre-skill.py`) — a model-invoked skill
  arrives as `tool_name: "Skill"` with no new prompt.

Both render the same string from `payload/scripts/research_directive.py`, so the two
paths cannot drift into disagreeing about which workflow counts as research. **Exit
code 2 on `PreToolUse` blocks the tool call**, so both hooks fail open: any exception
yields no output and exit 0. The `matcher: "Skill"` group — the reason
`_shared/settings.py` accepts a 5-tuple hook — keeps `pre-skill.py` off every other
tool call. `compliance-compiler` registers its `PostToolUse` hook the same way, under
`matcher: "Write|Edit|MultiEdit"`. `"research_directive": false` in `<kdir>/config.json` disables both,
live, with no installer re-run.

Synthesis can also be triggered manually: `/neurawork-cc-harness:kc-compile` and
`/neurawork-cc-harness:cl-update`, or directly via
`uv run --directory <dir> python scripts/{compile,update}.py`. Runs are incremental
by SHA-256 of each daily log and stamp a `last-{compile,update}.json` so the gate
knows when they last ran. Synthesis needs `ANTHROPIC_API_KEY` /
`CLAUDE_CODE_OAUTH_TOKEN`; capture and scaffolding do not.

`compliance-compiler` runs on a different clock. Its catalog ships prebuilt with the
plugin and is copied in at install, then rebuilt on demand: `co-extract` re-derives the
**constraints** from the standards and `co-capabilities` re-derives the **capability
layer** on top of them — both ~30 parallel SDK agents behind `asyncio.gather` + a
semaphore, the harness's only parallel compile path. `catalog/stack.json` — the tracked
record of the component chosen per capability — is scaffolded at install time from the
seeded capabilities (`scripts/stack.py --scaffold`, deterministic, no API key) and
refreshed by `co-capabilities` afterwards; both write a gap report naming the ones still
undecided. The install also points `PRP_HOME` at `.claude/PRPs`, without which prp-core
writes its plans outside the repo and the hook below never sees them. At runtime the
engine wires a **single** `co-`-prefixed **`PostToolUse`** hook (no
`SessionStart`/`SessionEnd`) that validates each PRP plan write — in the canonical
`.claude/PRPs/plans/` or in the `PRP_HOME` store one level deeper: a fast inline
structural precheck plus a detached deep LLM report under `compliance-base/reports/`.
The precheck covers both tiers — mandatory constraint references and the plan's
`**Capabilities**:` declaration — and, when the capability layer is missing entirely,
names the command that builds it. Manual check:
`/neurawork-cc-harness:co-validate <plan>`.

Separately, the **plugin itself** registers one `SessionStart` hook (`hooks/hooks.json`
→ `hooks/version-check.js`) — the only harness code that runs *from* the plugin with
`CLAUDE_PLUGIN_ROOT` set, rather than from an installed copy. It compares each installed
engine's stamped `VERSION` (`<repo>/<dir>/VERSION`) against the plugin's shipped
`VERSION` (`engines/<engine>/VERSION`), locating the install dir by parsing the engine's
hook command in `.claude/settings.json`, and prints a staleness nudge when an install is
behind. It has to live at the plugin level: an installed hook resolves its paths from its
own on-disk location and never sees the plugin, so it cannot read the shipped `VERSION`.
It is also the one script written in **Node rather than Python**, spawned through the hook
*exec form* (`"command": "node"`, script path in `args`, no shell). Everything else in the
harness runs under `uv` inside a target repo; this hook runs before any of that exists, so
it cannot use `uv` (an 11.6 s cold start against a 10 s timeout) and cannot name a Python
interpreter either — `python3` is the Microsoft Store alias on Windows, `python` does not
exist on macOS. `node` is on `PATH` wherever Claude Code runs, on every platform.

That language split is the one thing it costs: the nudge can no longer import the Python
engine registry in `scripts/harness_probe.py`, so it carries its own copy of the engine →
hook-marker map. The copy is not allowed to drift — `tests/test_version_check_registry.py`
asserts the JavaScript map names exactly the installable engines of `harness_probe.ENGINES`
with exactly their hook markers, and fails the moment a fifth engine is registered on one
side only. That guard is what makes a second map acceptable; do not delete it and "keep
them in sync by hand" — the map had already fallen an engine behind once before the probe
existed.

The manifest's semver `version` names the plugin *release* and is independent of the four
per-engine integer `VERSION` counters (which advance separately).

## Self-hosting in this repo

This repo installs the harness into itself:

- `knowledge-base/` — `knowledge-compiler` machinery + the tracked `knowledge/` wiki.
- `claudemd-lerner/` — `claudemd-lerner` machinery; its outputs are this repo's
  root `CLAUDE.md` hierarchy and `docs/` (including this file).
- `compliance-base/` — `compliance-compiler` machinery + the tracked `catalog/`
  (constraint JSON + `index.md` + `capabilities.{json,md}` + `stack.json`);
  `catalog/.shards/` and
  `reports/` are gitignored.
- `stack-base/` — `stack-compiler` machinery + the tracked scoping input `product.md`;
  it owns no data artifact (its passes write `compliance-base/catalog/stack.json`
  through that engine's `stack.py`). Installed and refreshed by
  `/neurawork-cc-harness:stack-compiler` like the other three;
  `engines/stack-compiler/tests/test_payload_drift.py` backs that installer up between
  runs, catching a direct edit to either copy that was never propagated. See [`stack-base/CLAUDE.md`](../stack-base/CLAUDE.md).

The hook sets live side by side in `.claude/settings.json` — the learner's are
`cl-`-prefixed on the `SessionStart`/`PreCompact`/`SessionEnd` events; on `PostToolUse`,
compliance's `co-`-prefixed hook and stack's `st-`-prefixed hook share the
`matcher: "Write|Edit|MultiEdit"` group — so they coexist without
clobbering each other. The machinery in those dirs is a
copy of the plugin payload — fix bugs in
`plugins/…/engines/<engine>/payload/` and re-run the installer to refresh, rather
than hand-editing the installed copy.
