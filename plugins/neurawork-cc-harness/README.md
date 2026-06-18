# neurawork-cc-harness

A Claude Code plugin that keeps a repo's project knowledge fresh. It bundles two
**independently installable** skills:

- **`knowledge-compiler`** — captures session transcripts into per-repo `daily/`
  logs and compiles them into a knowledge base (`knowledge/concepts/`,
  `knowledge/connections/`, `knowledge/index.md`).
- **`claudemd-lerner`** — learns from each session (git diff + conversation) and
  keeps the **CLAUDE.md hierarchy + `docs/`** current. No knowledge wiki.

Both install via a slash command, run an interactive **recon** (e.g. CLAUDE.md
level-depth, docs layout, excluded dirs), and **seed** an existing repo on first
install. Knowledge and docs are always written **inside the repo** — never under
`.claude/`.

## Status

Phase 1 (this commit): plugin scaffold + shared Python infrastructure
(`engines/_shared/`). No end-user skill behavior yet — skills land in Phases 2
and 3. See `.claude/PRPs/prds/neurawork-cc-harness.prd.md` in the host repo.

## Skill names & collision note

Skills resolve under the plugin namespace:

- `neurawork-cc-harness:claudemd-lerner` — collision-free.
- `neurawork-cc-harness:knowledge-compiler` — the bare name `knowledge-compiler`
  also exists in the `coding-suite` plugin. **Always invoke via the fully
  qualified `neurawork-cc-harness:knowledge-compiler` form** to avoid ambiguity.

## Shared infrastructure

`engines/_shared/` holds stdlib-only helpers reused by both skills:

| Module | Purpose |
|--------|---------|
| `hookio.py` | Parse hook stdin (Windows-safe) + recursion guard |
| `transcript.py` | Read a JSONL transcript → recent markdown turns |
| `gitctx.py` | Worktree detection + state redirect to main checkout |
| `settings.py` | Idempotent `.claude/settings.json` hook merge |
| `repo_guard.py` | Enforce: knowledge/docs in-repo, never under `.claude/` |
| `recon.py` | Git-root resolution + `RECON_JSON` emit for install recon |

## License

MIT — see `LICENSE`.
