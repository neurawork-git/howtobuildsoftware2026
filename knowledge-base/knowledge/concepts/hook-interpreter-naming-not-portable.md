---
title: "Naming a Python Interpreter in a Hook Command Is Not Portable"
aliases: [python3-store-alias, no-unsuffixed-python-macos, drop-the-interpreter]
tags: [hooks, portability, claude-code, windows, macos, gotcha]
sources:
  - "daily/2026-09-02.md"
created: 2026-09-03
updated: 2026-09-03
---

# Naming a Python Interpreter in a Hook Command Is Not Portable

There is no spelling of a Python interpreter that works across platforms in a
hook command. `python3` on Windows resolves to the Store alias, which writes to
**stdout** — and SessionStart stdout is injected as `additionalContext`, so the
failure contaminates the session rather than merely failing. Plain `python`
breaks macOS, which has shipped no unsuffixed `python` since 12.3. The resolution
for Issue #19 was to name no interpreter at all: node plus the hook exec form.

## Key Points

- `python3` on Windows is the Store alias; its output goes to stdout, and
  SessionStart stdout becomes `additionalContext` — the wrong binary silently
  injects text into the session.
- `python` is unavailable on macOS 12.3 and later, so it is not a fallback.
- `uv run` is not the escape hatch either: a cold checkout with no `.venv` takes
  roughly 11.6 s against 10–15 s hook timeouts, and Claude Code misreports the
  overrun as `Hook cancelled` (Issue #5).
- The fix was to drop the interpreter from the command entirely and use node with
  the hook exec form (#19).
- #19 was prioritised ahead of cost and design work because a plugin-load-path
  defect has the largest blast radius.

## Details

The Windows case is worse than a missing binary. A hook that fails loudly is a
nuisance; a hook whose stand-in binary prints to stdout on a `SessionStart` hook
feeds that output into the model's context as `additionalContext`, so a
platform-specific packaging accident becomes a content-injection bug. That
asymmetry is why the eventual answer was to remove the choice rather than pick
better among the options.

The three candidate spellings fail for three unrelated reasons — a Windows shim,
a macOS removal, and a cold-start budget — which is a good sign that the
requirement itself was wrong. This also bears on a decision recorded elsewhere:
Issue #5's point 4 proposed falling back to plain `python3` when `uv` is absent,
and that item was dropped as redundant given the 60 s timeout (see
[[concepts/hook-timeout-sixty-second-budget]]). The portability finding is an
independent reason the same fallback would not have held up.

## Related Concepts

- [[concepts/hook-timeout-sixty-second-budget]] — the timeout that made the `python3` fallback redundant
- [[concepts/cold-start-measurement-needs-empty-uv-cache]] — the cold-start cost that rules out `uv run` as the answer
- [[concepts/sessionend-hook-triggers]] — the hook lifecycle whose stdout contract matters here

## Sources

- [[daily/2026-09-02.md]] — `python3` is the Windows Store alias writing to stdout; no unsuffixed `python` on macOS since 12.3; resolved by dropping the interpreter (#19)
