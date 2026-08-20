# A fresh compliance-compiler install lands complete: stack scaffold present, plan validation actually firing

**Plan ID:** `compliance-install-stack-scaffold`
**Source PRD:** None
**PRD Phase:** None
**Source Issue:** None
**Plan Publication:** None

## Outcome

**Problem:** A fresh `compliance-compiler` install leaves a repo where two of the shipped
features do not work, for the same reason: the installer stops short of the state they need.

1. `install.py` seeds the expensive prebuilt catalog (`gdpr/soc2/iso27001.json`,
   `capabilities.json/.md`, `index.md`) but never produces `catalog/stack.json` — the record of
   which component was chosen per capability that `precheck.py:118` and `validate.py:58` both
   read. The only documented way to create it is `/neurawork-cc-harness:co-capabilities`, an LLM
   command, for a file `stack.py --scaffold` derives deterministically in under a second.
2. The `PostToolUse` validator only fires for plan writes under `.claude/PRPs/plans/`
   (`payload/scripts/config.py:36`), but `prp-core` writes plans to
   `"${PRP_HOME:-$HOME/.prp}/<name>-<hash>/plans/"`, and nothing sets `PRP_HOME`. On a default
   install every plan is therefore written outside the repo and silently never validated.

**Affected user:** A developer who installs the harness into their own repo. Observed live in
`/home/felix/projects/grillme-app`: complete catalog, no `stack.json`, hook wired, and not one
plan ever validated. Observed in this repo too — the plan you are reading was written to
`~/.prp/howtobuildsoftware2026-35325a96/plans/` and produced no validation report, while the
twelve plans that happened to be written into `.claude/PRPs/plans/` did.

**User outcome:** After a fresh install the repo holds every artifact the installer can produce
without an LLM, and every plan `prp-core` writes lands inside the repo *and* trips the validator.

**Invariant:** The installer never overwrites data a human or another tool owns — an existing
`catalog/stack.json` (with its `chosen` / `rationale` / `chosen_from` and the `stack-compiler`
`applicable` / `applicability_reason` / `scoped_from` / `ranked` / `ranked_from` fields) and an
existing `env.PRP_HOME` both survive any re-install untouched. The installer stays stdlib-only,
needs no API key and no `uv`.

**Success signal:** A fresh install into an empty git repo produces `catalog/stack.json` and an
`env.PRP_HOME` entry; the next plan `prp-core` writes lands under the repo and produces a report
in `<catalog-dir>/reports/`. `grillme-app` reaches the same state by re-running the installer in
ADOPT mode.

**Approach:** Two guarded, create-if-absent steps in `install.py` — run the target's own
`scripts/stack.py --scaffold`, and set `env.PRP_HOME` to the relative `.claude/PRPs` in the
tracked `.claude/settings.json` — plus widening `is_plan_path()` so the store layout `PRP_HOME`
produces (`.claude/PRPs/<name>-<hash>/plans/`) is recognized alongside the current
`.claude/PRPs/plans/`.

## Recommendation

Both halves are one defect: the install ships a feature whose precondition it does not
establish. Neither half works alone — setting `PRP_HOME` without widening the matcher moves
plans into the repo where the hook still ignores them; widening the matcher without setting
`PRP_HOME` leaves the plans in `~/.prp`. They belong in one change.

**Stack scaffold.** `stack.py --scaffold` is the existing primitive and it is already
stdlib-only: `argparse`, `hashlib`, `json`, `sys`, `pathlib`, plus local `cap_lib` / `config` /
`utils` and `_shared.repo_guard` (`payload/scripts/stack.py:67-79`). `config.py` derives every
path from the script's own grandparent (`payload/scripts/config.py:19-23`), so invoking the copy
`_copy_code()` just wrote resolves the target's catalog with no cwd or env setup. Verified: a
fresh `install.py --catalog-dir cb` into a temp git repo, then plain
`python3 cb/scripts/stack.py --scaffold`, printed
`stack.json: 68 capabilities (0 choice(s) carried, 68 new)` and
`Stack gaps: 62 of 62 applicable mandatory-linked capabilities have no chosen component`,
exit 0, no dependencies installed, no API key present.

