# Feature: neurawork-cc-harness — Exemplary Docs & Self-Host (Phase 4)

## Summary

Make `neurawork-cc-harness` the teachable, copyable example it claims to be. This is a **docs + distribution + self-host** phase, not a code-pattern phase. Four strands of work: (1) add a repo-root **MIT LICENSE** and fix the `README.md` `License: TBD`; (2) add a net-new **`.claude-plugin/marketplace.json`** at the repo root so any *second* repo can install the harness with two `/plugin` commands; (3) write a single canonical **install/upgrade guide** (`docs/INSTALL.md` + a root README pointer) covering local-dev loading, second-repo distribution, the per-skill recon→ask→install flow, **FQN invocation**, and **when-to-use vs `coding-suite`**; (4) **self-host** the harness on *this* repo by actually installing the skill(s) — landing `knowledge-base/` + `.claude/settings.json` hooks — and committing them as the worked example.

## User Story

As a NeuraWork engineer or customer evaluating the harness
I want a clear install/upgrade guide plus a repo that visibly runs its own harness and carries a real license
So that I can confidently upgrade a *second* repo by copying the documented steps, and trust the project legally.

## Problem Statement

The harness is built but not *teachable* or *legally usable yet*: there is no repo-root LICENSE (README says `License: TBD`), no way for another repo to install the plugin (no `marketplace.json`), no install/upgrade guide, no documented "when to use this vs `coding-suite`", and this repo does **not** run its own harness (no `knowledge-base/`, no `.claude/settings.json`). Until those exist, "any repo can be upgraded by installing it" (PRD core promise) is unverified.

## Solution Statement

Add the missing distribution + legal + doc artifacts and dogfood the harness on this repo. The plugin already carries MIT (`plugins/neurawork-cc-harness/LICENSE`) and documents the FQN/collision story in two places — Phase 4 propagates those upward (root LICENSE, root guide) rather than re-deciding them. Distribution uses Claude Code's `git-subdir` marketplace source so a plugin nested at `plugins/neurawork-cc-harness/` installs cleanly from GitHub. Self-host runs the *existing* `knowledge-compiler` install flow against this repo; the `claudemd-lerner` half of self-host is **gated on Phase 3** (not yet on disk) and is split into a clearly-marked deferred task so the rest of Phase 4 is not blocked.

## Metadata

| Field            | Value                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| Type             | NEW_CAPABILITY (docs, distribution manifest, self-host) + ENHANCEMENT (README/license) |
| Complexity       | MEDIUM — low technical risk, but a real dependency gate (Phase 3) and a "repo is both plugin source AND consumer" nuance |
| Systems Affected | Repo root (`LICENSE`, `README.md`, `docs/`, `.claude-plugin/marketplace.json`); `.claude/settings.json` (self-host hooks); `knowledge-base/` (self-host payload); plugin `README.md` |
| Dependencies     | Phase 2 **complete** (knowledge-compiler shippable); Phase 3 **INCOMPLETE** (claudemd-lerner not on disk — gates one task); `uv`; git; `ANTHROPIC_API_KEY` (only for the optional `--seed` smoke) |
| Estimated Tasks  | 10 (8 unblocked now + 1 gated on Phase 3 + 1 verification) |

---

## ⚠️ Dependency Gate (read first)

PRD Phase 4 `Depends: 2, 3`. **Phase 2 is complete; Phase 3 (`claudemd-lerner`) is NOT implemented** — `engines/claudemd-lerner/` and `skills/claudemd-lerner/SKILL.md` do **not exist on disk** (confirmed by codebase exploration; `skills/.gitkeep` is still a placeholder). The user explicitly chose to plan Phase 4 anyway.

Consequence: the PRD success signal "this repo self-hosts the harness" with **both** skills cannot be fully met until Phase 3 lands. This plan therefore:

- Does **all** Phase-4 work that does NOT depend on lerner **now** (license, marketplace, guide, self-host of `knowledge-compiler`).
- Isolates the lerner self-host into **Task 8 (GATED)** — execute only after Phase 3 is complete.
- Marks Phase 4 `complete` in the PRD only when Task 8 has also run (or the user accepts a "knowledge-compiler-only" partial completion explicitly).

---

