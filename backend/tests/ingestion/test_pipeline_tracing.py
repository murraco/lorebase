import pytest

from ingestion.pipeline import process_document
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_process_document_records_a_span_with_chunk_count(otel_spans) -> None:
    document = DocumentFactory()

    process_document(document, text="# Title\n\nSome content here.")

    (span,) = otel_spans.get_finished_spans()
    assert span.name == "ingestion.process_document"
    assert span.attributes["document.id"] == str(document.id)
    assert span.attributes["document.format"] == "markdown"
    assert span.attributes["ingestion.chunks_created"] == 1


def test_process_document_records_pdf_format(otel_spans, make_pdf_bytes) -> None:
    document = DocumentFactory()
    pdf_bytes = make_pdf_bytes([("Heading", "Body text.")])

    process_document(document, binary=pdf_bytes)

    (span,) = otel_spans.get_finished_spans()
    assert span.attributes["document.format"] == "pdf"