**`PRP_HOME` + matcher.** The `<name>-<hash>` suffix is not configurable away: all twelve
`prp-core` skills inline the same resolver, and `PRP_HOME` is its only lever. So `.claude/PRPs`
is the closest a setting can get, and the harness meets it halfway by accepting a `plans/`
directory one level deeper. The value is deliberately **relative**: Claude Code does not expand
`${CLAUDE_PROJECT_DIR}` inside a settings `env` value, and an absolute path would have to live in
the gitignored `settings.local.json`, which `git worktree add` never materializes — so worktrees,
where implementation happens, would lose it. `.claude/PRPs` in the tracked `settings.json`
travels with the repo and commits no `/home/<user>` path.

`coding-suite`'s `/workflow-rules-init` already writes exactly this key with exactly this value
(`engines/workflow-rules-init/set_prp_home.py:52-54`). Writing the same value from the harness
converges with it rather than fighting it; the create-if-absent guard means whichever runs second
is a no-op.

### Evidence

- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:94-116` — `_seed_catalog()`
  seeds six files; `stack.json` is not among them and nothing else in `main()` (lines 207-218)
  produces it.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:76-91` — `_scaffold()` is
  the never-clobber precedent: dirs `mkdir(exist_ok=True)`, `config.json` and `.gitignore` written
  only `if not ... exists()`.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:224-232` — the `--extract`
  branch is the precedent for the installer shelling out to an installed script.
- `plugins/neurawork-cc-harness/engines/_shared/settings.py:23-80` — `merge_hooks()` owns
  `.claude/settings.json` edits for every engine: parse-or-raise, mutate, atomic `tmp` +
  `os.replace`. The `env` writer belongs beside it, not in the installer.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/config.py:36` —
  `PLANS_SUBPATH = ".claude/PRPs/plans"`, the single code-level assumption; every other mention is
  prose (`docs/INSTALL.md:120`, `skills/compliance-compiler/SKILL.md:21`, `commands/co-validate.md:21`).
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/precheck.py:40-55` —
  `is_plan_path()`; measured behavior in Root Cause.
- `/home/felix/.claude/plugins/cache/prp-marketplace/prp-core/fabc81d862c6/skills/prp-plan/SKILL.md:139`
  — the resolver, repeated verbatim in eleven sibling skills.
- `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/1.13.0/engines/workflow-rules-init/set_prp_home.py:14-30,52-54`
  — the same key, the same relative value, and the probe (CC 2.1.234, 2026-08-18) showing
  `${CLAUDE_PROJECT_DIR}` is not expanded in a settings `env` value.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py:45-118`
  and `tests/test_shards_precheck.py:115-130` — the two test surfaces this change plugs into.
- `plugins/neurawork-cc-harness/hooks/version-check.py:63-89` — an installed VERSION below the
  shipped one produces the SessionStart "re-run the installer (ADOPT)" note.

### Alternatives considered

- **Ship a prebuilt `stack.json` in `payload/catalog-seed/`:** this repo's `stack.json` carries our
  scoping and ranking; shipping it would push our product decisions into every install. Stripping
  it would need new machinery in `sync_catalog_seed.py` and a weakened byte-comparison drift guard
  (`tests/test_catalog_seed.py:34-45`). Rejected.
- **Import `stack.scaffold()` into the installer:** needs the target's `scripts/` on `sys.path`,
  where the generic module names `config` / `utils` collide. The subprocess boundary is cheaper and
  matches the `--extract` precedent. Rejected.
- **Patch `prp-core` so plans land exactly in `.claude/PRPs/plans/`:** twelve inlined copies of the
  resolver in a third-party plugin. Rejected — the harness adapts its matcher instead.
- **Leave `PRP_HOME` to `coding-suite`'s `/workflow-rules-init`:** works, but makes the harness's
  own validator depend on a second plugin being installed and a command being remembered. The
  grillme-app install is the counter-example. Rejected as the *only* mechanism; the two remain
  compatible.
- **Write `scripts/state.json` at seed time so `/co-capabilities` sees a hash match:** unnecessary,
  see Root Cause. Rejected.
- **Make a missing `stack.json` distinguishable from "nothing chosen yet" in the hook summary:** a
  real silent-failure seam, but out of this invariant and unreachable through a normal install once
  this lands. See Not building.

## Root Cause

