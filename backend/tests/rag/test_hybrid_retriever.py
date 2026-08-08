from unittest.mock import patch

import pytest
from django.conf import settings

from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.retrieval.hybrid import HybridRetriever
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def _unit_vector(index: int = 0) -> list[float]:
    vector = [0.0] * settings.EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


def _search(query: str, query_vector: list[float], **kwargs):
    with patch("rag.retrieval.dense.get_embedding_provider") as mock_factory:
        mock_factory.return_value.embed_query.return_value = query_vector
        return HybridRetriever().search(query, **kwargs)


def test_surfaces_a_lexical_only_and_a_dense_only_match() -> None:
    """Neither retriever alone would find both of these; RRF fusion should."""
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    query_vector = _unit_vector()

    lexical_only = ChunkFactory(
        document=document,
        content="How to configure a kubernetes deployment step by step.",
        embedding=[-v for v in query_vector],  # deliberately far in vector space
    )
    dense_only = ChunkFactory(
        document=document,
        content="Completely unrelated grocery shopping list for the week.",
        embedding=query_vector,  # deliberately close in vector space
    )

    results = _search("kubernetes deployment", query_vector, workspace_id=workspace.id)

    result_ids = {r.chunk.id for r in results}
    assert lexical_only.id in result_ids
    assert dense_only.id in result_ids


def test_a_chunk_matching_both_lists_outranks_one_matching_only_one() -> None:
    """The RRF property worth internalizing: consensus across both lists
    beats being #1 in just one, which is what the k=60 damping buys.
    """
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    query_vector = _unit_vector()

    both = ChunkFactory(
        document=document, content="kubernetes deployment guide", embedding=query_vector
    )
    lexical_only = ChunkFactory(
        document=document,
        content="kubernetes deployment troubleshooting",
        embedding=[-v for v in query_vector],
    )

    results = _search("kubernetes deployment", query_vector, workspace_id=workspace.id)

    assert results[0].chunk.id == both.id
    assert results[1].chunk.id == lexical_only.id
