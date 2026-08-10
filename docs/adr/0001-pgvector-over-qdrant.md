# ADR 0001 — pgvector instead of a dedicated vector database (Qdrant)

**Status:** Accepted

## Context

Lorebase needs dense (embedding) vector search as half of its hybrid
retrieval (the other half is lexical full-text search). The two mainstream
options were: extend the relational database Lorebase already runs
(PostgreSQL) with the `pgvector` extension, or run a purpose-built vector
database (Qdrant, Weaviate, Milvus) as a separate service.

This decision was made at the very start of the project, in the original
design document, before any retrieval code existed — not discovered as a
limitation later.

## Decision

Use `pgvector` as a PostgreSQL extension. `Chunk.embedding` is a native
column on the same row as the chunk's text, metadata, and lexical search
vector — one database, one transaction per write, nothing to keep in sync.

Retrieval itself is isolated behind a `Retriever` interface
(`rag/retrieval/base.py`), so nothing outside that module knows or cares
that vectors live in Postgres specifically.

## Consequences

**Gains:**
- Zero new infrastructure — no second database to provision, secure, back
  up, or monitor. `infra/scripts/backup.sh`/`restore.sh` cover vectors for
  free: `pg_dump` treats a `vector` column like any other extension type,
  nothing pgvector-specific was needed (see `docs/roadmap.md`, Etapa 18).
- A chunk and its embedding can never drift out of sync — they're written
  in the same transaction, by construction, not by a reconciliation
  process between two systems.
- One less moving part to reason about operationally, which matters more
  for a personal-scale project than raw ANN throughput does.

**Costs / accepted limitations:**
- pgvector's approximate nearest-neighbor search (HNSW) is not as fast or
  as tunable at large scale as a database built specifically for vector
  search. This is a real, known trade-off, not an oversight.
- Advanced vector-DB features (payload-based pre-filtering at the index
  level, distributed sharding) aren't available.

**Migration trigger:** if the corpus and query volume grow well past
personal-second-brain scale (many millions of chunks, or filtering
patterns pgvector's indexes don't serve well), migrate to Qdrant. The
`Retriever` abstraction means this is a new implementation behind the
same interface, not a redesign — `HybridRetriever`, `DateAwareRetriever`,
and everything above them are unaffected either way.
