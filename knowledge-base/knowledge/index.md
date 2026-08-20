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
