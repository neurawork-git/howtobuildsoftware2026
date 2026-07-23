# howtobuildsoftware2026

> How to build software in 2026.

## Overview

This repository documents modern practices, tools, and workflows for building
software in 2026 — from project setup and architecture through delivery and
operations. It also **self-hosts** the plugin it ships: `knowledge-base/`,
`claudemd-lerner/`, and `compliance-base/` are live installs of the three skills
into this repo itself, so the repo is its own worked example.

## Status

🚧 Early stage. Structure and content are evolving.

## Install / Use

This repo ships a Claude Code plugin, **`neurawork-cc-harness`** (under
`plugins/`), bundling three independently installable skills:

- `neurawork-cc-harness:knowledge-compiler` — per-repo, self-building knowledge
  base. Captures each session into daily logs and compiles them into a queryable
  `knowledge/` wiki (concepts + connections + index), re-injected at session start.
- `neurawork-cc-harness:claudemd-lerner` — keeps your `CLAUDE.md` hierarchy +
  `docs/` tree current by editing them in place from session logs (no knowledge wiki).
- `neurawork-cc-harness:compliance-compiler` — ~30 parallel agents distil
  GDPR/SOC2/ISO27001 into a tracked constraint catalog (+ derived capabilities);
  a `PostToolUse` hook validates each PRP plan against it as it is written.

You do **not** clone this repo to use it. Install the plugin via its marketplace
from inside the repo you want to upgrade, in a Claude Code session:

```text
/plugin marketplace add neurawork-git/howtobuildsoftware2026
/plugin install neurawork-cc-harness@neurawork-harness
```

Then install any skill into your repo by invoking it (each runs its own recon +
seed and wires its own hooks — independent, install one or all three):

```text
/neurawork-cc-harness:knowledge-compiler
/neurawork-cc-harness:claudemd-lerner
/neurawork-cc-harness:compliance-compiler
```

### Slash commands

Once installed, each skill exposes on-demand commands (they otherwise run on their
own hooks — a 6-hour `SessionStart` gate for the first two, `PostToolUse` for compliance):

| Command | What it does |
|---------|--------------|
| `/neurawork-cc-harness:kc-compile` | Compile the knowledge base now — distil daily logs into `knowledge/` articles. |
| `/neurawork-cc-harness:cl-update` | Update `CLAUDE.md` + `docs/` now from captured session logs. |
| `/neurawork-cc-harness:co-extract` | (Re)build the compliance catalog now (~30 parallel agents). |
| `/neurawork-cc-harness:co-validate <plan>` | Validate a PRP plan against the catalog (deep gap report). |

The `co-extract` / `co-validate` (and the compile/update) LLM paths need
`ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`; install, scaffolding, and the
inline plan precheck run without it.

For the full install/upgrade flow (requirements, recon, seeding), see the
[install & upgrade guide](docs/INSTALL.md), and for how the harness is built,
[the architecture guide](docs/ARCHITECTURE.md).

## Sources

The principles and setup in this repo draw on:

- [How Claude Code works in large codebases: Best practices and where to start](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start) — Anthropic
- [multica-ai/andrej-karpathy-skills — CLAUDE.md](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md) — source of the working principles in `CLAUDE.md`, derived from Andrej Karpathy's observations on LLM coding pitfalls
- [coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler) — evolving memory for Claude Code via session capture + LLM compilation

## Contributing

Working **on** the harness (not just using it)? Clone the repo:

```bash
git clone git@github.com:neurawork-git/howtobuildsoftware2026.git
cd howtobuildsoftware2026
```

See the [install guide's local-development section](docs/INSTALL.md#local-development-working-on-the-plugin)
for loading the plugin from a checkout.

Issues and pull requests welcome. Keep changes focused and documented.

## License

MIT — see [LICENSE](LICENSE).
