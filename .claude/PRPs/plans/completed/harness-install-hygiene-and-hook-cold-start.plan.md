# Stop shipping plugin-only tests, and make harness hooks survive a cold checkout

**Plan ID:** `harness-install-hygiene-and-hook-cold-start`
**Source PRD:** None
**PRD Phase:** None
**Source Issue:** https://github.com/neurawork-git/howtobuildsoftware2026/issues/33 and https://github.com/neurawork-git/howtobuildsoftware2026/issues/5 (points 1 and 2 only)
**Plan Publication:** https://github.com/neurawork-git/howtobuildsoftware2026/issues/33#issuecomment-5440056525 and https://github.com/neurawork-git/howtobuildsoftware2026/issues/5#issuecomment-5440056789

## Outcome

**Problem:** Two independent install-time defects.

1. **#33** — `engines/_shared/tests/` holds two tests that assert plugin-level facts:
   `test_manifest.py` (the plugin manifest) and `test_version_check.py` (which reads
   `<plugin>/hooks/version-check.py`). `compliance-compiler` and `stack-compiler` exclude them
   from the `_shared/` copytree; `knowledge-compiler` and `claudemd-lerner` do not. Their
   installs receive both files, where they fail with `FileNotFoundError` because the plugin
   root does not exist inside a target repo. Live in this repo right now:
   `knowledge-base/_shared/tests/` and `claudemd-lerner/_shared/tests/` each carry both files
   and both are **tracked in git**; `compliance-base/_shared/tests/` correctly does not.
2. **#5 points 1 and 2** — every harness hook is a `uv run`, `uv.lock` is gitignored in all four
   install dirs, and the shipped hook timeouts are 10 s (SessionEnd, PreCompact,
   UserPromptSubmit, PreToolUse) and 15 s (SessionStart, both PostToolUse gates). A fresh
   worktree or clone therefore pays a full dependency **resolve plus install** on the first
   hook fire — measured 11.6 s for a single engine in the issue — and is killed before it
   finishes. Claude Code reports that as `failed: Hook cancelled`, which reads as a user
   interrupt. The state does not self-heal: each killed run leaves a partial `.venv`, so the
   next fire is cold again. Since the issue was filed the exposure grew from 2 hooks to 8 —
   `stack-base`'s PostToolUse gate and knowledge-compiler's `UserPromptSubmit` and `PreToolUse`
   retrieval hooks were added.

**Affected user:** Anyone who installs a harness engine into a repo, and anyone running this
harness in a `git worktree` or a fresh clone — which is every user of `/nw-worktree`, the
repo's own sanctioned feature-work path.

**User outcome:** An installed engine's test suite passes on arrival, and harness hooks
complete in a fresh checkout instead of being killed mid-bootstrap, so session capture, the
compliance gate and the stack gate actually run there.

**Invariant:** An installed engine directory contains only files that are valid inside a target
repo — running that directory's tests from a target repo passes with no reference to the plugin
root. And a merged hook entry's timeout is never lowered: a value a user raised by hand stays
raised.

**Success signal:** In a freshly created worktree of this repo, a session start and session end
complete without a `Hook cancelled` line, and `knowledge-base/daily/<today>.md` gains that
session. In a temp-repo install of `knowledge-compiler`, `python3 -m unittest discover -s
_shared/tests` from the installed directory passes.

**Approach:** Three mechanical changes plus a release task.

