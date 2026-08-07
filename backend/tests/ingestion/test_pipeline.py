import pytest

from ingestion.models import Chunk
from ingestion.pipeline import process_document, purge_chunks_for_documents
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_process_document_creates_chunks() -> None:
    document = DocumentFactory()

    process_document(document, "# Title\n\nSome body text.")

    assert document.chunks.count() == 1
    chunk = document.chunks.get()
    assert chunk.index == 0
    assert chunk.heading_path == "Title"
    assert "Some body text." in chunk.content


def test_reprocessing_replaces_chunks_entirely() -> None:
    document = DocumentFactory()
    process_document(document, "# A\n\nfirst version")
    first_chunk_id = document.chunks.get().id

    process_document(document, "# B\n\nsecond version")

    chunk = document.chunks.get()
    assert chunk.id != first_chunk_id
    assert chunk.heading_path == "B"


def test_purge_chunks_for_documents_deletes_them() -> None:
    document = DocumentFactory()
    process_document(document, "# A\n\nsome text")
    assert document.chunks.exists()

    purge_chunks_for_documents([document.id])

    assert not document.chunks.exists()


def test_purge_chunks_for_documents_does_not_touch_other_documents() -> None:
    kept = DocumentFactory()
    removed = DocumentFactory()
    process_document(kept, "# Keep\n\ntext")
    process_document(removed, "# Remove\n\ntext")

    purge_chunks_for_documents([removed.id])

    assert kept.chunks.exists()
    assert not removed.chunks.exists()
    assert Chunk.objects.filter(document=removed).count() == 0
