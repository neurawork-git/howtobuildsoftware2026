---
title: "Connection Articles Enable Backward Retrieval a Forward-Only Agent Misses"
aliases: [backward-retrieval, connection-article-value, probe-3]
tags: [knowledge-base, retrieval, query, connections]
sources:
  - "daily/2026-08-27.md"
created: 2026-08-27
updated: 2026-08-27
---

# Connection Articles Enable Backward Retrieval a Forward-Only Agent Misses

The `0.3.1` bump round existed to run four validation probes (Task 11), and probe
#3 tests exactly what connection articles are for: a query where the agent must
surface `connections/sdk-subprocess-forces-api-key.md` — a cross-cutting insight
a forward-only agent, reasoning strictly from concept to concept, would never
reach. The probe validates that the index-guided design retrieves non-obvious
links, not just the concepts a question names directly.

## Key Points

- Probe #3 is the key test: the agent must return
  [[connections/sdk-subprocess-forces-api-key]], which links the SDK subprocess
  model to the API-key requirement.
- A "forward-only" agent that walks from a named concept forward would never find
  that connection; the connection article is the retrieval bridge.
- This is why the schema mandates connection articles for genuinely non-obvious
  links and why every article carries ≥2 backlinks — retrieval depends on them.
- The four Task 11 probes were the original reason for the version-bump round.

## Details

Connection articles are not decorative cross-references; they are load-bearing
retrieval structure. A question phrased around one concept (e.g. authentication)
will not name the other (the subprocess packaging model), so an agent that only
expands outward from the named concept can miss the insight that ties them
together. The connection article gives the index a directly retrievable node for
that relationship, so the query engine can find it via `index.md` first-read.

Probe #3 makes this testable: success means the retrieval surfaced the
connection article on its own. This is the practical justification for Compile
Rule 4 (create connection articles for non-obvious links) and Rule 6 (every
article links to at least two others) — the graph density is what makes
backward-reachable insights retrievable at query time.

## Related Concepts

- [[connections/sdk-subprocess-forces-api-key]] — the exact connection article probe #3 must retrieve
- [[concepts/plugin-version-bump-propagates-cache]] — the bump round whose purpose was running these probes

## Sources

- [[daily/2026-08-27.md]] — Task 11 probes; probe #3 must return the sdk-subprocess-forces-api-key connection a forward-only agent would never find
