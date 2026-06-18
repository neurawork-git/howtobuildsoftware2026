# Feature: neurawork-cc-harness — Plugin Scaffold & Shared Infra (Phase 1)

## Summary

Create the `neurawork-cc-harness` Claude Code plugin skeleton plus the shared Python infrastructure that both later skills (`knowledge-compiler`, Phase 2; `claudemd-lerner`, Phase 3) will depend on. This phase produces NO end-user skill behavior — it lays down the plugin manifest, directory layout, namespacing, and a small set of stdlib-only shared helper modules (transcript reader, hook-stdin parser + recursion guard, git/worktree context, idempotent `settings.json` hook merge, an in-repo write-guard, and a recon base) with unit tests. The patterns are mirrored directly from the already-installed `coding-suite` plugin (authored by the same user), which already contains working `continuous-learner` and `knowledge-compiler` engines.

## User Story

As a plugin author
I want a valid `neurawork-cc-harness` plugin shell with shared, tested capture/hook/git/settings/write-guard helpers and a clean namespace
So that both skills can be built in Phases 2 and 3 by mirroring proven patterns, without colliding with the installed `coding-suite:*` skills and without ever writing knowledge/docs into `.claude/`.

## Problem Statement

No plugin scaffold exists in this repo (root has only `README.md`, `.gitignore`, `CLAUDE.md`). Both planned skills need a shared, verifiable foundation: read a session transcript, parse hook stdin safely, detect worktrees and redirect state, merge hooks into `.claude/settings.json` idempotently, and guarantee knowledge/docs are written in-repo (never under `.claude/`). Without this foundation built and tested first, Phases 2/3 would each re-derive the same brittle plumbing.

## Solution Statement

Mirror the `coding-suite` plugin structure (`.claude-plugin/plugin.json`, `skills/<name>/SKILL.md`, `engines/<name>/`, `commands/`). Add a new `engines/_shared/` Python package (stdlib only) containing the cross-skill helpers, ported clean from `coding-suite`'s `git_context.py`, `learn_session_end.py` (transcript + stdin parse), and `install.py` (settings merge), plus ONE net-new module — `repo_guard.py` — that enforces the user's hard constraint (knowledge/docs never under `.claude/`). Ship unit tests mirroring `coding-suite`'s `test_git_context.py`. Namespace is the manifest `name` field: `neurawork-cc-harness`.

## Metadata

| Field            | Value                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| Type             | NEW_CAPABILITY                                                        |
| Complexity       | MEDIUM                                                                |
| Systems Affected | Claude Code plugin system; per-repo `.claude/settings.json`; git/worktree |
| Dependencies     | Python ≥3.12 (stdlib only — no third-party deps in this phase); git CLI |
| Estimated Tasks  | 11                                                                    |

---

## UX Design

### Before State
```
╔════════════════════════════════════════════════════════════════════╗
║                           BEFORE STATE                               ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║   repo: howtobuildsoftware2026/                                      ║
║   ├── README.md   ├── .gitignore   ├── CLAUDE.md                     ║
║   └── .claude/PRPs/{prds,plans}/                                     ║
║                                                                      ║
║   NO plugin. No skills. No shared infra.                             ║
║   Phases 2/3 would each re-invent: transcript read, stdin parse,     ║
║   worktree guard, settings.json merge, write-guard.                  ║
║                                                                      ║
║   PAIN: duplicated brittle plumbing; collision risk with            ║
║         coding-suite:knowledge-compiler / :continuous-learner.       ║
╚════════════════════════════════════════════════════════════════════╝
```

### After State
```
╔════════════════════════════════════════════════════════════════════╗
║                            AFTER STATE                               ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║   neurawork-cc-harness/                                              ║
║   ├── .claude-plugin/plugin.json      (name: neurawork-cc-harness)   ║
║   ├── README.md   ├── LICENSE                                        ║
║   ├── commands/        (empty; filled Phase 2/3)                     ║
║   ├── skills/          (empty; filled Phase 2/3)                     ║
║   └── engines/_shared/                                               ║
║        ├── __init__.py                                               ║
║        ├── hookio.py     parse stdin + recursion guard               ║
║        ├── transcript.py JSONL transcript → markdown turns           ║
║        ├── gitctx.py     in_worktree / main root / state_home        ║
║        ├── settings.py   idempotent .claude/settings.json hook merge ║
║        ├── repo_guard.py NET-NEW: refuse writes under .claude/       ║
║        ├── recon.py      git-root + RECON_JSON emit helper           ║
║        └── tests/test_*.py  (unittest, stdlib)                       ║
║                                                                      ║
║   plugin loads → skills resolve as neurawork-cc-harness:*            ║
║   VALUE: Phases 2/3 import tested helpers; no collision; guard       ║
║          guarantees in-repo knowledge/docs.                          ║
╚════════════════════════════════════════════════════════════════════╝
```

