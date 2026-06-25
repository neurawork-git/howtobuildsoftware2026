"""Shared, stdlib-only helpers for neurawork-cc-harness skills.

Both skills (knowledge-compiler, claudemd-lerner) reuse these modules:

- hookio:     parse hook stdin (Windows-safe) + recursion guard
- transcript: read a JSONL session transcript into recent markdown turns
- gitctx:     worktree detection + state redirect to the main checkout
- settings:   idempotent .claude/settings.json hook merge
- repo_guard: enforce knowledge/docs are written in-repo, never under .claude/
- recon:      git-root resolution + RECON_JSON emit for install recon

No third-party dependencies — Python >= 3.12 standard library only.
"""
