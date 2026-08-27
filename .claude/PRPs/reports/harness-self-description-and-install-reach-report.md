# Implementation Report

**Plan:** `/home/felix/projects/howtobuildsoftware2026-harness-self-description/.claude/PRPs/plans/harness-self-description-and-install-reach.plan.md`
**Branch:** `feature/harness-self-description`
**Status:** `COMPLETE`

## Outcome

The plugin no longer ships a statement about itself that is untrue, and an installer change
now reaches an install that already exists.

- **`/nw-ship-pr` binds what it uses.** The ten unbound `$MAIN_ROOT` uses are gone. Both roots
  (`<wt-root>`, `<main-root>`) are resolved once in Phase 0.1 and inserted literally
  everywhere after; the Ground rules carry the single statement of what they are and why they
  cannot be shell variables. A guard test pins it.
- **The compliance hook only wakes for writes.** `merge_hooks` grew the migration half of the
  matcher story: an entry found under a different matcher is **moved** into the requested
  group and an emptied group is dropped. `compliance-compiler` registers under
  `Write|Edit|MultiEdit`. Proven live on this repo: the `co-` hook moved out of the catch-all
  group, the unrelated `st-` hook stayed in it, one entry total.
- **New ignore rules reach old installs.** `_shared/settings.py` gained `merge_gitignore`,
  append-only; the three identical create-if-absent blocks are gone. `catalog/.shards/` was
  the live case.
- **The release says what it contains.** `plugin.json` is `0.4.0` with `keywords`, `homepage`,
  `repository`; `CHANGELOG.md` was created, with the pre-`0.4.0` sections marked reconstructed.
  A test fails any release whose version has no section.
- **The README describes the plugin that exists** — three installable skills with their install
  dirs and hook prefixes, three install-free workflow surfaces, the `kb-researcher` agent, the
  slash-command list, and `stack-compiler`'s deliberate not-installable state with its PRD
  phase. The phase-numbered Status block is replaced by links to the two PRDs.
- **Existing installs are told to upgrade:** engine `VERSION` bumps (knowledge-compiler 2→3,
  claudemd-lerner 3→4, compliance-compiler 4→5), and this repo's three install dirs were
  refreshed through their own installers, not by hand.

## Validation

| Command or check | Result | Evidence |
| --- | --- | --- |
| `python3 -m unittest discover -s _shared/tests` (from `engines/`) | passed | Ran 55 tests, OK (44 before) |
| `python3 -m unittest discover -s knowledge-compiler/tests` | passed | Ran 36 tests, OK |
| `python3 -m unittest discover -s claudemd-lerner/tests` | passed | Ran 30 tests, OK |
| `python3 -m unittest discover -s compliance-compiler/tests` | passed | Ran 163 tests, OK (161 before) |
| `python3 -m unittest discover -s stack-compiler/tests` | passed | Ran 189 tests, OK — AC8, payload/self-host still byte-identical |
| `python3 -m unittest discover -s tests` (from plugin root) | passed | Ran 23 tests, OK (22 before) |
| `uvx ruff check <the 7 files touched>` | passed | 11 findings, all pre-existing: verified identical on the HEAD copy of each file (I001/BLE001/PLW1510/RUF100 in untouched lines). `_shared/settings.py` alone: "All checks passed!" |
| Live ADOPT of all three engines | passed | compliance printed "Hooks merged"; the other two "already present" |
| `python3 -c "…['hooks']['PostToolUse']"` on the repo's real `.claude/settings.json` | passed | `['', 'Write|Edit|MultiEdit']` — `co-` moved, `st-` untouched, one entry each (AC2 end to end) |
| Second ADOPT of compliance-compiler | passed | `md5sum .claude/settings.json` identical before/after; "Hooks already present" (AC3) |
| `git diff --stat <the three install dirs' .gitignore>` after ADOPT | passed | empty — a fully-covered file is not rewritten (AC4 idempotency) |
| `diff -r --exclude=__pycache__` payload↔install for all three engines, plus `_shared/` | passed | no output (AC7) |
| `VERSION` parity engine↔install | passed | 3/3, 4/4, 5/5 |
| `grep -ni 'two\|in progress' README.md` | passed | no "two skills" claim, no phase-progress claim left (AC6) |