### Interaction Changes
| Location | Before | After | User Impact |
|----------|--------|-------|-------------|
| Plugin registry | no `neurawork-cc-harness` | plugin present, loadable | Author can install/iterate the plugin |
| `engines/_shared/` | n/a | tested stdlib helpers | Phases 2/3 reuse instead of re-derive |
| Skill namespace | only `coding-suite:*` | `neurawork-cc-harness:*` reserved | No bare-name collision confusion |

---

## Mandatory Reading

**CRITICAL: Implementation agent MUST read these files before starting any task.** All are absolute paths to the installed `coding-suite` plugin — the authoritative pattern source.

| Priority | File | Lines | Why Read This |
|----------|------|-------|---------------|
| P0 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/.claude-plugin/plugin.json` | all | plugin.json schema to MIRROR exactly (name/description/author) |
| P0 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/engines/continuous-learner/git_context.py` | all | `in_worktree`/`main_checkout_root`/`state_home` to PORT into `gitctx.py` |
| P0 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/engines/continuous-learner/learn_session_end.py` | 1-30, 150-289 | recursion guard (line 21), stdin parse (157-178), transcript JSONL extraction, bundle write |
| P0 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/engines/continuous-learner/install.py` | 153-211 | `merge_settings` idempotent hook-merge to PORT into `settings.py` |
| P1 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/engines/knowledge-compiler/install.py` | 28-39 | exact HOOKS tuple shape (event, command, timeout, marker) for `uv run` hooks |
| P1 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/engines/continuous-learner/recon.py` | 37-119 | recon pattern: git-root + RECON_JSON delimited blob to base `recon.py` on |
| P1 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/engines/continuous-learner/test_git_context.py` | all | test structure to MIRROR for `tests/test_gitctx.py` |
| P1 | `/home/felix/.claude/plugins/cache/homeserver-tools/coding-suite/c6386387d2f4/skills/worktree/SKILL.md` | 100-154 | `.gitignore` auto-append pattern; config-frontmatter read pattern (used Phase 2/3) |
| P2 | `/home/felix/.claude/plugins/cache/caveman/caveman/25d22f864ad6/.claude-plugin/plugin.json` | all | example of inline `hooks` block + `statusMessage` (reference only; not used this phase) |
| P2 | `/home/felix/.claude/plugins/cache/claude-plugins-official/plugin-dev/unknown/skills/command-development/references/frontmatter-reference.md` | all | authoritative frontmatter field catalog for commands/skills/agents |

**External Documentation:** None required for this phase — scaffold + shared helpers are Claude-Code-plugin mechanics + Python stdlib. `claude-agent-sdk` docs are deferred to the Phase 2 plan (the engines that actually call the SDK).

---

## Patterns to Mirror

**PLUGIN_MANIFEST:**
```json
// SOURCE: coding-suite/.claude-plugin/plugin.json (full file)
// COPY THIS SHAPE (no `version` field — version comes from dir/SHA):
{
  "name": "coding-suite",
  "description": "Felix' coding workflow as one package: ...",
  "author": { "name": "Felix Doobe" }
}
```

**RECURSION_GUARD:** (top of every hook script, before heavy imports)
```python
# SOURCE: continuous-learner/learn_session_end.py:21
import os, sys
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)
```

**STDIN_PARSE (with Windows backslash fix):**
```python
# SOURCE: continuous-learner/learn_session_end.py:157-178
try:
    raw = sys.stdin.read()
    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        fixed = re.sub(r'(?<!\\)\\(?!["\\])', r'\\\\', raw)
        hook_input = json.loads(fixed)
