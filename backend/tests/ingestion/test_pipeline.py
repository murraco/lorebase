from collections.abc import Callable

import pytest

from ingestion.models import Chunk
from ingestion.pipeline import process_document, purge_chunks_for_documents
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_process_document_creates_chunks() -> None:
    document = DocumentFactory()

    process_document(document, text="# Title\n\nSome body text.")

    assert document.chunks.count() == 1
    chunk = document.chunks.get()
    assert chunk.index == 0
    assert chunk.heading_path == "Title"
    assert "Some body text." in chunk.content


def test_reprocessing_replaces_chunks_entirely() -> None:
    document = DocumentFactory()
    process_document(document, text="# A\n\nfirst version")
    first_chunk_id = document.chunks.get().id

    process_document(document, text="# B\n\nsecond version")

    chunk = document.chunks.get()
    assert chunk.id != first_chunk_id
    assert chunk.heading_path == "B"


def test_purge_chunks_for_documents_deletes_them() -> None:
    document = DocumentFactory()
    process_document(document, text="# A\n\nsome text")
    assert document.chunks.exists()

    purge_chunks_for_documents([document.id])

    assert not document.chunks.exists()


def test_purge_chunks_for_documents_does_not_touch_other_documents() -> None:
    kept = DocumentFactory()
    removed = DocumentFactory()
    process_document(kept, text="# Keep\n\ntext")
    process_document(removed, text="# Remove\n\ntext")

    purge_chunks_for_documents([removed.id])

    assert kept.chunks.exists()
    assert not removed.chunks.exists()
    assert Chunk.objects.filter(document=removed).count() == 0


def test_process_document_with_pdf_binary_tags_chunks_with_page_number(
    make_pdf_bytes: Callable[[list[tuple[str, str]]], bytes],
) -> None:
    document = DocumentFactory()
    pdf_bytes = make_pdf_bytes(
        [
            ("Page One", "First page body."),
            ("Page Two", "Second page body."),
        ]
    )

    process_document(document, binary=pdf_bytes)

    chunks = list(document.chunks.order_by("index"))
    assert len(chunks) == 2
    assert chunks[0].metadata == {"page": 1}
    assert chunks[1].metadata == {"page": 2}
    assert "First page body" in chunks[0].content
    assert "Second page body" in chunks[1].content


def test_reprocessing_a_pdf_replaces_chunks_entirely(
    make_pdf_bytes: Callable[[list[tuple[str, str]]], bytes],
) -> None:
    document = DocumentFactory()
    process_document(document, text="# Old\n\nwas markdown")
    old_chunk_id = document.chunks.get().id

    pdf_bytes = make_pdf_bytes([("New", "now a PDF")])
    process_document(document, binary=pdf_bytes)

    chunk = document.chunks.get()
    assert chunk.id != old_chunk_id
    assert chunk.metadata == {"page": 1}