`uvx ruff check` over the whole `engines/` tree reports 146 pre-existing findings and is a
permanent RED in this repo (already recorded in `.claude/BACKLOG.md` as the reason it is
excluded from the `/nw-ship-pr` validation gate), so it was run per touched file instead.

## Deviations and Decisions

- **`0.4.0`, not the plan's `0.3.0`.** The manifest was already at `0.3.1` when this landed
  (commit `04e4ba1`, after the plan was written). Same reasoning, next minor: installed
  behaviour changes (hook matcher, ignore-rule propagation).
- **`merge_hooks` keeps its optional 5th tuple element** instead of the plan's
  `(event, matcher, command, timeout, marker)`. The matcher parameter had already shipped in
  that shape (`4d757a7`, for `pre-skill.py`'s `Skill` matcher); rewriting the tuple order
  would have churned four call sites to no effect. Only the **migration** half was missing and
  is what this adds. The plan's audit intent is met by a comment at each `_hooks()` naming why
  its events take the catch-all group.
- **`hooks` is typed `Sequence`, not `list`.** `list` is invariant, so the compliance
  installer's uniform list of 5-tuples did not type-check against a list of the union.
- **The manifest/CHANGELOG test went into `engines/_shared/tests/test_manifest.py`**, not
  `tests/test_skill_assets.py`. The manifest guard already lived there; the skill-asset module
  is about prompt-only assets.
- **`stack-compiler.prd.md` Phase 4 is now `complete`**, not `pending` as the plan states. Only
  Phase 5 (the installer) is still pending, which is what the README says.
- **Four doc files outside the plan's scope were corrected** — `CLAUDE.md`, `plugins/CLAUDE.md`,
  `stack-base/CLAUDE.md`, `docs/ARCHITECTURE.md`. Each asserted that the `co-` and `st-` hooks
  share one `matcher: ""` group, or that the installer "writes `.gitignore`". This change made
  those sentences false; leaving them would have violated the plan's own invariant. The edits
  are one or two sentences each and touch nothing else.
- **`.claude/BACKLOG.md`**: the `$MAIN_ROOT` item is ticked. The other backlog items in the file
  are untouched.
- **`stack-base/_shared/settings.py` was deliberately left stale.** It is an older hand-installed
  copy with no matcher support at all, and nothing in `stack-base/` imports `merge_hooks`. It
  gets refreshed by `stack-compiler`'s Phase 5 installer, and touching it by hand here would be
  exactly the thing the engine/payload split exists to prevent.
- **Not built, per the plan:** `stack-compiler`'s installer/skill/commands, a fourth
  `ENGINES` entry, a git-diff version-bump CI guard.

## Review Dispositions

None.

## Completion Gate

- **Plan tasks complete:** `Yes` — all five.
- **Acceptance criteria satisfied:** `Yes` — AC1–AC8, each mapped to a row above.
- **Unresolved blocker:** `None`
- **Recovery:** `None`

## Intended Commit Scope

One commit: the five plan tasks plus the four doc corrections and the backlog tick they
require. Includes the three self-host install dirs refreshed by their own installers and the
repo's `.claude/settings.json` with the migrated hook entry — the live proof of AC2.

## Delivery

- **Commits:** `5c74a5e — feat(harness): the plugin describes itself truthfully and an installer change reaches an existing install`
- **Pull Request:** `https://github.com/neurawork-git/howtobuildsoftware2026/pull/41`
- **Base / Head:** `main <- feature/harness-self-description`
- **Source PRD:** `None` (plan metadata: `Source PRD: None`)
- **Tracked follow-ups:** `None`
