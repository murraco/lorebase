# ADR 0002 — PostgreSQL full-text search instead of OpenSearch

**Status:** Accepted

## Context

The lexical half of hybrid retrieval needs keyword/BM25-style search
alongside the dense (embedding) half. The design doc's original milestone
plan (Hito 7) sketched a throwaway keyword-search placeholder, to be
replaced by a real search engine (OpenSearch) later — see
`docs/roadmap.md`, "Hallazgos previos al plan", finding 3.

## Decision

Use PostgreSQL's native full-text search (`tsvector` + GIN index +
`websearch_to_tsquery` + `ts_rank_cd`) as the real, permanent lexical
retriever — not a placeholder. `Chunk.search_vector` is a generated column
in the same table as everything else, populated automatically on write.

This was a deliberate correction to the original plan, made *before*
writing any retrieval code, not a change made after the placeholder was
already built: a throwaway implementation would have been pure rework,
since Postgres FTS is already exactly the lexical half hybrid search
needs.

## Consequences

**Gains:**
- No separate service to run, index, or keep synchronized with Postgres —
  the same transactional-consistency argument as ADR 0001 (pgvector).
- One query engine serves both halves of hybrid search plus every other
  relational query (workspaces, sources, citations), so there's a single
  place to reason about indexing, backups, and access control.
- Zero implementation waste: nothing built for the "placeholder" had to
  be thrown away, because there never was one.

**Costs / accepted limitations:**
- Postgres FTS's relevance tuning is less sophisticated than a dedicated
  search engine's (no learned ranking, coarser control over field
  boosting).
- `Chunk.search_vector` is currently pinned to `config="english"` even
  though the real corpus is a Spanish/English mix, which measurably hurts
  lexical precision on Spanish text (documented as known debt in
  `docs/roadmap.md`) — a limitation of *this specific configuration*, not
  of Postgres FTS as an approach; a per-document language config would
  fix it without migrating engines.
- No built-in horizontal scaling or clustering; a single Postgres
  instance is the ceiling.

**Migration trigger:** if the corpus grows to genuinely need distributed
search, faceted aggregation, or ranking sophistication Postgres FTS can't
reach, migrate to OpenSearch. Same isolation property as ADR 0001: lexical
search lives behind `Retriever` (`LexicalRetriever` specifically), so this
is a new implementation of one interface, not a redesign of the retrieval
or hybrid-fusion logic above it.
