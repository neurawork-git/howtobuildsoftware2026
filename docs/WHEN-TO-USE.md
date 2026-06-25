# When to use which — neurawork-cc-harness vs coding-suite

Two skill names overlap between this plugin and the `coding-suite` plugin:
`knowledge-compiler` and (conceptually) the doc-maintaining learner. This page
explains the differences so you can pick — and so the name collision never bites.

## At a glance

| | `neurawork-cc-harness` | `coding-suite` |
|---|---|---|
| **Stack** | Python + `claude-agent-sdk` | bash |
| **Install recon** | interactive (dir, timezone, depth, docs, language, excluded dirs) | none |
| **Brownfield seed** | yes — analyses an existing repo on first install | no |
| **knowledge-compiler output** | `<repo>/<dir>/knowledge/` (in-repo, tracked) | `<repo>/<dir>/` (in-repo) |
| **doc learner output** | `claudemd-lerner` → repo-root `CLAUDE.md` + `docs/` | `continuous-learner` → under `.claude/` (often untracked) |
| **Namespacing** | `neurawork-cc-harness:*` | `coding-suite:*` |
| **Compile trigger** | manual command + SessionStart 6h-gate | (its own schedule) |

## Pick this harness (`neurawork-cc-harness`) when

- You are upgrading an **existing / brownfield** repo and want a one-shot **seed**
  to bootstrap the knowledge base or `CLAUDE.md`/`docs/`.
- You want the install **tailored by recon** (which dirs to exclude, how deep the
  `CLAUDE.md` hierarchy goes, language, etc.).
- You prefer the **Python + claude-agent-sdk** engine, or want the doc learner to
  maintain **tracked, in-repo** `CLAUDE.md` + `docs/` (not files under `.claude/`).

## `coding-suite` is fine when

- Greenfield repo, no seed needed, and you already use the rest of `coding-suite`.
- You want the lighter bash implementation and are happy with its defaults.

Neither tool is "better" everywhere — `coding-suite` is the broader toolkit;
`neurawork-cc-harness` is the focused, recon+seed, Python-SDK take on the same
memory/doc-drift problem.

## The collision rule

`knowledge-compiler` exists in **both** plugins. On a bare invocation the name is
ambiguous. **Always use the fully qualified form:**

- `neurawork-cc-harness:knowledge-compiler`
- `coding-suite:knowledge-compiler`

Do **not** run both knowledge-compilers against the **same** install dir in one
repo. If you want both for comparison, give them distinct dirs. The
`neurawork-cc-harness` skills are designed to coexist with each other
(`knowledge-compiler` + `claudemd-lerner` use separate dirs and distinct hook
markers); coexistence with `coding-suite` is your call per repo.