except (json.JSONDecodeError, ValueError, EOFError) as e:
    logging.error("Failed to parse stdin: %s", e)
    return
session_id = hook_input.get("session_id") or "unknown"
transcript_path_str = hook_input.get("transcript_path", "")
cwd = hook_input.get("cwd", "")
```

**WORKTREE_GUARD + STATE REDIRECT:**
```python
# SOURCE: continuous-learner/git_context.py:52-96
def in_worktree(start=None) -> bool:
    git_dir = _resolved(["rev-parse", "--git-dir"], start)
    common = _resolved(["rev-parse", "--git-common-dir"], start)
    if git_dir is None or common is None:
        return False
    return git_dir != common   # worktree: differ; main: equal

def state_home(local_dir, start=None):
    try:
        if not in_worktree(start):
            return local_dir
        main_root = main_checkout_root(start)
        wt_root = _resolved(["rev-parse", "--show-toplevel"], start)
        if main_root is None or wt_root is None:
            return local_dir
        rel = Path(local_dir).resolve().relative_to(wt_root)
        return main_root / rel
    except (OSError, ValueError):
        return local_dir
```

**TRANSCRIPT_EXTRACTION:** (JSONL → recent markdown turns)
```python
# SOURCE: continuous-learner/learn_session_end.py (transcript loop, ~lines 200-240)
# Iterate JSONL lines; per line json.loads; pull message.role + message.content
# for role in {"user","assistant"}; assemble last `max_turns` (30) as
# "**User:**\n...\n\n**Assistant:**\n..."; truncate to `max_context_chars` (15000).
```

**IDEMPOTENT_SETTINGS_MERGE:**
```python
# SOURCE: continuous-learner/install.py:153-190 (merge_settings)
# Open <repo>/.claude/settings.json (create if absent).
# For each (event, command, timeout, marker):
#   under hooks[event], search existing groups for a hook whose `command`
#   contains `marker`. If found → skip (idempotent). Else reuse a group with
#   matcher=="" or create {"matcher":"", "hooks":[{type:"command",command,timeout}]}.
# Write back atomically (tmp + os.replace).
```

**HOOK_JSON_SHAPE:**
```json
// SOURCE: continuous-learner/install.py:28-31 (written into repo .claude/settings.json)
{ "hooks": { "SessionEnd": [ { "matcher": "",
  "hooks": [ { "type": "command",
    "command": "python3 .claude/continuous-learner/learn_session_end.py",
    "timeout": 10 } ] } ] } }
```

**GITIGNORE_AUTO_APPEND:**
```bash
# SOURCE: worktree/SKILL.md:148-154
GI="$ROOT/.gitignore"
grep -qxF '.claude/*.local.md' "$GI" 2>/dev/null \
  || printf '\n# neurawork-cc-harness local config\n.claude/*.local.md\n' >> "$GI"
