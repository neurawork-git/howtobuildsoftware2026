# Changelog

All notable changes to `neurawork-cc-harness` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the plugin uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

The version in `.claude-plugin/plugin.json` is what a marketplace install resolves, and it is
the only signal an installed copy has that a newer one exists — an engine or payload change
without a bump never reaches an existing install.
`engines/_shared/tests/test_manifest.py` therefore fails a release whose version has no
section here.

> **Entries for 0.3.1 and older were reconstructed from `git log` on 2026-08-27**, after this
> file was created. They were not written at release time and are neither complete nor as
> precise as the sections written since. They are marked so nothing in this file reads as a
> contemporaneous record that is not one.

## [0.7.1] — 2026-09-02

### Fixed

- **The `SessionStart` staleness nudge printed an error into every Windows session.**
  `hooks/hooks.json` named `python3`, which on Windows resolves to the Microsoft Store
  app-execution alias. The alias writes `Python was not found` to **stdout**, and
  `SessionStart` stdout is injected into the session as `additionalContext` — so a hook
  documented as a silent no-op became a visible one (#16). `python` is not a fix either:
  macOS has shipped no unsuffixed `python` since 12.3, so the two candidate names fail on
  opposite platforms and no third name exists everywhere. `uv` is out too — an 11.6 s cold
  start against this hook's 10 s timeout (#5), and this is precisely the script that must
  bootstrap before the toolchain exists.

  The hook therefore stops naming an interpreter: `hooks/version-check.py` becomes
  `hooks/version-check.js`, spawned through the hook **exec form** (`"command": "node"`,
  script path in `args`, no shell). `node` is on `PATH` wherever Claude Code runs. Same
  logic, same output, tests ported to the built-in `node:test` runner
  (`hooks/version-check.test.js`).

  One cost, one guard: a Node hook cannot import the Python engine registry in
  `scripts/harness_probe.py`, so it carries a transcription of the engine → hook-marker map.
  `tests/test_version_check_registry.py` fails the build when the two disagree — the map had
  already fallen a whole engine behind reality once, which is what the shared registry was
  extracted to end.

  Not verified on Windows — the author reports macOS 15.7.3 / Node 22.19 only, and the
  platform the fix exists for is the one gap left (tracked in `.claude/BACKLOG.md`).

## [0.7.0] — 2026-09-02

### Fixed

- **The knowledge-base seed could write to the wrong directory.** `payload/scripts/seed.py`
  runs the seeding agent with `cwd=<repo root>` but writes into `KNOWLEDGE_DIR`
  (`<repo>/<kdir>/knowledge`), which it supplies in a separate `## Write articles under`
  section. `seed_prompt.txt` nevertheless stated all six of its write targets as bare
  relative paths (`knowledge/concepts/<slug>.md`, `knowledge/index.md`, `knowledge/log.md`,
  `knowledge/connections/`, and both `knowledge/` constraints), which resolve against that
  cwd — one level too high, at `<repo>/knowledge/`. Nothing caught it: the write guard
  checks `KNOWLEDGE_DIR` once before the run, never the agent's writes, and
  `<repo>/knowledge/` passes that check anyway. The prompt now binds every target to a
  `<knowledge-root>` token that it explicitly resolves to the absolute section, and states
  that the working directory is not that directory.
  `engines/knowledge-compiler/VERSION` goes `3` → `4`, so existing installs are nudged to
  re-install.
- `engines/knowledge-compiler/tests/test_seed_prompt.py` pins the invariant: no bare
  `knowledge/` write target in the prompt, the pointer to the absolute section is present,
  and `seed.py` still supplies both that section and the repo-root cwd. It also fails when
  the self-host copy at `knowledge-base/scripts/seed_prompt.txt` drifts from the payload.

## [0.6.0] — 2026-08-27

### Fixed

- **`claudemd-lerner` never ran.** `payload/scripts/update.py` imported `_shared.repo_guard`
  with no `sys.path` bootstrap — the only payload script missing the line its siblings carry —
  so every invocation died at import with `ModuleNotFoundError: No module named '_shared'`,
  before `argparse` and before `main()`. The `SessionStart` hook spawns it detached with both
  streams at `/dev/null`, so the crash produced no `CLAUDE.md` updates and no trace.
  `engines/claudemd-lerner/VERSION` goes `4` → `5`, so existing installs are nudged to
  re-install.
- **A failed update advanced the gate anyway.** `update.py` stamped `last-update.json`
  unconditionally after its per-log loop, shutting the 6-hour `SessionStart` gate over work
  that never happened. It now stamps only when at least one log actually ingested.

### Added

- **The update child's output is kept.** `hooks/cl-session-start.py` appends the detached
  run's stdout and stderr to `scripts/update.log` (already gitignored via `scripts/*.log`)
  instead of discarding both. A log that cannot be opened falls back to `/dev/null` — the
  gate never fails because logging failed.
- **`/nw-doctor` answers whether the plugin is current.** A new `plugin` section compares the
  installed version against the marketplace clone already on disk (offline, read-only, no
  `git` process): WARN when behind with the `/plugin update` + `/reload-plugins` fix, NOTE
  when ahead or unreadable, plus notes for a running plugin root that differs from the
  installed path, leftover cache versions, and — only when behind and an engine `VERSION`
  differs — that re-installing now would still install the older engine.
- **`/nw-doctor` names an engine that never ran.** A completion stamp with no ingest state
  and pending logs is now its own WARN instead of a benign "the gate reopens at X".

### Changed

- **The credentials finding stopped asserting something false.** With no API key but a
  subscription login present it is a NOTE saying the engines fall back to the bundled Claude
  Code CLI (still recommending an API key, which is what third-party plugin use is sanctioned
  for); with no auth at all it stays a WARN. The credentials file is checked for existence
  only — never read, parsed or rendered.

## [0.5.1] — 2026-08-27

### Fixed

- **`stack-compiler` recon reported the wrong stack state.** `engines/stack-compiler/recon.py`
  counted `applicable` where the scoping pass records `scoped_from`, so a repo that had
  already been scoped read back as unscoped. Reporting only — no install or payload behaviour
  changed.
- **`/nw-doctor` read the queue from the wrong checkout.** `scripts/doctor.py` read the daily
  queue from the current worktree instead of the main checkout, so a session inside a worktree
  saw an empty queue, and it now roots the suggested fix commands in the checkout it actually
  read.

## [0.5.0] — 2026-08-27

### Added

- **`stack-compiler` is the fourth installable skill.** `engines/stack-compiler/install.py`
  and `recon.py` install the product-scoping engine into any git repo the same way the other
  three install — recon, ask, ADOPT-safe execute — driven by
  `/neurawork-cc-harness:stack-compiler`. The engine owns no data artifact: every write goes
  through `<compliance-dir>/scripts/stack.py`, the single schema owner for
  `catalog/stack.json`.
- Four slash commands for its four passes: `/neurawork-cc-harness:st-scope` (which
  capabilities apply and why), `:st-rank` (order each one's components), `:st-select`
  (render the selection sheet, record the choices — no agent, no API key) and
  `:st-validate` (check a PRD or plan against the recorded stack on demand).
- `scripts/harness_probe.py`'s `stack-compiler` entry now names an install skill, so the
  `SessionStart` staleness nudge covers a `stack-base/` install for the first time.

### Changed

- The `st-` `PostToolUse` hook registers under `matcher: "Write|Edit|MultiEdit"` instead of
  the catch-all group, where every tool call in every session paid for a `uv run` subprocess
  that read stdin and exited. Re-running the installer **moves** an existing catch-all
  registration into that group, so the narrowing reaches installs that already exist.
- Installing without a `compliance-compiler` sibling is a warning, not a failure: the
  machinery installs, and the passes that genuinely need the catalog keep exiting 1 with
  their own message.

## [0.4.1] — 2026-08-27

### Changed

- The `nw-rules-init` block gains a fourth cluster, **Pull requests**: open and merge every PR
  with `/neurawork-cc-harness:nw-ship-pr`. Agents otherwise reach for whatever PR skill is
  enabled (`prp-pr`, a bare `gh pr create`) and skip the review, validation and approval gates
  `/nw-ship-pr` owns. The block is read on every session, which is the only place a routing
  rule is seen before the agent picks a tool. Rendered size 1,280 → 1,460 characters, inside
  the 1,500 budget.

## [0.4.0] — 2026-08-27

### Added

- `_shared/settings.py` gains `merge_gitignore(target, content)`: an append-only merge of an
  engine's ignore rules into its install dir's `.gitignore`. All three installers call it, on
  both FRESH and ADOPT.
- `CHANGELOG.md` (this file), plus `keywords`, `homepage` and `repository` in
  `.claude-plugin/plugin.json`.

### Changed

- The `compliance-compiler` `PostToolUse` hook registers under
  `matcher: "Write|Edit|MultiEdit"` instead of the catch-all group. It previously started a
  `uv run` subprocess on **every** tool call in every session, only to read stdin, see a
  non-write tool and exit. The hook keeps its own `WRITE_TOOLS` check — a matcher is an
  optimisation, not a contract, and a hand-edited `settings.json` must still be safe.
- `merge_hooks` migrates a hook that is registered under a different matcher: the entry is
  **moved** into the requested group and an emptied group is dropped. Without this the
  narrowing above would reach fresh installs only.
- Engine `VERSION` bumps so the `SessionStart` staleness nudge tells existing installs to
  re-run their installer: `knowledge-compiler` 2 → 3, `claudemd-lerner` 3 → 4,
  `compliance-compiler` 4 → 5.
- `README.md` rewritten against the actual inventory: three installable skills, three
  install-free workflow surfaces, the `kb-researcher` agent, and `stack-compiler`'s
  deliberate not-installable state.

### Fixed

- The three installers wrote their `.gitignore` create-if-absent, so a rule added in a later
  release reached fresh installs only. `catalog/.shards/` was the live case: a
  `compliance-base/` installed before it kept its shard files tracked forever.
- `/nw-ship-pr` used a `$MAIN_ROOT` shell variable it never bound — shell state does not
  survive between Bash calls, so the first-run config write and the whole 8.4 branch-cleanup
  block ran against `/`. Both roots are now resolved once in Phase 0.1 and inserted literally,
  the convention the rest of the file already used for `<wt-root>`.

## [0.3.1] — 2026-08-27 *(reconstructed)*

### Fixed

- `knowledge-compiler`'s recon reports all five installed hooks, not just the original three
  (`ed1f45e`). Shipped by the bump itself (`04e4ba1`) — an engine fix stays stranded in the
  repo until a new version number propagates it into an installed cache.

## [0.3.0] — 2026-08-27 *(reconstructed)*

### Added

- `agents/kb-researcher.md`, the plugin's one exported agent, plus the two
  `knowledge-compiler` hooks (`UserPromptSubmit`, `PreToolUse`/`Skill`) that spawn it when a
  PRP research workflow starts — the knowledge base as a fourth research axis (`4d757a7`,
  `5bb1b0d`). `research_directive: false` disables both, live.
- `/nw-rules-init`: the baseline coding rules as one marker-delimited block in a repo's root
  `CLAUDE.md`, with the repo's own test commands in the one fenced block that `/nw-ship-pr`'s
  validation gate reads (`f377a46`, `70adfae`).
- `/nw-ship-pr` captures every open item a run surfaces into the configured backlog
  (`e28442b`).
- `stack-compiler`: the chosen component per capability as a tracked decision (`8ba1c6d`), the
  per-capability ranking pass (`ff89eea`), and the `st-` `PostToolUse` gate that flags an
  off-stack component the moment a PRD or plan names it (`13aa40e`).

### Fixed

- `hooks.json` nests its hook events under the `hooks` key — the shape fix that made the
  staleness nudge fire at all (`3d62184`).
- The validation gate tests the branch being shipped rather than the main checkout's base
  (`58c6b84`).
- `claudemd-lerner`: an orphan `BEGIN` marker no longer swallows a later block (`c59d42e`).
- `knowledge-compiler` engine `VERSION` 1 → 2 so existing installs pick up the new hooks
  (`0b4613b`).
- `stack-compiler`: a re-rendered selection sheet no longer overwrites what an earlier sitting
  decided (`aa08fa5`); a branch is gated against its own recorded stack (`83175e1`).

## [0.2.0] — 2026-08-20 *(reconstructed)*

### Added

- The delivery lifecycle: `/nw-worktree` and `/nw-ship-pr`, carrying a change from worktree to
  merged PR (`a2b03bd`).
- `compliance-compiler`'s capability layer — the `co-capabilities` command, the derived
  `capabilities.{json,md}`, and plan validation against it (`83dc4dc`, `98e3fbe`).
- `stack-compiler`'s scoping pass: narrow the capability catalog to one product, accountably
  (`b9114cc`), and the capability → stack mapping with its gap report (`69598cd`, `58611f6`).

### Fixed

- `compliance-compiler`: catalog seeding is atomic (`0571595`); the catalog hash is not
  persisted when coverage is incomplete (`8fc9a21`).

## [0.1.0] — 2026-07-23 *(reconstructed)*

### Added

- The first versioned manifest, and the `SessionStart` staleness nudge that reads it
  (`db2ae3a`) — before this there was no version for an install to compare against.
- `knowledge-compiler` (`8bbcef5`) and `claudemd-lerner` (`059c14e`) as installable skills;
  the marketplace manifest, `LICENSE` and the docs tree (`c8e5699`).
- `compliance-compiler`: the parallel extraction engine and its catalog (`f79edeb`), the
  capability-derivation engine (`e2f4bf2`), and the license/cost policy for derived components
  (`b5055e4`).

### Changed

- `compliance-compiler` and `claudemd-lerner` dropped their `SessionStart` hooks, leaving that
  budget to the knowledge concepts (`df54dd1`, `6b55adf`).
