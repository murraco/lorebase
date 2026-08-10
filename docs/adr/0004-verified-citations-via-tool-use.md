# ADR 0004 — Server-verified citations via structured tool-use

**Status:** Accepted

## Context

The design doc's original requirement ("Hallazgos previos al plan", finding
7) was that every answer must cite real sources — but simply *asking* the
model for citations in the prompt has no enforcement mechanism. An LLM can
still fabricate a plausible-looking `chunk_id`, cite a chunk from an earlier
turn that's no longer in context, or hallucinate a citation entirely — and
a prompt instruction can't stop any of that.

## Decision

The LLM doesn't write prose with inline citations — it calls a structured
tool (`ANSWER_TOOL`) that returns `answer` plus a `cited_chunk_ids` list.
Before anything is persisted, `rag/chat/service.py` intersects that list
against `chunks_by_id`, the exact set of chunks that were actually sent to
the model as context for this turn. Any id that isn't in that set — typo'd,
left over from an earlier turn, or invented outright — is silently dropped,
never becomes a `Citation` row. Surviving ids are then re-sorted by
retrieval rank (not by the order the model happened to list them), so the
citation numbering a reader sees means "how the retriever ranked this."

## Consequences

**Gains:**
- A citation is a guarantee, not a prompt request: it is structurally
  impossible for a persisted `Citation` to point at a chunk that wasn't in
  the model's real context, regardless of what the model claims.
- The check is a plain set-membership test, not another LLM call — no added
  cost or latency to enforce it.
- Because tool use also disciplines the model's output shape (an `answer`
  string plus a list of ids, not freeform prose to parse), it removes a
  whole class of citation-parsing bugs a regex-over-prose approach would
  have.

**Costs / accepted limitations:**
- Doesn't verify the *content* of the answer against the chunk — only that
  a cited chunk was genuinely in context. A model can still misrepresent
  what a real, correctly-cited chunk says; that's what `faithfulness` (the
  RAGAS metric, Etapa 16) is for, not this mechanism.
- Requires an LLM provider that supports forced tool use with a strict
  schema — a hard dependency on this specific capability, not something
  every provider offers equally well.

**Migration trigger:** none anticipated — this is a foundational mechanism,
not a placeholder. It would need to change only if a future LLM provider
lacks reliable structured tool-use output, at which point the validation
logic itself (dict lookup against `chunks_by_id`) stays the same; only how
the model's output is obtained would change.
