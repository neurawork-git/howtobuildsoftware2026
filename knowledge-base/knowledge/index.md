# Knowledge Base Index

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
| [[concepts/plugin-marketplace-install]] | Plugin installs via marketplace commands, no clone needed | daily/2026-06-25.md | 2026-07-02 |
| [[concepts/readme-getting-started-vs-contributing]] | README splits user install/use from contributor clone instructions | daily/2026-06-25.md | 2026-07-02 |
| [[concepts/plugin-manifest-name-verification]] | Marketplace/plugin names verified against manifest files | daily/2026-06-25.md | 2026-07-02 |
| [[concepts/sessionend-hook-triggers]] | SessionEnd hook fires with four reasons; not on compact or login | daily/2026-07-02.md | 2026-07-23 |
| [[concepts/session-end-reason-ignored]] | session-end.py ignores reason field; all reasons capture identically | daily/2026-07-02.md | 2026-07-23 |
| [[concepts/knowledge-compile-idempotency]] | Compiler skips already-indexed daily logs; no reprocessing | daily/2026-07-02.md | 2026-07-23 |
| [[connections/session-capture-to-compile-pipeline]] | Uniform capture + idempotent compile compose into a hands-off pipeline | daily/2026-07-02.md | 2026-07-23 |
| [[concepts/grillme-app]] | Local requirements-interview app distilling ideas into a Markdown spec + tickets | daily/2026-08-13.md | 2026-08-20 |
| [[concepts/claude-agent-sdk-subprocess-architecture]] | Python Agent SDK spawns the Claude Code CLI; backend image needs Node + Python | daily/2026-08-13.md | 2026-08-20 |
| [[concepts/postgres-source-of-truth-replayed-sessions]] | Postgres holds state; disposable SDK sessions replay tree+history each round | daily/2026-08-13.md | 2026-08-20 |
| [[concepts/api-key-vs-subscription-for-account-apps]] | Apps with accounts must use an API key, not subscription/OAuth login | daily/2026-08-13.md | 2026-08-20 |
| [[concepts/swappable-backend-interfaces]] | Transcriber and Storage interfaces keep STT and image storage vendor-neutral | daily/2026-08-13.md | 2026-08-20 |
| [[concepts/editable-transcript-before-send]] | STT shown editable before manual send to keep dictation errors out of the tree | daily/2026-08-13.md | 2026-08-20 |
| [[connections/sdk-subprocess-forces-api-key]] | Wrapped CLI's OAuth login is exactly the path an account app must not use | daily/2026-08-13.md | 2026-08-20 |
| [[concepts/plugin-version-bump-propagates-cache]] | Fixes reach installed caches only via a version bump; marketplace pulls on new version | daily/2026-08-27.md | 2026-08-27 |
| [[concepts/semver-patch-for-reporting-only-change]] | Reporting-only recon fix is patch-level; 0.3.0 → 0.3.1 | daily/2026-08-27.md | 2026-08-27 |
| [[concepts/verify-generated-artifacts-before-commit]] | LLM-generated docs verified against real files/config before commit | daily/2026-08-27.md | 2026-08-27 |
| [[concepts/connection-articles-enable-backward-retrieval]] | Connection articles surface non-obvious links a forward-only agent misses | daily/2026-08-27.md | 2026-08-27 |
| [[concepts/cold-start-measurement-needs-empty-uv-cache]] | Cold start is only real with an empty UV_CACHE_DIR: 6.95 s vs 11.28 s | daily/2026-09-02.md | 2026-09-02 |
| [[concepts/hook-timeout-sixty-second-budget]] | 60 s hook timeout replaces 10 s and is the sole cold-start mitigation | daily/2026-09-02.md | 2026-09-02 |
| [[concepts/installer-merge-repairs-existing-installs]] | Monotonic timeout floor + gitignore prune fix old installs, not just fresh ones | daily/2026-09-02.md | 2026-09-02 |
| [[concepts/install-run-clobbers-local-edits]] | Install runs overwrite hand-edited timeouts, user gitignore lines, and re-add forbidden env.PRP_HOME | daily/2026-09-02.md | 2026-09-02 |
| [[concepts/timing-evidence-vs-observed-behavior]] | Review with 0 findings still flagged a symptom argued from timing, never observed | daily/2026-09-02.md | 2026-09-02 |
| [[concepts/uncommitted-changes-to-deleted-files-block-ff-pull]] | Dirty file deleted upstream blocks pull --ff-only | daily/2026-09-02.md | 2026-09-02 |
| [[connections/installer-repair-and-clobber]] | An installer's repair power and its clobber power are the same write | daily/2026-09-02.md | 2026-09-02 |