```

**TEST_STRUCTURE:** (stdlib unittest, real temp git repos)
```python
# SOURCE: continuous-learner/test_git_context.py
# unittest.TestCase; tempfile.TemporaryDirectory; subprocess `git init` real repos;
# assert in_worktree()/state_home() behavior for main vs linked worktree.
```

---

## Files to Change

| File | Action | Justification |
|------|--------|---------------|
| `neurawork-cc-harness/.claude-plugin/plugin.json` | CREATE | Plugin manifest; sets `name` namespace |
| `neurawork-cc-harness/README.md` | CREATE | What the plugin is + install pointer (filled per phase) |
| `neurawork-cc-harness/LICENSE` | CREATE | Public repo needs a license (resolve open question first) |
| `neurawork-cc-harness/.gitignore` | CREATE | Ignore `__pycache__/`, runtime state |
| `neurawork-cc-harness/commands/.gitkeep` | CREATE | Reserve dir for Phase 2/3 install commands |
| `neurawork-cc-harness/skills/.gitkeep` | CREATE | Reserve dir for Phase 2/3 SKILL.md |
| `neurawork-cc-harness/engines/_shared/__init__.py` | CREATE | Make `_shared` an importable package |
| `neurawork-cc-harness/engines/_shared/hookio.py` | CREATE | stdin parse + Windows fix + recursion guard helper |
| `neurawork-cc-harness/engines/_shared/transcript.py` | CREATE | JSONL transcript → markdown turns |
| `neurawork-cc-harness/engines/_shared/gitctx.py` | CREATE | in_worktree / main_checkout_root / state_home |
| `neurawork-cc-harness/engines/_shared/settings.py` | CREATE | idempotent `.claude/settings.json` hook merge |
| `neurawork-cc-harness/engines/_shared/repo_guard.py` | CREATE | NET-NEW: refuse knowledge/docs writes under `.claude/` |
| `neurawork-cc-harness/engines/_shared/recon.py` | CREATE | git-root resolve + RECON_JSON emit base |
| `neurawork-cc-harness/engines/_shared/tests/test_gitctx.py` | CREATE | mirror test_git_context.py |
| `neurawork-cc-harness/engines/_shared/tests/test_settings.py` | CREATE | merge idempotency + create-if-absent |
| `neurawork-cc-harness/engines/_shared/tests/test_repo_guard.py` | CREATE | guard rejects `.claude/` targets |
| `neurawork-cc-harness/engines/_shared/tests/test_transcript.py` | CREATE | JSONL parse + truncation |

**Decision needed before Task 1:** where does the plugin source live? Recommended: a sibling dir `/home/felix/projects/neurawork-cc-harness/` (its own public git repo), since the PRD says public repo and the plugin should not be nested inside `howtobuildsoftware2026`. The plan paths above are relative to that plugin root. Confirm with user (see Open Questions).

---

## NOT Building (Scope Limits)

- **No skill behavior** — `knowledge-compiler` and `claudemd-lerner` SKILL.md, install.py, hooks, recon questions, seed/bootstrap → Phases 2 & 3.
- **No `claude-agent-sdk` usage** — the scaffold helpers are stdlib only; SDK wiring is Phase 2/3.
- **No install commands** — `commands/*.md` deferred to Phase 2/3.
- **No actual hook scripts** — only the shared `settings.py` merge helper + hook JSON shape; the per-skill hook entrypoints belong to Phases 2/3.
- **No copying of coleam00 code** — knowledge-compiler engine (Phase 2) must reimplement clean; this phase touches none of it.
- **No validators** — TechStack/Compliance are Session 2.

---

## Step-by-Step Tasks

Execute in order. Each task is atomic and independently verifiable. Paths are relative to the plugin root (see "Decision needed" above).

### Task 1: CREATE `.claude-plugin/plugin.json`
- **ACTION**: CREATE the plugin manifest
- **IMPLEMENT**: `{ "name": "neurawork-cc-harness", "description": "<one-line: repo-local knowledge + CLAUDE.md/docs harness>", "author": { "name": "Felix Doobe", "email": "felix.doobe@neurawork.ai" } }`
- **MIRROR**: `coding-suite/.claude-plugin/plugin.json` (no `version` field)
- **GOTCHA**: `description` is the only place to advertise; keep it trigger-rich but truthful. No `version` key.
- **VALIDATE**: `python3 -c "import json;json.load(open('.claude-plugin/plugin.json'))"` exits 0

### Task 2: CREATE repo housekeeping files
- **ACTION**: CREATE `README.md`, `LICENSE`, `.gitignore`, `commands/.gitkeep`, `skills/.gitkeep`
- **IMPLEMENT**: README = name + one-paragraph purpose + "skills installed per Phase 2/3"; `.gitignore` ignores `__pycache__/`, `*.pyc`; LICENSE = chosen license text (BLOCKED on Open Question — if unresolved, create `LICENSE` as a TODO placeholder and flag it, do not invent terms)
- **MIRROR**: `coding-suite/README.md` tone (concise)
- **GOTCHA**: Do not finalize LICENSE until the coleam00-derivation question is resolved (knowledge-compiler is Phase 2, but the repo license is set now).
- **VALIDATE**: files exist; `git status` shows them

### Task 3: CREATE `engines/_shared/__init__.py`
- **ACTION**: CREATE empty package marker (may contain `__all__`)
- **IMPLEMENT**: empty file (or module docstring)
- **VALIDATE**: `python3 -c "import sys;sys.path.insert(0,'engines');import _shared"` exits 0

### Task 4: CREATE `engines/_shared/gitctx.py`
- **ACTION**: PORT git/worktree helpers
- **IMPLEMENT**: `_resolved(args, start)`, `in_worktree(start=None)`, `main_checkout_root(start=None)`, `state_home(local_dir, start=None)`, `repo_root(start=None)`
- **MIRROR**: `continuous-learner/git_context.py:52-96` exactly (clean port — same logic, your own code)
- **IMPORTS**: `subprocess`, `from pathlib import Path`
- **GOTCHA**: main checkout → `--git-dir` == `--git-common-dir`; worktree → differ. Catch `(OSError, ValueError)` and fall back to `local_dir`.
- **VALIDATE**: `python3 -m py_compile engines/_shared/gitctx.py`

### Task 5: CREATE `engines/_shared/hookio.py`
- **ACTION**: CREATE hook stdin/recursion helpers
- **IMPLEMENT**: `recursion_guard()` (exit 0 if `CLAUDE_INVOKED_BY` set), `read_hook_input()` (read stdin, json.loads with Windows backslash `re.sub` fallback, return dict), `child_env()` (returns `{**os.environ, "CLAUDE_INVOKED_BY": "neurawork_cc_harness"}`)
- **MIRROR**: `learn_session_end.py:21` (guard) and `:157-178` (parse)
- **IMPORTS**: `os, sys, json, re`
- **GOTCHA**: Never raise on bad stdin — return `{}` and log; SessionStart sends fields the parser may not need.
- **VALIDATE**: `python3 -m py_compile engines/_shared/hookio.py`

### Task 6: CREATE `engines/_shared/transcript.py`
- **ACTION**: CREATE transcript reader
- **IMPLEMENT**: `extract_turns(transcript_path, max_turns=30, max_chars=15000) -> str` — read JSONL, per line `json.loads`, pull `message.role`/`message.content` for user+assistant, format `**User:**` / `**Assistant:**`, keep last `max_turns`, truncate to `max_chars`. Handle string OR list-of-blocks content.
- **MIRROR**: `learn_session_end.py` transcript loop (~200-240)
- **IMPORTS**: `json`, `from pathlib import Path`
- **GOTCHA**: content can be a string or a list of `{type,text}` blocks — join text blocks; skip non-text. Missing file → return `""`.
- **VALIDATE**: `python3 -m py_compile engines/_shared/transcript.py`

### Task 7: CREATE `engines/_shared/settings.py`
- **ACTION**: PORT idempotent settings-merge
- **IMPLEMENT**: `merge_hooks(repo_root, hooks: list[tuple[event,command,timeout,marker]]) -> bool` — load/create `<repo_root>/.claude/settings.json`; for each entry, search `hooks[event]` groups for a hook whose `command` contains `marker`; if absent, reuse a `matcher==""` group or create one; atomic write (tmp + `os.replace`). Return True if changed.
- **MIRROR**: `continuous-learner/install.py:153-190`
- **IMPORTS**: `json, os`, `from pathlib import Path`
- **GOTCHA**: Idempotent — never duplicate a hook; never clobber unrelated hooks/keys. Create `.claude/` dir if missing.
- **VALIDATE**: `python3 -m py_compile engines/_shared/settings.py`

### Task 8: CREATE `engines/_shared/repo_guard.py`  (NET-NEW)
- **ACTION**: CREATE the in-repo write-guard enforcing the user's hard constraint
- **IMPLEMENT**: `assert_in_repo_not_dotclaude(target_path, repo_root)` — resolve `target_path`; raise `WriteGuardError` if it is outside `repo_root` OR under `<repo_root>/.claude/`. `safe_join(repo_root, *parts)` convenience that validates then returns the path. Define `class WriteGuardError(Exception)`.
- **MIRROR**: no direct source — design follows the PRD constraint "knowledge/docs always in-repo, never `.claude/`". Use `Path.resolve()` + `.relative_to()` / `is_relative_to()` checks.
- **IMPORTS**: `from pathlib import Path`
- **GOTCHA**: Use `Path.resolve()` on both sides before comparing to defeat `..` traversal. `.claude/continuous-learner/state.json`-style RUNTIME state is allowed (that is config/state, not knowledge) — guard only knowledge/docs targets, so make the rule explicit: reject paths under `.claude/` only when called for knowledge/doc writes.
- **VALIDATE**: `python3 -m py_compile engines/_shared/repo_guard.py`

### Task 9: CREATE `engines/_shared/recon.py`
- **ACTION**: CREATE recon base helper
- **IMPLEMENT**: `git_root_or_fail() -> str | None` (None ⇒ caller prints `NOT_A_GIT_REPO`), `emit_recon_json(data: dict)` — print human summary then a `RECON_JSON … RECON_JSON` delimited JSON blob, matching the parse contract used by install skills.
- **MIRROR**: `continuous-learner/recon.py:37-119` (esp. the `RECON_JSON` delimiters at line 115)
- **IMPORTS**: `json, subprocess`
- **GOTCHA**: The delimiter string must be exactly what Phase 2/3 install skills will grep for. Keep it `RECON_JSON` on its own lines.
- **VALIDATE**: `python3 -m py_compile engines/_shared/recon.py`

### Task 10: CREATE shared unit tests
- **ACTION**: CREATE `engines/_shared/tests/test_gitctx.py`, `test_settings.py`, `test_repo_guard.py`, `test_transcript.py` (+ `tests/__init__.py`)
- **IMPLEMENT**:
  - `test_gitctx`: real `git init` in a `tempfile.TemporaryDirectory`; assert `in_worktree()` False in main; create a linked worktree, assert True + `state_home` redirects to main.
  - `test_settings`: merge into absent settings → file created with hook; merge again → no duplicate (idempotent); unrelated existing hook preserved.
  - `test_repo_guard`: target under `<repo>/.claude/foo` → raises; target `<repo>/docs/x.md` → ok; `..` escape → raises.
  - `test_transcript`: write a tiny JSONL; assert turns formatted + truncation at `max_chars`; missing file → `""`.
- **MIRROR**: `continuous-learner/test_git_context.py` (unittest + tempdir + real git)
- **IMPORTS**: `unittest, tempfile, subprocess, json, os`
- **GOTCHA**: Tests that shell out to `git` need `git` on PATH; guard with `shutil.which("git")` skip if absent.
- **VALIDATE**: `python3 -m unittest discover -s engines/_shared/tests -v`

### Task 11: VALIDATE plugin loads + namespacing
- **ACTION**: Verify the plugin is structurally valid and namespaced
- **IMPLEMENT**: Run the `plugin-dev:plugin-validator` agent against the plugin root; confirm `.claude-plugin/plugin.json` parses, dirs are recognized, and skills (none yet) would resolve as `neurawork-cc-harness:*`. Confirm no bare-name clash strategy is documented in README (knowledge-compiler via FQN).
- **MIRROR**: n/a (validation step)
- **GOTCHA**: With no skills/commands yet, the validator should still pass on manifest + structure. Empty `skills/` with only `.gitkeep` is acceptable for this phase.
- **VALIDATE**: validator reports no errors; `python3 -c "import json;json.load(open('.claude-plugin/plugin.json'))"`

---

## Testing Strategy

### Unit Tests to Write
| Test File | Test Cases | Validates |
|-----------|------------|-----------|
| `tests/test_gitctx.py` | main repo, linked worktree, non-git dir | `in_worktree`, `state_home`, `repo_root` |
| `tests/test_settings.py` | absent file, idempotent re-merge, preserve unrelated | `merge_hooks` |
| `tests/test_repo_guard.py` | `.claude/` reject, docs/ allow, `..` escape reject | `assert_in_repo_not_dotclaude` |
| `tests/test_transcript.py` | string content, block content, truncation, missing file | `extract_turns` |

### Edge Cases Checklist
- [ ] Not a git repo → `gitctx` returns sane fallback; `recon.git_root_or_fail()` returns None
- [ ] Malformed hook stdin → `read_hook_input` returns `{}`, no crash
- [ ] `.claude/settings.json` absent → `merge_hooks` creates it
- [ ] Duplicate merge → no second hook entry
- [ ] Write target escaping repo via `..` → `WriteGuardError`
- [ ] Transcript content as list-of-blocks vs string
- [ ] `git` not on PATH → git-dependent tests skip, not fail

---

## Validation Commands

### Level 1: STATIC_ANALYSIS
```bash
python3 -m py_compile engines/_shared/*.py engines/_shared/tests/*.py
# if available: ruff check engines/  (optional — not a hard dep this phase)
python3 -c "import json;json.load(open('.claude-plugin/plugin.json'))"
```
**EXPECT**: Exit 0, no syntax errors, manifest parses.

### Level 2: UNIT_TESTS
```bash
python3 -m unittest discover -s engines/_shared/tests -v
```
**EXPECT**: All tests pass (git-dependent tests may SKIP if `git` absent — not fail).

### Level 3: FULL_SUITE
```bash
python3 -m unittest discover -s engines/_shared/tests && \
  python3 -c "import json;json.load(open('.claude-plugin/plugin.json'))"
```
**EXPECT**: All pass; manifest valid.

### Level 4: DATABASE_VALIDATION
N/A — no database in this plugin.

### Level 5: BROWSER_VALIDATION
N/A — no UI.

### Level 6: MANUAL_VALIDATION
1. Run `plugin-dev:plugin-validator` agent against the plugin root → no errors.
2. (Optional) Add the plugin's parent dir as a local marketplace and confirm it loads and skills would namespace as `neurawork-cc-harness:*` without colliding with `coding-suite:*`.

---

## Acceptance Criteria
- [ ] `.claude-plugin/plugin.json` exists, parses, `name == "neurawork-cc-harness"`.
- [ ] `engines/_shared/` has all 6 modules + `__init__.py`, all compile.
- [ ] `repo_guard.py` rejects `.claude/` and out-of-repo knowledge/doc targets.
- [ ] All unit tests pass (Levels 1–3 exit 0).
- [ ] No skill/command behavior added (scope held to scaffold).
- [ ] README documents FQN invocation note for `knowledge-compiler` (collision with `coding-suite`).
- [ ] `plugin-dev:plugin-validator` reports no errors.

## Completion Checklist
- [ ] Tasks 1–11 done in order, each validated.
- [ ] Level 1 static analysis passes.
- [ ] Level 2 unit tests pass.
- [ ] Level 3 full suite + manifest valid.
- [ ] Manual: plugin-validator clean.
- [ ] PRD Phase 1 marked complete; Phases 2 & 3 unblocked (can run parallel in worktrees).

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LICENSE undecided blocks Task 2 | MED | MED | Create placeholder LICENSE flagged TODO; resolve coleam00-derivation + repo-license open questions before Phase 2 ships knowledge-compiler |
| Bare `knowledge-compiler` name collides with `coding-suite:knowledge-compiler` | MED | LOW | Namespace via manifest; document FQN-only invocation in README; `claudemd-lerner` is collision-free |
| Plugin source location ambiguous (sibling repo vs nested) | MED | MED | Confirm sibling `/home/felix/projects/neurawork-cc-harness/` with user before Task 1 |
| `git` absent in CI → worktree tests fail | LOW | LOW | `shutil.which("git")` skip-guard in tests |
| repo_guard over-blocks legitimate `.claude/` state writes | LOW | MED | Guard only knowledge/doc writes; allow runtime state/config under `.claude/<engine>/` explicitly |
| Drift from coding-suite patterns over time | LOW | LOW | Clean port now; document SOURCE file:line in each module header |

---

## Notes

- **Key context**: `coding-suite` (authored by the same user) already implements both target engines. `neurawork-cc-harness` is effectively a clean, public, renamed re-packaging. This makes Phase 1 low-risk: every pattern has a working reference at a known absolute path.
- **Renaming map**: `coding-suite:continuous-learner` → `neurawork-cc-harness:claudemd-lerner`; `coding-suite:knowledge-compiler` → `neurawork-cc-harness:knowledge-compiler`.
- **Shared-vs-vendored**: PRD makes shared infra "Should" / opt-in and skills "independently installable." This phase builds `_shared` as the canonical source; Phase 2/3 install.py decides whether to vendor a copy per-skill (default, for independence) or symlink a single shared copy (opt-in). Not decided here.
- **Why no web research this phase**: scaffold uses only CC-plugin mechanics + Python stdlib; the installed `coding-suite` is a more authoritative reference than external docs. `claude-agent-sdk` (>=0.1.29 per coding-suite's payload `pyproject.toml`) research belongs in the Phase 2 plan.
- **Confidence**: high — patterns are concrete, local, and tested in production by `coding-suite`.