## UX Design

### Before State
```
╔══════════════════════════════════════════════════════════════════════╗
║                            BEFORE STATE                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  Repo root:  README.md (License: TBD) · CLAUDE.md · plugins/ · .git    ║
║    NO LICENSE file.  NO docs/.  NO .claude-plugin/marketplace.json.    ║
║    NO .claude/settings.json.  NO knowledge-base/.                      ║
║                                                                        ║
║  Plugin builds, has its own MIT LICENSE + FQN note, but:               ║
║    • a 2nd repo has NO documented way to install it                   ║
║    • this repo does NOT run its own harness (no dogfooding)           ║
║    • no "when to use vs coding-suite" guidance anywhere               ║
║  PAIN: the "copyable example" promise is unverified.                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

### After State
```
╔══════════════════════════════════════════════════════════════════════╗
║                             AFTER STATE                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  Repo root gains:                                                      ║
║    LICENSE (MIT) ◄── matches plugins/.../LICENSE; README License: MIT  ║
║    .claude-plugin/marketplace.json ◄── git-subdir → plugins/neura...   ║
║    docs/INSTALL.md ◄── the canonical install/upgrade guide            ║
║    docs/WHEN-TO-USE.md ◄── neurawork-cc-harness vs coding-suite       ║
║                                                                        ║
║  Self-host (dogfood) of knowledge-compiler:                            ║
║    /neurawork-cc-harness:knowledge-compiler → recon→ask→install        ║
║      → knowledge-base/ (hooks, scripts, _shared, knowledge/, config)   ║
║      → .claude/settings.json gains 3 hooks                            ║
║    git commit → this repo now RUNS its own harness                    ║
║                                                                        ║
║  Second repo upgrade path (documented + verified):                     ║
║    /plugin marketplace add <owner>/howtobuildsoftware2026             ║
║    /plugin install neurawork-cc-harness@<marketplace>                 ║
║    /neurawork-cc-harness:knowledge-compiler   (and :claudemd-lerner)  ║
║                                                                        ║
║  [GATED on Phase 3] also self-host claudemd-lerner → repo-root         ║
║    CLAUDE.md + docs/ maintained automatically.                        ║
║  VALUE: legally usable, installable elsewhere, self-demonstrating.    ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| repo-root `LICENSE` | absent | MIT | Legally usable; matches plugin license |
| `README.md` License line | `TBD` | `MIT` + link to LICENSE + install pointer | Trust + discoverability |
| `.claude-plugin/marketplace.json` | absent | git-subdir entry → `plugins/neurawork-cc-harness` | A 2nd repo can `/plugin install` it |
| `docs/INSTALL.md` | absent | full install/upgrade guide | One-stop copyable steps |
| `docs/WHEN-TO-USE.md` | absent | harness vs coding-suite matrix | Disambiguates the name collision |
| `.claude/settings.json` | absent | 3 knowledge-compiler hooks | This repo captures its own sessions |
| `knowledge-base/` | absent | full payload + tracked `knowledge/` | This repo self-hosts the harness |

---

## Mandatory Reading

**This is a docs/distribution/self-host phase. Read the EXISTING artifacts to mirror their wording and not duplicate/contradict them. The install incantation and FQN note already exist — propagate, don't reinvent.**

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `plugins/neurawork-cc-harness/LICENSE` | all | The MIT text + exact copyright line (`(c) 2026 Felix Doobe / NeuraWork`) to COPY to repo root |
| P0 | `plugins/neurawork-cc-harness/skills/knowledge-compiler/SKILL.md` | 1-61 | The canonical recon→ask→install flow + the FQN/collision note (lines 22-25) to quote in the guide |
| P0 | `plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py` | 110-156 | Exact CLI surface (`--knowledge-dir`, `--seed`) and the "Next steps" print block the guide must match verbatim |
| P0 | `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` | all | Plugin `name` (`neurawork-cc-harness`) → marketplace `source` + FQN; confirm/extend optional fields (`version`, `license`, `author`) |
| P1 | `plugins/neurawork-cc-harness/README.md` | all (esp. 22-30) | Existing FQN/collision wording + Phase-1 status; the root guide should point here, not fork it |
| P1 | `README.md` (repo root) | 1-37 | Existing Overview / Status / **Sources** / License sections — extend in place, surgical |
| P1 | `CLAUDE.md` (repo root) | all | Will be modified by self-hosted lerner later; for now only note the harness in Repository status if asked. Do NOT pre-empt lerner's job |
| P1 | `.claude/PRPs/reports/neurawork-cc-harness-knowledge-compiler-report.md` | all | Phase-2 manual-smoke notes + auth posture to reuse in the guide's "requirements" |
| P1 | `engines/knowledge-compiler/recon.py` | 75-88 | What recon emits (`seed_recommended`, `existing_kdir`, `clean`) — the guide should describe what the user will be asked |
| P2 | `~/.claude/plugins/cache/homeserver-tools/coding-suite/*/skills/continuous-learner/SKILL.md` | all | For the "when-to-use vs coding-suite" matrix: coding-suite installs to `.claude/`, bash-based, no recon/seed/Python-SDK |