- **Observed failure A — no stack scaffold:** `grillme-app` has a complete
  `compliance-base/catalog/` (127 GDPR, 160 SOC 2, 72 ISO 27001 constraints, 68 capabilities, all
  committed) and no `catalog/stack.json`; the file is produced only by step 3 of
  `commands/co-capabilities.md:31-34`. `main()` calls `_copy_code` → `_scaffold` → `_seed_catalog`
  and stops (`install.py:207-209`); `grep -n "stack" install.py` returns nothing.
- **Observed failure B — plans never validated:** `is_plan_path()` run against the four candidate
  layouts, with the repo root as `repo_root`:

  | path | result |
  |---|---|
  | `<repo>/.claude/PRPs/plans/x.plan.md` | `True` |
  | `<repo>/.claude/PRPs/plans/completed/x.plan.md` | `False` (archived, by design) |
  | `<repo>/.claude/PRPs/<name>-<hash>/plans/x.plan.md` | `False` ← what `PRP_HOME` produces |
  | `~/.prp/<name>-<hash>/plans/x.plan.md` | `False` ← what happens today |

  `PRP_HOME` is set in no settings file on this machine (`~/.claude/settings.json`,
  `~/.claude/settings.local.json`, `<repo>/.claude/settings.json`,
  `<repo>/.claude/settings.local.json` all lack an `env` block), so the default `~/.prp` applies and
  the hook's path filter rejects every plan write before any check runs.
- **Corroboration:** `compliance-base/reports/` holds reports for twelve plans — the ones that were
  written into `.claude/PRPs/plans/` by hand — and none for the plan written to `~/.prp` on
  2026-08-20. The validator works; it is simply not reached.
- **Fix boundary:** `install.py:209` (one guarded call plus one guarded settings write) and
  `payload/scripts/precheck.py:40-55` + `payload/scripts/config.py:36` (the path predicate).
- **Regression proof:** install tests asserting `catalog/stack.json` and `env.PRP_HOME` appear on a
  fresh install and survive ADOPT unchanged; predicate tests asserting the store layout is accepted
  and its `completed/` subdirectory still is not.
- **Correction to the reported premise — verified, not assumed:** the report expected a missing
  `scripts/state.json` to make `/co-capabilities` re-run ~30 SDK agents. It does not.
  `capabilities.py:415-425` has a second branch: with no state file the hash comparison fails, but
  the *constraint-id-set* comparison against the seeded `capabilities.json` succeeds, so the run
  reuses and merely refreshes the hash. Confirmed against the real half-installed repo —
  `uv run --directory compliance-base python scripts/capabilities.py --dry-run` in `grillme-app`
  printed `~ gdpr: constraint id set unchanged — reusing, refreshing hash`, `cluster: (none)`,
  `delta: (none)`, `reuse: gdpr`. The cost of the detour is the detour itself, not agent spend.
- **Remaining uncertainty:** None.

## Implementation Context

### Mandatory reading

| File | Why it matters |
|---|---|
| `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:94-116,184-233` | Seed contract, never-clobber convention, and the existing subprocess precedent |
| `plugins/neurawork-cc-harness/engines/_shared/settings.py:23-80` | The parse → mutate → atomic-replace pattern the `env` writer must follow, and `SettingsError` |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/precheck.py:40-55` | The predicate being widened, including the `completed` exclusion that must survive |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/stack.py:614-655` | `--scaffold`: exits 1 with `No capabilities.json` when the capability layer is absent, else writes `stack.json` + gap report and exits 0 |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py:45-118` | Install test surface (`_init_repo`, `_install`) |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_shards_precheck.py:115-130` | Existing `is_plan_path` cases to extend |

### Existing patterns and primitives

- **Never-clobber scaffolding:** `install.py:76-91` — data written only when absent, code always
  overwritten. Both new steps sit on the data side of that line.
- **Installer shelling out to an installed script:** `install.py:224-232` — `subprocess.run(...,
  check=False)` and a printed outcome; a non-zero return code is reported, not raised.
- **Atomic seed guard:** `install.py:103-110` — a target holding its own constraint catalog skips
  the seed entirely. The scaffold step must survive that case.
- **Settings ownership:** every settings edit in this codebase goes through `_shared/settings.py`
  or `_prune_removed` (`install.py:131-181`); nothing hand-rolls a second writer.
- **Gap report side effect:** `stack.py --scaffold` also writes `reports/stack-gaps-<date>.md`,
  gitignored via `install.py:44-46`.

### Integration points

