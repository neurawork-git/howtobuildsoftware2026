# AGENTS.md — Knowledge Compiler Constitution

This file is the specification the compiler LLM follows when turning raw session
logs into a structured, queryable knowledge base. Read it in full before
compiling, querying, seeding, or linting.

> Lineage: this is a repo-local implementation of the LLM-as-compiler knowledge
> base idea popularised by Andrej Karpathy's LLM wiki and rebuilt openly by
> coleam00's claude-memory-compiler. The design below is independent NeuraWork
> work; only the underlying concept is shared.

## The Compiler Model

```
daily/        source code   — raw session logs, append-only, never rewritten
LLM           compiler      — reads logs, emits/maintains articles
knowledge/    executable    — the structured, queryable knowledge base
lint          test suite    — structural + semantic health checks
query         runtime       — answering questions from the base
```

Knowledge is never organised by hand. Sessions produce logs; the compiler does
the synthesis, cross-linking, and upkeep.

## Layout

```
daily/                       session logs (immutable source), one file per day
knowledge/
  index.md                   master catalog — the retrieval mechanism
  log.md                     append-only build log
  concepts/                  atomic knowledge articles
  connections/               cross-cutting insights linking 2+ concepts
  qa/                        filed query answers (optional, grows over time)
```

All knowledge lives inside the repository, under the knowledge directory. Never
write under `.claude/`.

## Daily Log Format

```markdown
# Daily Log: YYYY-MM-DD

## Sessions

### Session (HH:MM)

**Context:** what was being worked on.

**Key Exchanges:**
- notable question/answer or discussion

**Decisions Made:**
- decision with its rationale

**Lessons Learned:**
- gotcha, pattern, or insight

**Action Items:**
- [ ] follow-up
```

## Article Formats

### Concept article — `knowledge/concepts/<slug>.md`

One atomic idea per file: a fact, pattern, decision, convention, or lesson.

```markdown
---
title: "Concept Name"
aliases: [other-name]
tags: [domain, topic]
sources:
  - "daily/2026-06-18.md"
created: 2026-06-18
updated: 2026-06-18
---

# Concept Name

Two to four sentences stating the concept plainly.

## Key Points

- self-contained bullet (aim for 3-5)

## Details

Encyclopedia-style paragraphs (2+). Factual, neutral, specific to this repo.

## Related Concepts

- [[concepts/other-concept]] — how it relates

## Sources

- [[daily/2026-06-18.md]] — what was extracted from it
```

### Connection article — `knowledge/connections/<slug>.md`

Created only when a log exposes a non-obvious relationship between 2+ concepts
that already have articles.

```markdown
---
title: "Connection: X and Y"
connects:
  - "concepts/x"
  - "concepts/y"
sources:
  - "daily/2026-06-18.md"
created: 2026-06-18
updated: 2026-06-18
---

# Connection: X and Y

## The Connection

What ties these concepts together.

## Key Insight

The non-obvious part.

## Evidence

Concrete examples from the logs.

## Related Concepts

- [[concepts/x]]
- [[concepts/y]]
```

### Q&A article — `knowledge/qa/<slug>.md`

Optional. Written by `query --file-back` to persist an answer.

```markdown
---
title: "Q: the question"
question: "the exact question asked"
consulted:
  - "concepts/a"
filed: 2026-06-18
---

# Q: the question

## Answer

The synthesized answer with [[wikilinks]] to the articles consulted.

## Sources Consulted

- [[concepts/a]] — why it was relevant
```

## Index — `knowledge/index.md`

A table of every article. The compiler and the query engine read this FIRST,
then open only the articles a task needs.

```markdown
# Knowledge Base Index

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
| [[concepts/example]] | one-line summary | daily/2026-06-18.md | 2026-06-18 |
```

## Build Log — `knowledge/log.md`

Append-only. One entry per compile/query/lint:

```markdown
## [2026-06-18T14:30:00-05:00] compile | 2026-06-18.md
- Source: daily/2026-06-18.md
- Created: [[concepts/example]]
- Updated: (none)
```

## Compile Rules (daily/ → knowledge/)

1. Read the daily log, then `index.md`, then any existing articles it touches.
2. Extract 3-7 distinct concepts per log — no more. Quality over volume.
3. **Prefer UPDATE over CREATE.** If a concept already has an article, add the
   new information and append the daily log to its `sources:`; don't make a
   near-duplicate.
4. Create a `connections/` article only for genuinely non-obvious links between
   existing concepts.
5. Every article carries complete YAML frontmatter and cites its source daily
   log(s) in `sources:` and the `## Sources` section.
6. Every article links to at least two others via `[[wikilinks]]`.
7. Wikilinks use repo-relative paths from `knowledge/`, no `.md` extension:
   `[[concepts/slug]]`, `[[connections/slug]]`. Daily-log references are written
   `[[daily/YYYY-MM-DD.md]]` (keeps the extension; not an article).
8. Update `index.md` (add/modify rows) and append to `log.md` after writing.

## Query Rules

1. Read `index.md` first.
2. Pick 3-10 relevant articles and read them in full.
3. Synthesize an answer that cites sources with `[[wikilinks]]`.
4. If the base lacks the answer, say so plainly — do not invent.

## Why No RAG

At repo scale (tens to a few hundred articles) an LLM reasoning over a curated
index beats vector similarity: embeddings match similar words, the LLM matches
relevant meaning. Index-guided retrieval is the design. If a base ever grows
past roughly 2,000 articles / ~2M tokens the index stops fitting in context;
add a keyword+semantic search layer at that point. Until then, no embeddings,
no chunking, no vector store.

## Lint Checks

Structural (free): broken wikilinks, orphan pages (no inbound links), orphan
sources (uncompiled daily logs), stale articles (source log changed since
compile), missing backlinks (A→B but not B→A), sparse articles (<200 words).
Semantic (LLM): contradictions across articles. Reports go to `reports/`.

## Conventions

- Dates ISO 8601 (`YYYY-MM-DD`); timestamps full ISO with offset.
- File names lowercase, hyphenated.
- Writing style: factual, neutral, encyclopedia-like.
- Frontmatter minimum: `title`, `sources`, `created`, `updated`.