**External Documentation (current 2026, verified via claude-code-guide):**
| Source | Section | Why Needed |
|--------|---------|-----|
| [Plugin marketplaces — required fields](https://code.claude.com/docs/en/plugin-marketplaces.md#required-fields) | `name`, `owner`, `plugins[]` | marketplace.json schema |
| [Plugin marketplaces — git subdirectories](https://code.claude.com/docs/en/plugin-marketplaces.md#git-subdirectories) | `git-subdir` source | Plugin is nested at `plugins/...`, NOT repo root → must use `git-subdir` for external installs |
| [Discover & install plugins — add from GitHub](https://code.claude.com/docs/en/discover-plugins.md#add-from-github) | `/plugin marketplace add`, `/plugin install` | Exact second-repo install commands |
| [Plugins reference — plugin manifest schema](https://code.claude.com/docs/en/plugins-reference.md#plugin-manifest-schema) | required/optional fields | What `claude plugin validate` checks |
| [Plugins reference — skills-directory plugins](https://code.claude.com/docs/en/plugins-reference.md#skills-directory-plugins) | local loading, `/reload-plugins` | How to load the plugin locally during dev (symlink into `.claude/skills/`) |
| [Plugin marketplaces — version resolution](https://code.claude.com/docs/en/plugin-marketplaces.md#version-resolution-and-release-channels) | version vs commit SHA | GOTCHA: a stale `version` blocks updates; omit or bump |

---

## Key Decisions (Phase-4 specific)

```
APPROACH_CHOSEN: Root MIT LICENSE (mirror plugin) + repo-root .claude-plugin/marketplace.json
  using `git-subdir` source + canonical docs/INSTALL.md (root README points to it) +
  dogfood install of knowledge-compiler now, lerner gated on Phase 3.

RATIONALE:
  - License already decided MIT in Phase 1 (plugin LICENSE exists); Phase 4 only propagates it. No re-litigation.
  - `git-subdir` is REQUIRED, not optional: the plugin is nested at plugins/neurawork-cc-harness/, and
    relative `./path` sources fail for URL-based marketplace adds (verified gotcha). git-subdir works from GitHub.
  - Single canonical guide in docs/INSTALL.md (not duplicated across 3 READMEs): root README + plugin README
    both POINT to it. Avoids drift — and docs/ is exactly what the lerner skill will later maintain.
  - Dogfood knowledge-compiler now because it is shippable today; gate lerner to respect the real dependency.

ALTERNATIVES_REJECTED:
  - Relative `./plugins/...` marketplace source: rejected — breaks for URL-based adds; git-subdir is the documented fix.
  - Skills-dir/symlink-only loading as the distribution story: rejected as the PRIMARY path — it is dev-only and
    per-machine; the PRD promise is "a second repo can be upgraded", which needs a marketplace. (Documented as the
    dev workflow, not the install story.)
  - Re-choosing the license in Phase 4: rejected — Phase 1 already chose MIT; open-question #2 is thereby closed.
  - Putting the guide only in README.md: rejected — too long; docs/ is the right home and feeds lerner.

NOT_BUILDING:
  - No Phase-3 (claudemd-lerner) implementation — that is Phase 3; only its self-host step is referenced (gated).
  - No CI/release automation, no published GitHub release, no marketplace versioning scheme beyond "omit version → SHA".
  - No changes to plugin engine code or _shared/ — Phase 4 is docs/distribution/self-host only.
  - No Validators (Phases 5-6, Session 2).
```

---

## Files to Change

Repo-root paths unless noted. "Self-host" files (knowledge-base/, .claude/settings.json) are produced by running the existing installer, not hand-written.

| File | Action | Justification |
|------|--------|---------------|
| `LICENSE` | CREATE | Repo-root MIT — copy of `plugins/neurawork-cc-harness/LICENSE` |
| `README.md` | UPDATE | `License: TBD` → `MIT` + link; add a short "Install / Use" section pointing to `docs/INSTALL.md` |
| `.claude-plugin/marketplace.json` | CREATE | Makes the plugin installable from a second repo (git-subdir source) |
| `docs/INSTALL.md` | CREATE | Canonical install/upgrade guide (local dev, second-repo, per-skill flow, FQN, requirements) |
| `docs/WHEN-TO-USE.md` | CREATE | neurawork-cc-harness vs `coding-suite` matrix (collision disambiguation) |
| `plugins/neurawork-cc-harness/README.md` | UPDATE | Add a one-line pointer to `docs/INSTALL.md`; bump Phase status note to include Phase 4 |
| `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` | UPDATE (optional) | Add `description`/`license`/`author`/`version` if absent (verify first; `name` already present) |
| `.claude/settings.json` | CREATE (by installer) | 3 knowledge-compiler hooks — self-host artifact |
| `knowledge-base/**` | CREATE (by installer) | Self-host payload + tracked `knowledge/` — the dogfood proof |

---

## NOT Building (Scope Limits)

- **claudemd-lerner implementation** — Phase 3. Its self-host is Task 8, gated.
- **No marketplace versioning/release pipeline** — omit `version` in marketplace entry so installs track the commit SHA (documented gotcha); no GitHub Releases automation.
- **No engine/`_shared`/hook code changes** — Phase 4 touches docs, a manifest, and runs the existing installer.
- **No rewrite of the existing FQN/collision note** — reuse the wording already in SKILL.md / plugin README.
- **No pre-emptive hand-editing of root CLAUDE.md to describe architecture** — that is the lerner skill's job once self-hosted; only a minimal "this repo self-hosts the harness" note is allowed if the user asks.
- **Validators (Phases 5-6)** — Session 2.

---

## Step-by-Step Tasks

Execute in order. Tasks 1-7 + 9-10 are unblocked now. **Task 8 is gated on Phase 3.** Run validation from the repo root.

### Task 1: CREATE `LICENSE` (repo root)
- **ACTION**: Copy the MIT text from `plugins/neurawork-cc-harness/LICENSE` verbatim (same copyright holder/year: `Copyright (c) 2026 Felix Doobe / NeuraWork`).
- **MIRROR**: `plugins/neurawork-cc-harness/LICENSE`
- **GOTCHA**: Keep the copyright line identical to the plugin's so the two licenses don't appear to conflict.
- **VALIDATE**: `test -f LICENSE && grep -q "MIT" LICENSE && grep -q "NeuraWork" LICENSE`

### Task 2: UPDATE `README.md` — license + install pointer
- **ACTION**: Change the License section value `TBD` → `MIT — see [LICENSE](LICENSE).` Add a concise "## Install / Use" section that links to `docs/INSTALL.md` and names the two skills + their FQNs.
- **MIRROR**: existing README section style (`README.md:1-37`); keep the **Sources** section untouched (surgical).
- **GOTCHA**: Do not rewrite Overview/Status/Sources — only the License line and one new section.
- **VALIDATE**: `grep -q "MIT" README.md && grep -q "docs/INSTALL.md" README.md && ! grep -q "License: TBD" README.md`

### Task 3: CREATE `.claude-plugin/marketplace.json` (repo root)
- **ACTION**: Author a minimal valid marketplace manifest with one plugin entry using a **`git-subdir`** source pointing at `plugins/neurawork-cc-harness`.
- **IMPLEMENT** (fill the real GitHub `url` — confirm the remote with `git remote get-url origin`):
  ```json
  {
    "name": "neurawork-harness",
    "owner": { "name": "NeuraWork", "email": "felix.doobe@neurawork.ai" },
    "description": "Repo-local, self-maintaining CLAUDE.md + knowledge harness for Claude Code.",
    "plugins": [
      {
        "name": "neurawork-cc-harness",
        "source": {
          "source": "git-subdir",
          "url": "https://github.com/<owner>/howtobuildsoftware2026.git",
          "path": "plugins/neurawork-cc-harness"
        },
        "description": "Two independently installable skills: knowledge-compiler + claudemd-lerner.",
        "license": "MIT"
      }
    ]
  }
  ```
- **GOTCHA**: MUST be `git-subdir` (not relative `./plugins/...`) — relative paths fail for URL-based marketplace adds (verified). Omit `version` so installs track the commit SHA (a stale `version` blocks updates). Resolve `<owner>` from the actual git remote; if no remote exists, leave a clearly-marked `<owner>` placeholder and note it in the report.
- **VALIDATE**: `python3 -c "import json;d=json.load(open('.claude-plugin/marketplace.json'));assert d['name'] and d['owner']['name'] and d['plugins'][0]['source']['source']=='git-subdir'"`

### Task 4: CREATE `docs/INSTALL.md` — canonical install/upgrade guide
- **ACTION**: Write the one-stop guide. Sections:
  1. **Requirements**: `uv`, git, Python ≥3.12; `ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`) needed for compile/seed/flush SDK calls (capture-only hooks work without it). Subscription creds NOT sanctioned for third-party — state plainly.
  2. **Install in YOUR repo (the upgrade path)**: `/plugin marketplace add <owner>/howtobuildsoftware2026` → `/plugin install neurawork-cc-harness@neurawork-harness` → then per-skill: `/neurawork-cc-harness:knowledge-compiler` and (when shipped) `/neurawork-cc-harness:claudemd-lerner`. For each: recon → AskUserQuestion (dir name, timezone, seed?) → install → `uv sync --directory <dir>` → `git add <dir> .claude/settings.json && git commit`. Quote the installer's "Next steps" block verbatim from `install.py:143-145`.
  3. **FQN / collision**: always invoke `neurawork-cc-harness:knowledge-compiler` (collides with `coding-suite:knowledge-compiler` on bare name); `claudemd-lerner` is collision-free but use FQN anyway. Reuse the SKILL.md wording (`SKILL.md:22-25`).
  4. **Local development loading**: symlink the plugin into `.claude/skills/` to load as `@skills-dir` without a marketplace; `/reload-plugins` after non-SKILL changes; note marketplace-installed copies are cached (edits to the source repo won't be seen).
  5. **Upgrading**: `/plugin marketplace update` semantics; SHA-tracked installs pull latest on update.
  6. Pointer to `docs/WHEN-TO-USE.md`.
- **MIRROR**: the recon→ask→install narrative in `skills/knowledge-compiler/SKILL.md`; the exact CLI flags from `install.py:110-156`.
- **GOTCHA**: Do NOT invent commands — every command must match an existing script flag or a doc-cited `/plugin` command. Mark `claudemd-lerner` steps as "available once Phase 3 ships" if it is still absent at write time.
- **VALIDATE**: `test -f docs/INSTALL.md && grep -q "git-subdir\|/plugin marketplace add" docs/INSTALL.md && grep -q "neurawork-cc-harness:knowledge-compiler" docs/INSTALL.md && grep -q "ANTHROPIC_API_KEY" docs/INSTALL.md`

### Task 5: CREATE `docs/WHEN-TO-USE.md` — vs coding-suite
- **ACTION**: A short decision doc + matrix distinguishing this harness from the globally-installed `coding-suite` skills (`continuous-learner`, `knowledge-compiler`).
- **IMPLEMENT** the contrast (from PRD + codebase facts): neurawork-cc-harness = Python + `claude-agent-sdk`, interactive **recon**, brownfield **seed**, writes per-repo **in-repo** (knowledge-base/ + repo-root CLAUDE.md/docs), plugin-namespaced. `coding-suite:knowledge-compiler` = same `<repo>/<kdir>/` target but bash-based, no recon/seed. `coding-suite:continuous-learner` = installs under `.claude/` (often untracked), bash-based. Guidance: prefer neurawork-cc-harness for brownfield repos / when you want recon+seed + Python-SDK; either is fine greenfield; never run both knowledge-compilers in one repo without distinct dirs.
- **MIRROR**: the comparison framing in PRD `Research Summary` + `Technical Approach`.
- **GOTCHA**: Don't disparage coding-suite — it's the user's own tool; frame as "when to use which".
- **VALIDATE**: `test -f docs/WHEN-TO-USE.md && grep -qi "coding-suite" docs/WHEN-TO-USE.md && grep -qi "recon\|seed" docs/WHEN-TO-USE.md`

### Task 6: UPDATE `plugins/neurawork-cc-harness/README.md`
- **ACTION**: Add a one-line pointer near the top: "Install & upgrade guide: [`../../docs/INSTALL.md`](../../docs/INSTALL.md)". Update the Phase status note to mark Phase 4 in-progress/complete as appropriate. Keep the existing FQN note.
- **MIRROR**: existing plugin README structure.
- **GOTCHA**: Surgical — don't duplicate the full guide here; just point to it.
- **VALIDATE**: `grep -q "docs/INSTALL.md" plugins/neurawork-cc-harness/README.md`

### Task 7: UPDATE `plugins/neurawork-cc-harness/.claude-plugin/plugin.json` (verify-then-fill)
- **ACTION**: Read the manifest first. Confirm `name` exists. Add any MISSING common fields: `description`, `license: "MIT"`, `author` ({name, email}), and either omit `version` or set one you commit to bumping. Do not change `name`.
- **MIRROR**: schema from [plugins-reference#plugin-manifest-schema]; existing field style.
- **GOTCHA**: If fields already exist, leave them — surgical. Run `claude plugin validate` after.
- **VALIDATE**: `python3 -c "import json;d=json.load(open('plugins/neurawork-cc-harness/.claude-plugin/plugin.json'));assert d['name']=='neurawork-cc-harness'"` then `claude plugin validate ./plugins/neurawork-cc-harness` (if CLI available)

### Task 8: SELF-HOST — install the harness on THIS repo  ⛔ PARTIALLY GATED ON PHASE 3
- **ACTION**: Dogfood. This is the worked-example proof.
  - **8a (UNBLOCKED — knowledge-compiler)**: Run the recon→ask→install flow against this repo:
    - `python3 plugins/neurawork-cc-harness/engines/knowledge-compiler/recon.py` (expect `existing_kdir=None`, `seed_recommended=True`, `branch=main`).
    - `python3 plugins/neurawork-cc-harness/engines/knowledge-compiler/install.py --knowledge-dir knowledge-base` (add `--seed` only if `ANTHROPIC_API_KEY` is set and tree is clean).
    - `uv sync --directory knowledge-base`.
    - Commit: `git add knowledge-base .claude/settings.json && git commit` (on a branch, per repo convention — not directly to main unless the user authorizes).
  - **8b (GATED — claudemd-lerner)**: After Phase 3 ships, run `/neurawork-cc-harness:claudemd-lerner` recon→ask→install (`--lerner-dir claudemd-lerner [--seed]`), `uv sync --directory claudemd-lerner`, commit. Verify `.claude/settings.json` then holds **both** skills' hook sets (distinct `cl-` vs plain markers — the Phase-3 coexistence guarantee).
- **MIRROR**: the ordered self-host operations from the analyst trace; `SKILL.md` Phase A/B/C.
- **GOTCHA**: This MODIFIES this repo (adds `knowledge-base/`, creates `.claude/settings.json`). Do it on a feature branch and let the user review the diff before merge — outward-facing change. Confirm root `.gitignore` already covers `__pycache__`/`.venv`; the installer writes `knowledge-base/.gitignore` for runtime files. Do NOT seed without explicit auth + clean tree.
- **VALIDATE**: `test -d knowledge-base/hooks && test -f .claude/settings.json && python3 -c "import json;h=json.load(open('.claude/settings.json'))['hooks'];assert all(k in h for k in ('SessionStart','PreCompact','SessionEnd'))"`

### Task 9: VALIDATE marketplace + plugin loadability
- **ACTION**: Verify the distribution artifacts are well-formed and (if possible) test-add the marketplace locally.
  - `claude plugin validate ./plugins/neurawork-cc-harness` (manifest + frontmatter).
  - JSON-parse `marketplace.json` (Task 3 validate).
  - If feasible in a throwaway checkout: `/plugin marketplace add <local-or-git>` then `/plugin install neurawork-cc-harness@neurawork-harness` to confirm git-subdir resolves. Document the result (gated on network/remote).
- **VALIDATE**: validator clean; marketplace.json parses; install dry-run documented.

### Task 10: VERIFY the "second repo" upgrade path end-to-end (documented smoke)
- **ACTION**: In a throwaway repo (or document as a manual runbook if no remote yet): follow `docs/INSTALL.md` exactly — add marketplace, install plugin, run `knowledge-compiler` install, confirm hooks fire on next session, confirm `kc-compile` works. Capture any step where the guide diverges from reality and fix the guide.
- **GOTCHA**: This is the PRD success signal ("a second repo can be upgraded by following the guide"). If no GitHub remote exists yet, record this as a pending manual verification and note the `<owner>` placeholder in marketplace.json must be filled when the repo is pushed.
- **VALIDATE**: runbook executed or explicitly documented as pending-on-remote in the report.

---

## Testing Strategy

This phase has little executable code; validation is mostly artifact checks + manual runbook.

### Checks to Run
| Check | Command | Validates |
|-------|---------|-----------|
| LICENSE present | `grep -q MIT LICENSE` | Task 1 |
| README license fixed | `! grep -q "License: TBD" README.md` | Task 2 |
| marketplace.json valid + git-subdir | JSON assert in Task 3 | Task 3 |
| guide completeness | greps in Task 4/5 | Tasks 4-5 |
| plugin manifest valid | `claude plugin validate ./plugins/neurawork-cc-harness` | Task 7 |
| self-host hooks present | settings.json hook assert | Task 8a |
| no regression | `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s engines -v` | Phase 1/2 still green |

### Edge Cases Checklist
- [ ] No git remote yet → marketplace `url` has a clear `<owner>` placeholder; documented as pending
- [ ] `ANTHROPIC_API_KEY` absent → install works (capture-only); `--seed` skipped; documented
- [ ] Repo is both plugin SOURCE and CONSUMER → confirmed fine (plugin reads `plugins/`, writes config to `.claude/`); note cache-vs-symlink dev gotcha in guide
- [ ] Relative marketplace source → REJECTED in favor of git-subdir (URL-add gotcha)
- [ ] Phase 3 absent → Task 8b skipped, marked GATED; Phase 4 not marked fully complete until 8b runs (or partial completion explicitly accepted)
- [ ] Self-host commit → on a branch, user-reviewed (outward-facing change)
- [ ] Existing Phase-1/2 unit tests still pass after edits

---

## Validation Commands

### Level 1: ARTIFACT_INTEGRITY
```bash
# from repo root
test -f LICENSE && grep -q MIT LICENSE
grep -q MIT README.md && ! grep -q "License: TBD" README.md
python3 -c "import json;d=json.load(open('.claude-plugin/marketplace.json'));assert d['plugins'][0]['source']['source']=='git-subdir'"
test -f docs/INSTALL.md && test -f docs/WHEN-TO-USE.md
grep -q "neurawork-cc-harness:knowledge-compiler" docs/INSTALL.md
```
**EXPECT**: exit 0.

### Level 2: PLUGIN_VALIDATION
```bash
claude plugin validate ./plugins/neurawork-cc-harness   # if CLI present
python3 -c "import json;json.load(open('plugins/neurawork-cc-harness/.claude-plugin/plugin.json'))"
```
**EXPECT**: validator clean; manifest parses.

### Level 3: NO_REGRESSION
```bash
cd plugins/neurawork-cc-harness && python3 -m unittest discover -s engines -v
```
**EXPECT**: all Phase-1/2 tests pass (git tests SKIP if no git).

### Level 4: SELF-HOST (Task 8a)
```bash
test -d knowledge-base/hooks && test -f knowledge-base/config.json
python3 -c "import json;h=json.load(open('.claude/settings.json'))['hooks'];assert all(k in h for k in ('SessionStart','PreCompact','SessionEnd'))"
```
**EXPECT**: knowledge-base/ scaffolded; 3 hooks present.

### Level 5: SECOND-REPO SMOKE (Task 9/10, gated on remote)
- `/plugin marketplace add <url>` → `/plugin install neurawork-cc-harness@neurawork-harness` resolves via git-subdir; document outcome.

### Level 6: MANUAL
- Follow `docs/INSTALL.md` verbatim in a clean checkout; fix any divergence.

---

## Acceptance Criteria
- [ ] Repo-root `LICENSE` (MIT) present; `README.md` says MIT + links INSTALL guide; no `License: TBD`.
- [ ] `.claude-plugin/marketplace.json` valid, uses `git-subdir` source → `plugins/neurawork-cc-harness`, no stale `version`.
- [ ] `docs/INSTALL.md` covers: requirements/auth, second-repo `/plugin` commands, per-skill recon→ask→install, FQN/collision, local-dev loading, upgrading. Commands match real script flags / doc-cited `/plugin` syntax.
- [ ] `docs/WHEN-TO-USE.md` contrasts harness vs `coding-suite` (recon/seed/Python-SDK/in-repo vs bash/.claude/).
- [ ] `plugin.json` has `name` + (added if missing) `description`/`license`/`author`; `plugin validate` clean.
- [ ] Self-host (8a): this repo carries `knowledge-base/` + `.claude/settings.json` with 3 hooks, committed on a reviewed branch.
- [ ] Phase-1/2 unit tests still pass.
- [ ] Phase-3-gated self-host (8b) either done (both skills' hooks coexist) OR explicitly deferred with PRD noting partial completion.

## Completion Checklist
- [ ] Tasks 1-7, 9, 10 done + validated.
- [ ] Task 8a done (knowledge-compiler self-hosted); 8b done OR deferred-with-note.
- [ ] Levels 1-4 pass; Level 5/6 done or documented-as-pending-on-remote.
- [ ] PRD Phase 4 → `in-progress` (now) → `complete` only after 8b (or accepted partial). Phases 5-6 unblock when 4 completes.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Phase 3 not done** → can't fully self-host / guide references absent skill | HIGH | MED | Task 8 split; lerner steps marked "once Phase 3 ships"; Phase 4 completion gated on 8b |
| marketplace source wrong (relative path) → install fails for external users | MED | HIGH | Use `git-subdir` (verified fix); Task 9 test-adds the marketplace |
| No GitHub remote yet → `<owner>` unknown, second-repo path unverifiable | MED | MED | Placeholder + report note; Task 10 documented as pending-on-push |
| Self-host commit pollutes main / surprises user | MED | MED | Do on a feature branch; user reviews diff before merge |
| Stale `version` in manifest/marketplace blocks updates | LOW | MED | Omit version → SHA-tracked installs (documented gotcha) |
| Guide drifts from real script flags | LOW | MED | Quote `install.py` "Next steps" verbatim; Task 10 runbook reconciles |
| `--seed` run without auth/clean tree mangles CLAUDE.md | LOW | HIGH | Seed only with `ANTHROPIC_API_KEY` + clean tree + on a branch; default to no-seed |

---

## Notes
- **License question closed**: PRD open-question #2 ("which license for the harness") is answered — MIT, already in the plugin; Phase 4 only propagates it to the repo root. Record this in the PRD decisions/open-questions when marking the phase.
- **`git-subdir` is load-bearing**: the plugin's nested location (`plugins/neurawork-cc-harness/`) means relative marketplace paths fail for URL-based adds. This is the single most important distribution decision.
- **Repo = source AND consumer**: confirmed safe — the plugin reads from `plugins/`, writes hook config to `.claude/`. During development prefer the `.claude/skills/` symlink (live edits) over a cached marketplace install.
- **docs/ is intentional**: putting the guide in `docs/` (not just README) both keeps the README lean and seeds the very `docs/` tree the `claudemd-lerner` skill will later maintain — the repo demonstrates its own product.
- **Confidence**: 8/10 for one-pass — the artifacts (license, marketplace, guide) are low-risk and fully specified; −2 because (a) full self-host depends on Phase 3 landing first and (b) the true second-repo verification needs a pushed GitHub remote that may not exist yet.