- `install.py:209` — call site for both new steps, right after `_seed_catalog(target)`.
- `payload/scripts/config.py:36` — the constant the predicate reads.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/VERSION` — bumping it nudges every
  existing install, including `grillme-app`.
- `docs/INSTALL.md:120-130`, `docs/ARCHITECTURE.md:125-130`,
  `plugins/neurawork-cc-harness/skills/compliance-compiler/SKILL.md:21,75-76`,
  `plugins/neurawork-cc-harness/commands/co-capabilities.md:10-13`,
  `plugins/neurawork-cc-harness/commands/co-validate.md:21` — the prose stating the old single
  plan path and the LLM-only stack scaffold.

## Scope

### In scope

- The installer produces `catalog/stack.json` when the capability layer exists and `stack.json`
  does not, via the target's own `scripts/stack.py --scaffold`.
- The installer sets `env.PRP_HOME` to `.claude/PRPs` in the repo's tracked
  `.claude/settings.json`, only when the key is absent, through a new `_shared/settings.py` helper.
- `is_plan_path()` accepts `.claude/PRPs/<store>/plans/*.plan.md` alongside
  `.claude/PRPs/plans/*.plan.md`, keeping `completed/` excluded in both.
- Tests for all three behaviors, at the surfaces that already cover their neighbours.
- Engine VERSION bump plus an ADOPT re-install of this repo's own `compliance-base/`.
- Documentation updated where it states the old paths or the LLM-only scaffold.

### Not building

- Extending the validator to PRD writes — that is harness PRD Phase 7, which will reuse the widened
  predicate rather than reintroduce the narrow one.
- Migrating plans already sitting in `~/.prp/<name>-<hash>/plans/` into the repo; the two plans
  there are moved by hand if wanted, and this repo already archives shipped plans under
  `.claude/PRPs/plans/completed/`.
- Writing `scripts/state.json` or `scripts/last-extract.json` at seed time — verified unnecessary.
- Distinguishing "stack.json missing" from "nothing chosen yet" in the hook summary
  (`payload/hooks/co-post-tooluse.py:72-74`) — separate silent-failure fix.
- Any scoping, ranking or selection at install time; those need a product description and agents.
- Touching `prp-core`, or having the other two engines (`knowledge-compiler`, `claudemd-lerner`)
  write `PRP_HOME` — neither depends on plan paths.

## Delivery Considerations

| Concern | Decision and owned work |
|---|---|
| Discoverability / adoption | The VERSION bump makes `hooks/version-check.py` print the ADOPT re-run note at SessionStart for every existing install. `grillme-app` is repaired that way after merge — non-destructive; it writes the missing `stack.json`, adds `PRP_HOME`, refreshes the code and the VERSION stamp. Its `claudemd-lerner` install is also a version behind and benefits from the same treatment. |
| Compatibility / migration | Create-if-absent throughout: an existing catalog, choice, scope, ranking or `PRP_HOME` value is untouched. The widened predicate is strictly additive — every path accepted today is still accepted. Repos that already ran `coding-suite`'s `/workflow-rules-init` see no settings diff at all. |
| Rollout / reversibility | Reversible by deleting `catalog/stack.json` and removing the `env` entry; no other new artifact (the gap report is gitignored). |
| Observability | Each step prints one line naming what it wrote or why it skipped, so a half-applied install is visible in the installer output instead of being inferred later from a silent hook. |
| Documentation / communication | Task 5 updates `docs/INSTALL.md`, `docs/ARCHITECTURE.md` and the skill/command prose: the install now leaves a scaffolded `stack.json`, sets `PRP_HOME`, and validates plans under either layout. |

## Implementation

### 1. The installer scaffolds `catalog/stack.json` when the capability layer exists without one

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` — UPDATE — add
  `_seed_stack(target)` and call it from `main()` right after `_seed_catalog(target)` (line 209).
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py` — UPDATE.

**Implementation**
- `_seed_stack(target)`: return early when `target/"catalog"/"stack.json"` exists (never clobber a
  decision record) or when `target/"catalog"/"capabilities.json"` is absent (nothing to derive from
  — the atomic-seed-skip case of `install.py:103-110`); in the latter case print one line saying
  the scaffold was skipped because the capability layer is absent.
- Otherwise run `subprocess.run([sys.executable, str(target / "scripts" / "stack.py"),
  "--scaffold"], check=False)`. `stack.py` is stdlib-only and resolves its own paths from `__file__`
  (`payload/scripts/config.py:19-23`), so no cwd, env or `uv` is needed; `_copy_code()` has already
  written that file at this point in `main()`.
- Print the outcome; on a non-zero return code print a warning naming
  `scripts/stack.py --scaffold` as the manual recovery and continue — a failed scaffold must not
  fail an otherwise complete install (same posture as `install.py:231-232`).
- Do not add the file to `GITIGNORE`; `catalog/stack.json` is tracked.

**Tests**
- Fresh install: `catalog/stack.json` exists, parses, `choices` is non-empty, every entry has
  `chosen: None`, and its key count equals the capability count in the seeded `capabilities.json`.
- ADOPT non-clobber: after a first install, write a sentinel `chosen` into one entry, re-install,
  assert the file is byte-identical.
- Atomic-seed-skip: a target holding its own `gdpr.json` but no `capabilities.json` (the existing
  `test_seeding_is_atomic` setup) gets no `stack.json`, and the install still exits 0.
- `stack.json` does not appear in the generated `.gitignore`.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests`

### 2. `_shared` gains a non-clobbering `env` writer for `.claude/settings.json`

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/_shared/settings.py` — UPDATE — add `set_env_default()`
  beside `merge_hooks()`; this module is the single owner of settings edits.
- `plugins/neurawork-cc-harness/engines/_shared/tests/test_settings.py` — UPDATE.

**Implementation**
- `set_env_default(repo_root, key, value) -> str`: read `.claude/settings.json` with the same
  parse-or-`SettingsError` handling as `merge_hooks` (`settings.py:41-51`), then:
  `"already"` when `env[key] == value` (nothing written); `"conflict"` when `env[key]` exists with a
  different value (nothing written — another tool or the user owns it); `"wrote"` otherwise, setting
  `data.setdefault("env", {})[key] = value` and writing atomically via `tmp` + `os.replace`
  (`settings.py:78-80`).
- Creates `.claude/settings.json` and its directory when absent, as `merge_hooks` does.
- Generic in `key`/`value`; it must not know about `PRP_HOME`.

**Tests**
- `wrote` into a repo with no settings file, with a hooks-only settings file, and with an unrelated
  `env` key present (other keys preserved).
- `already` on a second call — file mtime/content unchanged.
- `conflict` when a different value is present — the existing value is still there afterwards.
- Invalid JSON raises `SettingsError` and leaves the file untouched.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests`

### 3. The installer points `PRP_HOME` at the repo

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` — UPDATE — call
  `set_env_default(root, "PRP_HOME", ".claude/PRPs")` in `main()` after the hook merge
  (`install.py:211-216`), so both settings writes sit together.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py` — UPDATE.

**Implementation**
- Import `set_env_default` alongside `merge_hooks` (`install.py:38`).
- Print one line per outcome: written / already present / a differing value left alone. On
  `conflict`, name both values and say plans may land outside `.claude/PRPs`, so the validator may
  not see them — visible, not fatal.
- The value is the relative string `.claude/PRPs`, matching `coding-suite`'s
  `set_prp_home.py:52-54`. Do not attempt `${CLAUDE_PROJECT_DIR}` (not expanded in settings `env`)
  and do not write an absolute path (it would have to live in the gitignored
  `settings.local.json`, which `git worktree add` does not materialize).
- A `SettingsError` here is reported like the hook-merge failure (`install.py:214-216`).

**Tests**
- Fresh install: `.claude/settings.json` has `env.PRP_HOME == ".claude/PRPs"` and the PostToolUse
  hook is still present (both writers coexist).
- ADOPT with a pre-set differing `PRP_HOME`: the value is unchanged after re-install and the
  install exits 0.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests`

### 4. The validator recognizes the `PRP_HOME` store layout

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/config.py:36` — UPDATE.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/payload/scripts/precheck.py:40-55` —
  UPDATE — `is_plan_path()`.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_shards_precheck.py:115-130` —
  UPDATE.
- `compliance-base/scripts/{config,precheck}.py` — UPDATE — the self-host copies, refreshed by the
  ADOPT re-install in Task 6, not hand-edited.

**Implementation**
- Keep `PLANS_SUBPATH = ".claude/PRPs/plans"` as the canonical location and add
  `PRP_SUBPATH = ".claude/PRPs"` next to it, with a comment naming the resolver
  (`"${PRP_HOME:-$HOME/.prp}/<name>-<hash>"`) that produces the deeper form.
- `is_plan_path()` accepts a path whose repo-relative parts start with `.claude/PRPs` and whose
  next component is either `plans` (canonical) **or** a single store segment followed by `plans`.
  Anything deeper is rejected, so the predicate stays a whitelist rather than a substring search.
- The `completed` exclusion applies to the components after `plans` in both forms, unchanged.
- `.plan.md` suffix check, `resolve().relative_to()` handling and the `(ValueError, OSError)`
  guard stay exactly as they are — only the path shape changes.

**Tests**
- Extend the existing cases with: `.claude/PRPs/<store>/plans/x.plan.md` → True;
  `.claude/PRPs/<store>/plans/completed/x.plan.md` → False; `.claude/PRPs/<store>/prds/x.plan.md`
  → False; `.claude/PRPs/a/b/plans/x.plan.md` → False (too deep); an absolute path outside the repo
  → False. Keep the two current cases passing unchanged.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests`
- End-to-end after Task 6: write a throwaway plan under
  `.claude/PRPs/howtobuildsoftware2026-35325a96/plans/` and confirm a report appears in
  `compliance-base/reports/`.

### 5. The docs describe the install as it now behaves

**Files and integration points**
- `docs/INSTALL.md:120-130` — UPDATE — the install leaves a scaffolded `stack.json` and sets
  `PRP_HOME`; `/co-capabilities` refreshes the scaffold after the constraints change.
- `docs/ARCHITECTURE.md:125-130` — UPDATE — same correction in the `co-capabilities` flow.
- `plugins/neurawork-cc-harness/skills/compliance-compiler/SKILL.md:21,75-76` — UPDATE — what a
  fresh install already contains, and both accepted plan locations.
- `plugins/neurawork-cc-harness/commands/co-capabilities.md:10-13` — UPDATE — "ships prebuilt with
  the install" now covers the stack scaffold.
- `plugins/neurawork-cc-harness/commands/co-validate.md:21` — UPDATE — the example path is one of
  two accepted layouts.

**Implementation**
- Surgical wording only, no restructuring. Leave `compliance-base/CLAUDE.md:70` (`stack.json`
  ownership is split) unchanged — still accurate.

**Tests**
- None; prose.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`

### 6. Existing installs are nudged, and this repo's self-host matches the shipped engine

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/compliance-compiler/VERSION` — UPDATE — `2` → `3`.
- `compliance-base/` — UPDATE — refreshed by re-running the installer, not by hand.

**Implementation**
- Bump the engine VERSION so `hooks/version-check.py:63-68` reports installs still on `2` as behind.
- Re-run `python3 plugins/neurawork-cc-harness/engines/compliance-compiler/install.py` from the
  repo root. Expected: ADOPT mode; `compliance-base/VERSION` → `3`; the widened
  `config.py`/`precheck.py` copied in; `env.PRP_HOME` added to `.claude/settings.json`;
  `compliance-base/catalog/stack.json` untouched (it exists and carries this repo's scope and
  ranking — 41 applicable of 68, 41 ranked, 0 chosen).
- Confirm `git diff` after that run touches `compliance-base/VERSION`, the refreshed scripts and
  `.claude/settings.json` — no catalog, no `stack.json`.

**Tests**
- Covered by Tasks 1 and 3; no test for the version constant.

**Validation**
- `git diff --stat compliance-base .claude/settings.json`
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests`

## Acceptance

1. **AC1 — Fresh install is decision-ready:** installing into an empty git repo with no
   `ANTHROPIC_API_KEY`, no `uv sync` and no network produces `catalog/stack.json` with one entry per
   seeded capability, every `chosen` null, and prints the open-decision count; exit 0.
2. **AC2 — Decision data is never clobbered:** re-installing over a target whose `stack.json`
   carries a `chosen` value (or scope/ranking fields) leaves that file byte-identical.
3. **AC3 — No capability layer, no scaffold, no failure:** installing into a target that holds its
   own constraint catalog but no `capabilities.json` writes no `stack.json`, prints why, exits 0.
4. **AC4 — Plans land in the repo:** a fresh install leaves `env.PRP_HOME == ".claude/PRPs"` in the
   tracked `.claude/settings.json`, alongside the PostToolUse hook.
5. **AC5 — A differing `PRP_HOME` is left alone:** re-installing over a repo whose `PRP_HOME` is
   set to something else changes nothing and exits 0, naming the value it found.
6. **AC6 — Both plan layouts are validated:** `is_plan_path()` returns True for
   `.claude/PRPs/plans/x.plan.md` and `.claude/PRPs/<store>/plans/x.plan.md`, and False for the
   `completed/` form of either, for a `prds/` path, and for a deeper nesting.
7. **AC7 — Nothing else regressed:** all five test suites and `ruff` pass, and this repo's
   `compliance-base/catalog/` is unchanged by the ADOPT re-install.

## Validation

| Gate | Command or procedure | Proves |
|---|---|---|
| Focused behavior | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests` | AC1, AC2, AC3, AC4, AC5, AC6 |
| Shared helper | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests` | AC4, AC5 at the writer level |
| Engine suites | `cd plugins/neurawork-cc-harness/engines && for d in _shared knowledge-compiler claudemd-lerner compliance-compiler; do python3 -m unittest discover -s $d/tests; done` | AC7 |
| Prompt assets | `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | AC7 (Task 5 edits) |
| Lint | `cd plugins/neurawork-cc-harness/engines && uvx ruff check` | AC7 |
| Self-host ADOPT | `python3 plugins/neurawork-cc-harness/engines/compliance-compiler/install.py && git diff --stat` | AC2, AC4, AC7 |
| Runtime | Write a throwaway plan under `.claude/PRPs/howtobuildsoftware2026-35325a96/plans/`, then check `compliance-base/reports/` for its report; delete the throwaway afterwards | AC6 end to end — the hook actually fires on the `PRP_HOME` layout |

## Risks and Decisions

| Decision or risk | Recommendation | Evidence / mitigation | Consequence if different |
|---|---|---|---|
| Create-if-absent vs. always re-scaffold on ADOPT | Create-if-absent | `scaffold()` already carries decisions over, but re-running rewrites `generated` on every install, producing a diff that says nothing | Always-scaffold keeps new capabilities in sync automatically at the cost of date churn; `/co-capabilities` step 3 already owns that refresh |
| A scaffold or settings failure fails the install | No — warn and continue | Matches `install.py:231-232`; the rest of the install is complete and useful | Failing hard leaves a half-installed repo over a recoverable, re-runnable step |
| The harness writing a `prp-core` setting | Yes, guarded | Same key and value as `coding-suite`'s `set_prp_home.py:52-54`; absent-only write means whichever tool runs second is a no-op | Leaving it to `/workflow-rules-init` makes the harness's validator depend on a second plugin and a remembered command — the grillme-app case |
| Relative `PRP_HOME` resolves against the session cwd, so a worktree session writes plans inside that worktree | Accept | It is the only value that survives `git worktree add` (tracked `settings.json`); the plan then travels on the feature branch, which is where the work is | An absolute value in `settings.local.json` gives one fixed store but disappears in every worktree |
| Widening the predicate weakens the whitelist | Accept one optional store segment, nothing deeper | Keeps `completed/`, `prds/` and arbitrary nesting out; tested explicitly | A substring match on `plans/` would validate unrelated files |
| Repairing `grillme-app` | Re-run the installer there in ADOPT mode after merge | Non-destructive; writes the missing `stack.json`, adds `PRP_HOME`, refreshes code and VERSION | Leaving it means its hook keeps reading an empty stack and never sees a plan |

## Agent Notes

- Verified before planning, do not re-derive: `python3 <target>/scripts/stack.py --scaffold` runs
  under bare system `python3` with no installed dependencies — spiked in a temp git repo after a
  real `install.py` run, output `stack.json: 68 capabilities (0 choice(s) carried, 68 new)`.
- The `/co-capabilities` "30 agents" worry is disproven (see Root Cause); do not add hash/state
  plumbing to the installer to work around it.
- `is_plan_path()` behavior was measured, not read: the four-row table in Root Cause comes from
  running the real function against the real repo root.
- Harness PRD Phase 7 (`co-` hook on PRD writes) will need the same two-layout treatment for
  `.claude/PRPs/prds` — build it on the constants this plan introduces rather than a second
  hardcoded path.
- This repo archives shipped plans into `.claude/PRPs/plans/completed/`; this plan currently lives
  in the global PRP store, which is exactly what Task 3 stops happening for the next one.
