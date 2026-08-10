# ADR 0006 — Reciprocal Rank Fusion over a weighted score fusion

**Status:** Accepted

## Context

Hybrid search (Etapa 10) needs to combine two ranked lists — lexical
(Postgres FTS's `ts_rank_cd`) and dense (pgvector cosine similarity) — into
one ranking before reranking and sending results to the LLM. The two lists'
raw scores live on incomparable scales: `ts_rank_cd` is an unbounded
document-frequency-weighted value, cosine similarity is bounded to
`[-1, 1]`. Combining them by weighted sum (`w1 * lexical_score + w2 *
dense_score`) requires normalizing both onto a shared scale first, and
picking weights to begin with.

## Decision

`HybridRetriever` (`rag/retrieval/hybrid.py`) uses Reciprocal Rank Fusion:
`score(chunk) = sum(1 / (RRF_K + rank_in_list))` across every list a chunk
appears in, with `RRF_K = 60` — the constant from the original paper
(Cormack, Clarke & Grossman, SIGIR 2009), now a de facto industry default.
RRF deliberately ignores both retrievers' raw scores and uses only rank
position.

## Consequences

**Gains:**
- No normalization step and no weights to tune: rank position needs no
  cross-scale conversion the way a raw score does, so there's nothing to
  calibrate as the corpus or query mix changes.
- `RRF_K = 60` is a published, widely-reused default, not a value guessed
  and left untuned — a reasonable starting point without a tuning pass this
  project doesn't have data to justify yet.
- Adding a third ranked signal later (e.g., a recency-boosted list) is
  "compute one more rank list and sum one more term," not a new
  normalization scheme.

**Costs / accepted limitations:**
- Throws away real information: a chunk that barely beat its neighbor and
  a chunk that dominated it contribute identically to fusion if their ranks
  match — RRF can't distinguish "won by a landslide" from "won by a hair."
- No learned weighting between the lexical and dense signals — if one
  retriever is measurably more trustworthy for this corpus, RRF can't
  reflect that the way a tuned or learned weighted fusion could.

**Migration trigger:** if evaluation data (Etapa 16's harness) ever shows
one retriever is systematically more reliable and a fixed 50/50-by-rank
fusion is costing real precision/recall, move to a weighted or learned
fusion — informed by measurement, the same standard ADR 0005 already
applied to the direct-vs-agentic retrieval choice.
