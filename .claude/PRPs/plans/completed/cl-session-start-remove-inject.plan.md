# Feature: Propagate cl-session-start inject removal through the plugin

## Summary

The `claudemd-lerner` SessionStart hook (`cl-session-start.py`) previously did two jobs:
(1) inject the repo's `CLAUDE.md` + `docs/` listing + recent daily log as
`additionalContext`, and (2) spawn a detached `update.py` behind a 6-hour gate. The
injection is removed so the SessionStart context is left free for the
`knowledge-compiler`'s concepts inject (CLAUDE.md is already read at session start, so
re-injecting it only crowds context). This plan removes the injection from both hook
copies and propagates the change: docs/skill text updated, engine version bumped, tests green.

## Metadata

| Field            | Value |
| ---------------- | ----- |
| Type             | REFACTOR (behaviour + propagation) |
| Complexity       | LOW |
| Systems Affected | claudemd-lerner engine (payload + self-host), plugin docs, SKILL.md |
| Dependencies     | none (stdlib Python) |
| Estimated Tasks  | 6 |

## Files to Change

| File | Action | Why |
| ---- | ------ | --- |
| `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/hooks/cl-session-start.py` | UPDATE | Remove injection; keep only the update-spawn gate |
| `claudemd-lerner/hooks/cl-session-start.py` | UPDATE | Self-host copy — keep byte-identical to payload |
| `plugins/neurawork-cc-harness/skills/claudemd-lerner/SKILL.md` | UPDATE | Line ~11 falsely claims SessionStart injects CLAUDE.md + docs/ |
| `docs/ARCHITECTURE.md` | UPDATE | SessionStart bullet (~86) conflates both engines; scope inject to knowledge-compiler |
| `plugins/neurawork-cc-harness/engines/claudemd-lerner/payload/pyproject.toml` | UPDATE | Bump version 0.1.0 → 0.1.1 |
| `claudemd-lerner/pyproject.toml` | UPDATE | Keep self-host version identical |

## NOT Building

- No `version` field added to `plugin.json` (never had one; separate convention).
- knowledge-compiler / compliance-compiler SessionStart hooks unchanged (still inject by design).
- `docs/INSTALL.md:9` "re-injected" is the knowledge-compiler bullet → correct, untouched.
- No new test (no test covered inject output; hook contract = registered + spawns update, unchanged).

## Tasks

1. Rewrite `payload/hooks/cl-session-start.py`: drop `build_context`/`_recent_daily`/inject
   constants/orphan imports; `main()` runs the update gate only, no `additionalContext` print.
2. Copy payload hook → self-host; `diff` must be empty.
3. Fix `SKILL.md` injection claim.
4. Scope `docs/ARCHITECTURE.md` SessionStart inject to knowledge-compiler.
5. Bump payload `pyproject.toml` version → 0.1.1.
6. Bump self-host `pyproject.toml` version → 0.1.1; run ruff + all four unittest suites.

## Validation

- `diff` payload↔self-host hook → identical.
- `python3 -c "import ast; ast.parse(open(...))"` → parse OK.
- No grep hit for `injects the current CLAUDE.md` under docs/ + skills/claudemd-lerner.
- `uvx ruff check` clean in the engine dir.
- All four `python3 -m unittest discover` suites OK.
- Both `pyproject.toml` read `version = "0.1.1"`.

## Notes

`plugin.json` has no `version` field; the only engine semver is `pyproject.toml`. This plan
bumps that (patch). Plugin-wide semver would first require a `version` field in `plugin.json`
— out of scope. Compliance PostToolUse precheck is N/A here (internal docs/version only, no
data-processing/auth/security surface).
