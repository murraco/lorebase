# ADR 0005 — Direct retrieval instead of agentic retrieval

**Status:** Accepted

## Context

The original design doc (§5) sketched agentic retrieval as the intended
query flow: the LLM decides what to search for, via tool use, possibly
issuing several searches before answering — as opposed to direct retrieval,
where the query is embedded and searched once, and the LLM only ever sees
the results. §4.12 of the same document described direct retrieval instead,
an internal contradiction noted as finding 6 in `docs/roadmap.md`. The MVP
shipped with direct retrieval and query rewriting, deferring the choice
until an evaluation harness existed to decide with data instead of
intuition (Etapa 16).

## Decision

Both strategies were implemented (`ask_with_contexts()` for direct,
`ask_agentic()` for agentic, sharing one contract so `manage.py evaluate
--strategy {direct,agentic}` picks between them with no conditional logic
beyond which function to call) and run against the same 30-question golden
set with the same judge model:

| Metric | Direct | Agentic |
|---|---|---|
| Hit-rate | 30/30 | 30/30 |
| `context_precision` | 0.809 | 0.724 |
| `context_recall` | 0.900 | 0.928 |
| `faithfulness` | 0.950 | 0.930 |
| `answer_relevancy` | 0.924 | 0.928 |
| Avg. latency | 3.6s | 14.4s |
| Avg. input tokens | 2,658 | 4,348 |

Direct retrieval is what's wired into the app. No quality metric justified
paying 4x the latency and ~40% more input tokens for agentic retrieval on
this corpus.

## Consequences

**Gains:**
- Every chat request costs one embedding call and one LLM call, not a
  variable, LLM-decided number of search round-trips — predictable latency
  and cost, which matters more for a personal tool used interactively than
  a marginal quality gain would.
- The measured comparison, not just the simpler implementation, is the
  actual justification — reversible if the corpus or question shape changes
  enough to favor agentic's real advantage (recovering from an
  insufficient first search).

**Costs / accepted limitations:**
- The golden set is mostly single-fact questions that direct retrieval
  already answers correctly on the first try — there is no genuinely
  multi-hop question in it that would give agentic retrieval a chance to
  show its theoretical advantage. The finding is "direct already works well
  on *this* corpus," not "agentic retrieval never helps."
- The agentic code path (`rag/chat/agentic.py`, `LLMProvider.stream_tools()`)
  is built, tested, and kept in the codebase but not exposed in the app UI
  — live code with no caller from the product surface, an unusual state
  deliberately accepted here rather than deleted.

**Migration trigger:** real multi-hop questions showing up in practice (a
first search that's genuinely insufficient and needs a follow-up search to
answer correctly), or a UI decision to offer agentic retrieval as an
opt-in, slower-but-more-thorough mode — both are additive, not a redesign,
since the code already exists and shares its contract with the direct path.
