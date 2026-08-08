from unittest.mock import patch

import pytest

from ingestion.factories import ChunkFactory
from ingestion.pipeline import process_document
from rag.embeddings.service import embed_pending_chunks
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_embeds_the_heading_path_along_with_the_content() -> None:
    """What gets embedded is content_with_heading, not content — otherwise
    a chunk split off the middle of a dated section carries no date into
    its vector at all.
    """
    ChunkFactory(heading_path="2025-07-21 > Work", content="Finished the refactor.")

    with patch("rag.embeddings.service.get_embedding_provider") as mock_get_provider:
        mock_get_provider.return_value.embed_documents.return_value = [[0.0] * 1024]
        embed_pending_chunks()

    embedded_texts = mock_get_provider.return_value.embed_documents.call_args[0][0]
    assert embedded_texts == ["2025-07-21 > Work\n\nFinished the refactor."]


def test_embeds_all_pending_chunks() -> None:
    document = DocumentFactory()
    text = "# A\n\ntext one\n\n## B\n\ntext two, long enough to not merge back up"
    process_document(document, text=text)

    assert document.chunks.filter(embedding__isnull=True).exists()

    embedded_count = embed_pending_chunks()

    assert embedded_count == document.chunks.count()
    assert not document.chunks.filter(embedding__isnull=True).exists()


def test_does_not_touch_already_embedded_chunks() -> None:
    document = DocumentFactory()
    process_document(document, text="# A\n\nsome text")
    embed_pending_chunks()
    chunk = document.chunks.get()
    original_vector = chunk.embedding

    # Nothing new to embed -> should be a no-op.
    embedded_count = embed_pending_chunks()

    chunk.refresh_from_db()
    assert embedded_count == 0
    assert chunk.embedding == original_vector


def test_respects_batch_size_across_multiple_db_batches() -> None:
    # Five separate documents (one chunk each) rather than relying on the
    # chunker's merge heuristics to produce a specific chunk count from
    # one document — this test is about pagination, not chunking.
    documents = [DocumentFactory() for _ in range(5)]
    for i, document in enumerate(documents):
        process_document(document, text=f"# Doc {i}\n\nsome text")
    assert sum(d.chunks.count() for d in documents) == 5

    embedded_count = embed_pending_chunks(batch_size=2)

    assert embedded_count == 5
    for document in documents:
        assert not document.chunks.filter(embedding__isnull=True).exists()
