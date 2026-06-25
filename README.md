# howtobuildsoftware2026

> How to build software in 2026.

## Overview

This repository documents modern practices, tools, and workflows for building
software in 2026 — from project setup and architecture through delivery and
operations.

## Status

🚧 Early stage. Structure and content are evolving.

## Getting Started

```bash
git clone git@github.com:neurawork-git/howtobuildsoftware2026.git
cd howtobuildsoftware2026
```

## Install / Use

This repo ships a Claude Code plugin, **`neurawork-cc-harness`** (under
`plugins/`), bundling two independently installable skills:

- `neurawork-cc-harness:knowledge-compiler` — per-repo, self-building knowledge base.
- `neurawork-cc-harness:claudemd-lerner` — keeps your `CLAUDE.md` hierarchy + `docs/` current.

To install the harness in your own repo, or to upgrade an existing one, follow the
[install & upgrade guide](docs/INSTALL.md). For how it differs from the `coding-suite`
skills of the same name, see [when to use which](docs/WHEN-TO-USE.md).

## Sources

The principles and setup in this repo draw on:

- [How Claude Code works in large codebases: Best practices and where to start](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start) — Anthropic
- [multica-ai/andrej-karpathy-skills — CLAUDE.md](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md) — source of the working principles in `CLAUDE.md`, derived from Andrej Karpathy's observations on LLM coding pitfalls
- [coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler) — evolving memory for Claude Code via session capture + LLM compilation

## Contributing

Issues and pull requests welcome. Keep changes focused and documented.

## License

MIT — see [LICENSE](LICENSE).