- **A (#33).** One definition of the plugin-only test list and one `_shared/` refresh function
  in a new plugin-side-only module `engines/_shared_install.py`; all four `_copy_code`
  implementations call it. Delete the two stale tracked copies in this repo.
- **B (#5 point 2).** Ship 60 s for every engine hook, and teach `merge_hooks` to raise an
  existing entry's timeout when it sits **below** the shipped value, so the fix reaches
  installations that already exist. A higher hand-edited value is still kept.
- **C (#5 point 1).** Drop `uv.lock` from the four shipped `.gitignore` bodies, add a
  `prune_gitignore` counterpart to `merge_gitignore` so the already-written ignore line is
  removed from existing installs, and track this repo's four lock files.

## Recommendation

Each change reuses a primitive that already exists in this codebase.

**A** is not "copy three lines into two more installers". That shape is what the current state
already is, and it is why the list drifted: four copies of a tuple that has to stay in sync
with the contents of one directory. The copy block itself is byte-identical in all four
installers (`knowledge-compiler/install.py:75-77`, `claudemd-lerner/install.py:72-74`,
`compliance-compiler/install.py:83-91`, `stack-compiler/install.py:83-91`), so one function
removes the duplication and the seam together, for a net reduction in lines.

Its home is `engines/_shared_install.py`, at the `engines/` level, **not** inside `_shared/`.
Every installer already puts `engines/` on `sys.path` for exactly this kind of import
(`knowledge-compiler/install.py:27`, `claudemd-lerner/install.py:31`,
`compliance-compiler/install.py:34`, `stack-compiler/install.py:35`), and only `_shared/` is
copied into a target — so an install-only helper placed there can never itself become the next
plugin-only file shipped into a repo. Putting it inside `_shared/` would reproduce the defect
this task fixes.

**B** hinges on one existing behavior: `merge_hooks` deliberately keeps a hand-edited timeout
when it finds an entry by marker (`_shared/settings.py:88-93`, implemented at `:120-124`) and
only writes `timeout` on the *append* path (`:140`). Raising the four `_hooks()` tuples alone
would therefore change nothing for any repo that already installed — including this one. A
value below the engine's own shipped minimum is not a preference, it is the bug being fixed, so
the merge becomes a monotonic raise: lift an existing timeout that is lower, leave a higher one
alone. That keeps the documented intent (a user who raised it keeps their value) while letting a
shipped floor propagate. `_shared/tests/test_settings.py:68` and `:151` already pin the
hand-edited case with `99`, which stays above any shipped value and so keeps passing unchanged —
the existing contract is preserved by construction, not by exception.

60 s for every engine hook, no per-event exception. Warm, these hooks cost ~0.2 s, so the
timeout is only ever reached in the cold case the fix exists for; a rule with an exception costs
more to explain than the worst-case edit latency it saves. The plugin's own
`hooks/hooks.json:10` version-check hook stays at 10 s on purpose: it runs under system
`python3` with no `uv` and no venv (`hooks/version-check.py:16`), so it has no cold start to
survive.

**C** needs a removal primitive because `merge_gitignore` is append-only by design
(`_shared/settings.py:161-165`): dropping `uv.lock` from the shipped body is invisible to every
repo that already has the line. The prune is the gitignore counterpart of
`compliance-compiler/install.py:175-183`'s `REMOVED_HOOK_MARKERS` cleanup — an existing,
accepted pattern for "a later release has to undo what an earlier one wrote" — so it belongs
next to `merge_gitignore` with the same idempotent contract.

A committed `uv.lock` removes the *resolve* from a cold start; the wheel install itself is served
from the machine-level `uv` cache after the first download. That is why C alone does not close
#5 and B is not optional.

### Evidence

- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:49` and
  `stack-compiler/install.py:51` — `PLUGIN_ONLY_SHARED_TESTS`, the existing fix, applied at
  `:86-91` in both (copytree `ignore` plus an unlink of copies an older install left behind).
- `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py:75-77` and
  `claudemd-lerner/install.py:72-74` — the same copytree with no exclusion. The defect.
- `git ls-files` — `claudemd-lerner/_shared/tests/test_manifest.py`,
  `claudemd-lerner/_shared/tests/test_version_check.py` and the `knowledge-base/` pair are
  tracked; `compliance-base/_shared/tests/` has neither. The exclusion works where applied.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py:60-61`
  and `stack-compiler/tests/test_install_recon.py:80-81` — the regression test to mirror.
- `plugins/neurawork-cc-harness/engines/_shared/settings.py:88-93, :120-124, :140` — hook merge
  keeps a hand-edited timeout and only writes `timeout` when appending a new entry.
- `plugins/neurawork-cc-harness/engines/_shared/settings.py:161-165` — `merge_gitignore` is
  append-only by design; nothing removes a rule.
- `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py:107-115` (15/10/10/10/10),
  `claudemd-lerner/install.py:101-103` (15/10/10), `compliance-compiler/install.py:169` (15),
  `stack-compiler/install.py:120` (15) — every shipped timeout, all below the 11.6 s cold start.
- `.claude/settings.json:10,15,27,32,44,49,61,66,78,90` — the live installed values in this
  repo: 8 hook entries at 10 or 15 s.
- `plugins/neurawork-cc-harness/engines/{knowledge-compiler,claudemd-lerner,compliance-compiler,stack-compiler}/install.py:48,51,62,63`
  — `uv.lock` in all four shipped `.gitignore` bodies; mirrored live in the four install dirs.
- `plugins/neurawork-cc-harness/scripts/doctor.py:367-373` — the doctor already reports a
  missing `.venv` with `uv sync --directory <dir>` as the fix. #5's suggestion 3 is done; only
  its points 1 and 2 remain, which is exactly this plan's scope.
- Knowledge base: no prior finding exists on the installer copytree, hook cold start, `uv.lock`
  pinning or the settings merge. The `kb-researcher` sweep of all 22 articles plus backlinks
  returned only adjacent material —
  `knowledge-base/knowledge/concepts/plugin-version-bump-propagates-cache.md` (a fix reaches an
  installed cache only via a version bump, which Task 4 owns). This is uncompiled ground, so
  nothing here re-derives a recorded finding.

### Alternatives considered

- **Copy the three-line exclusion into the two missing installers.** Purely mechanical, but
  leaves four copies of a list that must track the contents of `_shared/tests/`. The next
  plugin-only test added there reopens the same issue in whichever installers were missed.
- **Put the shared install helper in `_shared/`.** It would then be copied into every target
  repo — a new plugin-only file inside the directory whose plugin-only files are the bug.
- **Raise only the shipped `_hooks()` values, leave `merge_hooks` alone.** Reaches new installs
  only. Every existing install — including this repo and the reporter's — keeps 10/15 s.
- **Lower the two PostToolUse gates to 30 s while capture hooks get 60 s.** Bounds worst-case
  edit latency, but only in the cold case, and buys that with a per-event exception to explain
  and to keep consistent across four installers.

## Implementation Context

### Mandatory reading

| File | Why it matters |
|---|---|
| `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:44-92` | The exclusion + copytree + stale-unlink to hoist verbatim, and the `_is_adopt`/`_copy_code` contract around it |
| `plugins/neurawork-cc-harness/engines/_shared/settings.py:74-155` | `merge_hooks`: the marker lookup, the migration branches, and the single place `timeout` is written |
| `plugins/neurawork-cc-harness/engines/_shared/settings.py:155-200` | `merge_gitignore`'s append-only contract and its comment/blank-line grouping, which `prune_gitignore` must not disturb |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:175-232` | `REMOVED_HOOK_MARKERS` + `_prune_stale_hooks`: the precedent for undoing what an earlier release wrote |
| `plugins/neurawork-cc-harness/engines/compliance-compiler/tests/test_install_recon.py:40-90` | The install-into-temp-repo test harness and the exclusion assertions to mirror |

### Existing patterns and primitives

- **Install-time `sys.path` bootstrap:** `knowledge-compiler/install.py:27` — every installer
  already imports from `engines/`, so `_shared_install` needs no new mechanism.
- **Idempotent merge contract:** `_shared/settings.py:84-85` and `:158-159` — both merges return
  `True` when the file changed and `False` when everything was already present.
  `prune_gitignore` follows the same contract.
- **ADOPT-mode refresh:** each `_copy_code` always overwrites code and never touches data
  (`compliance-compiler/install.py:74`), which is why the stale-file unlink is part of the copy
  and not a separate migration step.

### Integration points

- `plugins/neurawork-cc-harness/engines/*/install.py` `_copy_code` — the four call sites for
  `refresh_shared`.
- `plugins/neurawork-cc-harness/engines/*/install.py` `_scaffold` — where `merge_gitignore` runs
  today (`knowledge-compiler/install.py:100`), and where the prune call joins it.
- `.claude/settings.json` — this repo's own eight hook entries, updated by re-running the four
  installers once B has landed.

## Scope

### In scope

- Issue #33 in full, for all four engines, with the duplication removed.
- Issue #5 point 1 (track `uv.lock`) and point 2 (raise hook timeouts), including reaching
  installations that already exist.
- Deleting the two stale tracked test copies in this repo's self-host installs.
- The plugin version bump and CHANGELOG entry that carry the fixes into installed caches.

### Not building

- **Issue #5 points 3 and 4.** Point 3 (surface worktree provisioning) is already delivered by
  `doctor.py:367-373`. Point 4 (run the capture hooks on plain `python3`, no `uv`) is a
  different change with its own dependency-boundary design; it is not needed once the timeout
  covers the cold start.
- **Issues #15, #16, #18.** Separate defects, not in this request.
- **Anything in the open `feature/doctor-currency` worktree.** That branch fixes `update.py`'s
  missing `sys.path` bootstrap, the queue-check severity, the doctor's plugin-currency section
  and the credentials finding. No file in this plan overlaps it except the release task —
  see Risks.
- **A shared bootstrap for the `payload/scripts/*.py` `sys.path` lines.** Same surface family,
  but runtime code inside targets, and the doctor branch is actively editing one of them.

## Delivery Considerations

| Concern | Decision and owned work |
|---|---|
| Discoverability / adoption | All three fixes are install-time; they reach a user's repo only on the next install/ADOPT run of the engine, and reach installed plugin caches only after a version bump plus `/plugin update` + `/reload-plugins` (`knowledge-base/knowledge/concepts/plugin-version-bump-propagates-cache.md`). Task 4 owns the bump and the CHANGELOG entry naming the required re-install. |
| Compatibility / migration | Two migrations are the point of the plan: the timeout floor-raise reaches existing `.claude/settings.json` entries, and `prune_gitignore` removes an ignore line an earlier release wrote. Both are idempotent and both leave unrelated user content untouched. |
| Rollout / reversibility | `git revert` restores every shipped default. It does **not** re-lower a timeout already raised in a user's settings.json, and does not re-add the pruned `uv.lock` line — stated here because the migrations are deliberately one-way. Neither leaves a broken state. |
| Observability | `/nw-doctor` is the check surface: it already reports engine version drift and a missing `.venv`. After Task 2, a settings.json read shows 60 s on all eight entries. |
| Documentation / communication | CHANGELOG (Task 4). Root `CLAUDE.md` needs no change: no command, engine responsibility or architecture boundary moves. `docs/INSTALL.md` gains nothing — the install commands are unchanged. |

## Compliance

**Capabilities**: none — this change edits developer tooling that runs on the operator's own
machine: which files an installer copies into a local directory, an integer timeout in a local
settings file, and which lines a local `.gitignore` carries. It processes no personal data, adds
no network path, no data store, no interface and no authentication or authorisation surface, and
changes no runtime data flow. No capability in `compliance-base/catalog/capabilities.json` is
delivered by it.

## Implementation

### 1. One definition of the plugin-only shared tests, used by all four installers

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/_shared_install.py` — CREATE — install-only helpers
  shared by the engines. Lives at `engines/` level precisely because only `_shared/` is copied
  into a target repo, so nothing here can ever be shipped into an install.
- `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py:75-77` — UPDATE — call the
  helper.
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/install.py:72-74` — UPDATE — same.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:49, :83-91` — UPDATE —
  drop the local constant and block, call the helper.
- `plugins/neurawork-cc-harness/engines/stack-compiler/install.py:51, :83-91` — UPDATE — same.
- `claudemd-lerner/_shared/tests/test_manifest.py`, `claudemd-lerner/_shared/tests/test_version_check.py`,
  `knowledge-base/_shared/tests/test_manifest.py`, `knowledge-base/_shared/tests/test_version_check.py`
  — DELETE — `git rm` the four stale tracked copies in this repo's self-host installs.

**Implementation**
- `_shared_install.py` holds `PLUGIN_ONLY_SHARED_TESTS = ("test_manifest.py", "test_version_check.py")`
  and `refresh_shared(shared_src: Path, target: Path) -> None`, which performs the copytree with
  `ignore=shutil.ignore_patterns("__pycache__", *PLUGIN_ONLY_SHARED_TESTS)` and
  `dirs_exist_ok=True`, then unlinks any of the named files an older install left behind. Body
  lifted from `compliance-compiler/install.py:83-91`; keep the comment explaining *why* the two
  tests stay in the plugin, since that reason is the whole point of the module.
- Each installer imports it beside its existing `_shared` imports (the `sys.path.insert` at
  `knowledge-compiler/install.py:27` and its three siblings already makes this resolvable) and
  replaces its copytree block with one call.
- The two engines that had no exclusion gain the stale-file unlink for free, which is what
  cleans up an existing install on its next ADOPT run.

**Tests**
- `plugins/neurawork-cc-harness/engines/knowledge-compiler/tests/test_install_recon.py` and
  `claudemd-lerner/tests/test_install_recon.py`: in the fresh-install case, assert neither
  `_shared/tests/test_manifest.py` nor `_shared/tests/test_version_check.py` exists in the
  installed directory, and that a normal shared test (`test_settings.py`) does — mirroring
  `compliance-compiler/tests/test_install_recon.py:60-61`.
- Same two files: an ADOPT case that pre-creates both stale files in the target and asserts the
  re-install removes them. This is the half no engine currently covers, and it is what repairs
  installs in the wild.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s knowledge-compiler/tests`
  — fresh-install and ADOPT exclusion assertions pass.
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s claudemd-lerner/tests`
  — same.
- `git ls-files | grep -E '_shared/tests/(test_manifest|test_version_check)\.py'` — no output.

### 2. A shipped timeout floor that reaches installations that already exist

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/_shared/settings.py:120-124` — UPDATE — raise a lower
  existing timeout inside the existing-entry branch of `merge_hooks`.
- `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py:107-115` — UPDATE — five
  hooks to 60.
- `plugins/neurawork-cc-harness/engines/claudemd-lerner/install.py:101-103` — UPDATE — three
  hooks to 60.
- `plugins/neurawork-cc-harness/engines/compliance-compiler/install.py:169` — UPDATE — 60.
- `plugins/neurawork-cc-harness/engines/stack-compiler/install.py:120` — UPDATE — 60.
- `.claude/settings.json` — UPDATE — this repo's own eight entries, produced by re-running the
  four installers, not by hand.

**Implementation**
- In `merge_hooks`, beside the existing command-drift and matcher-move branches, add: when the
  existing entry's `timeout` is missing or lower than the shipped value, set it to the shipped
  value and mark `changed`. A higher value is left alone. Update the docstring at
  `_shared/settings.py:88-93` — it currently promises the timeout is kept, and after this change
  the promise is narrower and must say so.
- Leave `hooks/hooks.json:10` at 10 s: that hook runs under system `python3` with no `uv` and no
  venv (`hooks/version-check.py:16`), so it has no cold start to survive.
- Apply to this repo by re-running the four engine installers (the sanctioned route), then read
  `.claude/settings.json` back to confirm eight entries at 60.

**Tests**
- `plugins/neurawork-cc-harness/engines/_shared/tests/test_settings.py`: an existing entry with
  `timeout: 10` and a shipped 60 is raised to 60; an existing entry with `timeout: 99` keeps 99
  (already covered at `:68` and `:151` — confirm both still pass rather than duplicating them);
  a second merge with no change returns `False`, so the raise stays idempotent.
- `knowledge-compiler/tests/test_install_recon.py:102` reads `install._hooks("kb")` directly —
  extend it to assert every shipped tuple carries 60, so a future hook added at 10 fails here.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests`
  — raise, keep-higher and idempotency cases pass.
- `python3 -c "import json;d=json.load(open('.claude/settings.json'));print(sorted(h['timeout'] for e in d['hooks'].values() for g in e for h in g['hooks']))"`
  — eight values, all 60.

### 3. Track `uv.lock`, and un-ignore it where an earlier release wrote the rule

**Files and integration points**
- `plugins/neurawork-cc-harness/engines/_shared/settings.py` — UPDATE — add `prune_gitignore`
  next to `merge_gitignore`.
- `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py:48`,
  `claudemd-lerner/install.py:51`, `compliance-compiler/install.py:62`,
  `stack-compiler/install.py:63` — UPDATE — drop `uv.lock` from the `GITIGNORE` body, add
  `REMOVED_GITIGNORE_RULES = ("uv.lock",)`, and call the prune from `_scaffold` beside the
  existing `merge_gitignore` call (`knowledge-compiler/install.py:100`).
- `knowledge-base/uv.lock`, `claudemd-lerner/uv.lock`, `compliance-base/uv.lock`,
  `stack-base/uv.lock` — ADD — `git add` the four existing lock files in this repo.
- `knowledge-base/.gitignore`, `claudemd-lerner/.gitignore`, `compliance-base/.gitignore`,
  `stack-base/.gitignore` — UPDATE — produced by the prune, by re-running the installers.

**Implementation**
- `prune_gitignore(target, rules)` removes lines whose stripped form equals a named rule, leaves
  every other line — including comments, blanks and the user's own entries — byte-identical in
  place, writes only when something was removed, and returns the same `True`/`False` contract as
  `merge_gitignore`. No file, no write when the file is absent. Same shape as
  `compliance-compiler/install.py:175-183`'s hook-marker cleanup, one level down.
- Order inside `_scaffold` is prune-then-merge or merge-then-prune indifferently, since the two
  rule sets are disjoint; put the prune first so the merge sees the final file.
- `.venv/` stays ignored. Only `uv.lock` moves.

**Tests**
- `_shared/tests/test_settings.py`: a `.gitignore` containing `uv.lock` among other rules loses
  exactly that line and keeps the rest byte-identical; a second call returns `False`; a missing
  file is a no-op returning `False`.
- `knowledge-compiler/tests/test_install_recon.py` and `claudemd-lerner/tests/test_install_recon.py`:
  after an ADOPT install over a `.gitignore` that already has `uv.lock`, the line is gone and
  the file's other rules survive.

**Validation**
- `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests`
  — prune behaviour and idempotency pass.
- `git check-ignore -v knowledge-base/uv.lock` — exit 1, no output: the file is no longer ignored.
- `git ls-files | grep -c 'uv\.lock'` — `4`.

### 4. Release the fixes so installed caches receive them

**Files and integration points**
- `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` — UPDATE — version bump.
- `plugins/neurawork-cc-harness/CHANGELOG.md` — UPDATE — entry.
- `plugins/neurawork-cc-harness/engines/*/VERSION` — UPDATE — bump each engine whose payload or
  installer changed. All four installers change; no `payload/` file changes, so judge each
  engine's VERSION against what that file is documented to track and state the reading used.

**Implementation**
- Minor bump, not patch: `merge_hooks` and `merge_gitignore` gain behaviour that rewrites a
  user's existing `.claude/settings.json` and `.gitignore`. That is more than the reporting-only
  change that justified the last patch bump
  (`knowledge-base/knowledge/concepts/semver-patch-for-reporting-only-change.md`).
- The CHANGELOG entry states what a user must do to get the fixes: `/plugin update` +
  `/reload-plugins`, then re-run each installed engine's install skill — the timeout raise and
  the gitignore prune only happen during an install run.
- Take the base version from whatever is on `main` at the time; the `feature/doctor-currency`
  branch bumps the same file (see Risks).

**Tests**
- No new test. `plugins/neurawork-cc-harness/tests/` already pins manifest shape, and
  `_shared/tests/test_manifest.py` asserts every hook entry is a command with an integer timeout
  (`:73-82`).

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` — plugin asset
  guards pass.
- `python3 plugins/neurawork-cc-harness/scripts/doctor.py` — no new WARN; engine versions
  consistent between plugin and installs.

## Acceptance

1. **AC1 — an installed engine ships no plugin-only test.** Installing `knowledge-compiler` or
   `claudemd-lerner` into a repo produces an `_shared/tests/` directory containing neither
   `test_manifest.py` nor `test_version_check.py`, and containing the shared tests that do apply.
2. **AC2 — an existing install is repaired on upgrade.** Re-running any of the four installers
   over a target that already holds those two files removes them.
3. **AC3 — the exclusion has one definition.** `PLUGIN_ONLY_SHARED_TESTS` and the `_shared/`
   copy exist once, in `engines/_shared_install.py`, and no installer carries its own copy.
4. **AC4 — shipped hook timeouts are 60 s.** Every tuple returned by every engine's `_hooks()`
   carries `60`.
5. **AC5 — a low timeout is raised, a high one is kept.** `merge_hooks` over a settings.json
   whose matching entry has `timeout: 10` writes `60`; over one with `99` it leaves `99`; a
   repeat merge reports no change in both cases.
6. **AC6 — `uv.lock` is tracked and no longer ignored.** The four lock files in this repo are in
   `git ls-files`, `git check-ignore` claims none of them, and re-running an installer over a
   `.gitignore` that still carries the rule removes exactly that line.
7. **AC7 — nothing else in the ignore file moves.** After the prune, every other line of a
   target's `.gitignore`, including user-added rules and the shipped comments, is unchanged.
8. **AC8 — the fixes are released.** The plugin version is bumped and the CHANGELOG names the
   re-install step required for the two migrations to run.

## Validation

| Gate | Command or procedure | Proves |
|---|---|---|
| Shared helpers | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests` | AC5, AC6, AC7 |
| knowledge-compiler | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s knowledge-compiler/tests` | AC1, AC2, AC4 |
| claudemd-lerner | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s claudemd-lerner/tests` | AC1, AC2 |
| compliance-compiler | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s compliance-compiler/tests` | AC3 — no regression where the exclusion already worked |
| stack-compiler | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s stack-compiler/tests` | AC3, plus `test_payload_drift.py` |
| Plugin assets | `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | AC8 |
| Lint | `cd plugins/neurawork-cc-harness/engines && uvx ruff check` | Style gate on the new module and the edited installers |
| Harness health | `python3 plugins/neurawork-cc-harness/scripts/doctor.py` | No new WARN; installs consistent |
| Runtime, manual | `git worktree add ../hbs-coldstart-check -b throwaway/coldstart`, start and end a Claude Code session inside it, then `git worktree remove --force ../hbs-coldstart-check` | The success signal: no `Hook cancelled`, and today's `knowledge-base/daily/` log gains that session |

## Risks and Decisions

| Decision or risk | Recommendation | Evidence / mitigation | Consequence if different |
|---|---|---|---|
| The open `feature/doctor-currency` worktree also bumps `plugin.json` and edits `CHANGELOG.md` (its Task 7) | Land that PR first, then start Task 4 from the version it leaves on `main` | `git worktree list` shows it at `c454a12` with both files modified; no other file overlaps this plan | A conflicting bump, or two releases claiming the same version |
| A 60 s PostToolUse gate can block a `Write`/`Edit` for up to a minute in a cold checkout | Accept | Warm cost is ~0.2 s, so the ceiling is only reached where the alternative today is a silently dead gate | A per-event exception to carry across four installers |
| `merge_hooks` no longer preserves a *lowered* hand-edited timeout | Accept, and say so in the docstring | A value below the engine's shipped minimum is the defect being fixed, not a preference; anything higher is still kept, which is what `test_settings.py:68` and `:151` pin | Existing installs keep 10/15 s and #5 stays open for them |
| A committed `uv.lock` pins dependency versions until someone runs `uv lock --upgrade` | Accept — that is the point | Removing the resolve is what makes a cold start survivable | Fresh environments keep re-resolving and picking up new `claude-agent-sdk` releases unannounced |
| `engines/_shared_install.py` is a second shared location beside `_shared/`, which root `CLAUDE.md` calls the single source of truth for shared helpers | Keep them distinct and name the distinction in the module docstring: `_shared/` is shipped into targets, `_shared_install.py` never leaves the plugin | Putting it in `_shared/` would ship a plugin-only file into every install — the exact defect of #33 | Either the bug returns, or four copies of the list drift again |

## Agent Notes

- The self-host installs in this repo (`knowledge-base/`, `claudemd-lerner/`, `compliance-base/`,
  `stack-base/`) are live installs, so Tasks 2 and 3 change tracked files there as a *result* of
  re-running the installers. Re-run the installers rather than hand-editing those files, so the
  committed state is exactly what a user's install produces.
- `stack-compiler/tests/test_payload_drift.py` compares the plugin payload against the installed
  copy. No `payload/` file changes in this plan, but run that suite anyway after re-running the
  installers.
- The throwaway worktree in the manual gate must be removed afterwards; it is a verification
  fixture, not a Hand worktree, so it does not go through `/nw-worktree`.
