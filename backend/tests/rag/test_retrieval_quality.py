"""A small quality battery against a real Voyage account — not a unit
test of our code's mechanics (those are covered elsewhere with fake
providers and hand-crafted vectors), but a check that hybrid + reranked
retrieval actually finds the right chunk for realistic natural-language
questions, some paraphrased enough that lexical search alone wouldn't
catch them.

Skipped unless RUN_RETRIEVAL_QUALITY_TEST=1 is set explicitly — deliberately
NOT gated on VOYAGE_API_KEY alone. A key can be present in backend/.env for
other manual verification without that silently turning this ~10+ minute,
real-money test into something that runs on every local `make test`.
"""

import os
import time

import pytest
from django.conf import settings

from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.embeddings.factory import get_embedding_provider
from rag.embeddings.service import embed_pending_chunks
from rag.reranking.factory import get_reranker
from rag.retrieval.factory import get_retriever
from sources.factories import DocumentFactory

_opted_in = os.environ.get("RUN_RETRIEVAL_QUALITY_TEST") == "1"
_has_key = bool(settings.VOYAGE_API_KEY)

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        not (_opted_in and _has_key),
        reason="opt-in only: set RUN_RETRIEVAL_QUALITY_TEST=1 and a real VOYAGE_API_KEY",
    ),
]

NOTES = [
    "Hybrid search combines BM25 lexical search with dense vector retrieval "
    "using embeddings, then merges the two ranked lists with an algorithm "
    "like Reciprocal Rank Fusion.",
    "A cross-encoder reranker scores a query and a document together in a "
    "single forward pass, which makes it far more accurate than comparing "
    "independently computed embedding vectors, but also much more "
    "computationally expensive.",
    "Celery tasks can be chained by calling another task's delay() method "
    "from inside a task, which dispatches a brand new message to the "
    "broker rather than running the second task inline.",
    "Django's GeneratedField lets Postgres compute and store a column "
    "automatically from other columns, such as a tsvector search column "
    "derived from a text field, without needing a manual trigger.",
    "PDF files are converted to Markdown text before chunking, so the exact "
    "same heading-based chunker used for plain notes also handles PDFs "
    "without any special-casing for the format.",
    "A cache backend can implement a distributed lock using an atomic "
    "set-if-not-exists operation, which is exactly what Redis's SET NX "
    "command provides.",
    "PostgreSQL's pgvector extension adds an HNSW index for approximate "
    "nearest neighbor search over high-dimensional vectors, trading a "
    "small amount of accuracy for a large speed improvement.",
    "An embedding API can treat queries and documents asymmetrically: "
    "which mode you pick changes an internal prompt that gets prepended "
    "to the text before it's encoded.",
]

QUESTIONS = [
    ("What is Reciprocal Rank Fusion used for?", 0),
    ("How does hybrid search combine BM25 and embeddings?", 0),
    ("Why is a cross-encoder more accurate than comparing embeddings separately?", 1),
    ("Why can't you run a reranker over your entire database?", 1),
    ("How do you chain Celery tasks together?", 2),
    ("What happens when you call delay() on a task from inside another task?", 2),
    ("How does Django automatically compute a search column from text?", 3),
    ("What is a GeneratedField used for in Postgres full text search?", 3),
    ("How are PDFs turned into chunks?", 4),
    ("Does converting a PDF to text require a separate chunking codepath?", 4),
    ("How can Redis implement a distributed lock?", 5),
    ("What Redis command provides atomic set-if-not-exists?", 5),
    ("What index does pgvector use for approximate nearest neighbor search?", 6),
    (
        "How do vector databases search millions of embeddings quickly, "
        "without checking each one?",
        6,
    ),
    ("How does an embeddings API differentiate embedding a query from a document?", 7),
]


def test_hybrid_reranked_retrieval_finds_the_right_note_for_most_questions(settings) -> None:
    settings.EMBEDDING_PROVIDER = "voyage"
    settings.RERANK_PROVIDER = "voyage"
    settings.RETRIEVAL_STRATEGY = "hybrid_reranked"
    get_embedding_provider.cache_clear()
    get_reranker.cache_clear()
    get_retriever.cache_clear()

    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    chunks = [ChunkFactory(document=document, content=note) for note in NOTES]
    embed_pending_chunks()

    retriever = get_retriever()
    failures = []
    for i, (question, expected_index) in enumerate(QUESTIONS):
        if i > 0:
            # hybrid_reranked makes 2 API calls per question (embed + rerank).
            # Free-tier Voyage accounts without a payment method on file are
            # capped at 3 requests/minute (verified against a real account,
            # 2026-08) — this test is skipped by default specifically
            # because it's slow and makes real paid calls, so pacing to
            # respect that cap is acceptable here, not something to do in
            # any actual request path.
            time.sleep(45)
        results = retriever.search(question, workspace_id=workspace.id, top_k=3)
        top_ids = [r.chunk.id for r in results]
        if chunks[expected_index].id not in top_ids:
            failures.append((question, NOTES[expected_index]))

    get_embedding_provider.cache_clear()
    get_reranker.cache_clear()
    get_retriever.cache_clear()

    accuracy = (len(QUESTIONS) - len(failures)) / len(QUESTIONS)
    failure_report = "\n".join(f"  - {q!r} (expected: {note[:60]}...)" for q, note in failures)
    assert accuracy >= 0.8, (
        f"Only {accuracy:.0%} of questions found the expected chunk in the top 3:\n{failure_report}"
    )
