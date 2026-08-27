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
