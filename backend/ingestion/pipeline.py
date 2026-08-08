from collections.abc import Iterable
from uuid import UUID

from django.db import transaction

from ingestion.chunking.base import ChunkData
from ingestion.chunking.heading import HeadingChunker
from ingestion.models import Chunk
from ingestion.parsers.markdown import MarkdownParser
from ingestion.parsers.pdf import extract_pdf_pages
from sources.models import Document

_chunker = HeadingChunker()


@transaction.atomic
def process_document(
    document: Document,
    *,
    text: str | None = None,
    binary: bytes | None = None,
    section_boundary_pattern: str | None = None,
) -> None:
    """Parse + chunk a document's current content and persist its Chunks,
    replacing anything left over from a previous version wholesale rather
    than diffing individual chunks — simpler, and always correct.

    Exactly one of `text` (Markdown, from a text-based connector) or
    `binary` (PDF bytes) must be given.

    `section_boundary_pattern` comes from the owning Source's config (see
    sources.sync._ingest) — content with no Markdown headings at all (a
    flat journal file using bare timestamp lines, say) otherwise parses as
    one giant headingless section, chunked blindly by token budget alone.
    """
    parser = MarkdownParser(extra_boundary_pattern=section_boundary_pattern)
    if binary is not None:
        chunks_data = _chunk_pdf(binary, parser)
    else:
        assert text is not None, "process_document needs either text or binary"
        sections = parser.parse(text)
        chunks_data = _chunker.chunk(text, sections)

    document.chunks.all().delete()
    Chunk.objects.bulk_create(
        Chunk(
            document=document,
            index=i,
            content=chunk.content,
            heading_path=" > ".join(chunk.heading_path),
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            token_count=chunk.token_count,
            metadata=chunk.metadata,
        )
        for i, chunk in enumerate(chunks_data)
    )


def _chunk_pdf(binary: bytes, parser: MarkdownParser) -> list[ChunkData]:
    """Each PDF page is parsed and chunked independently — through the
    exact same MarkdownParser + HeadingChunker as any other note, so
    start_line/end_line stay meaningful (relative to that page's own
    converted text). The page number gets tagged onto each resulting chunk
    from the outside; neither the parser nor the chunker know PDFs exist.
    """
    all_chunks: list[ChunkData] = []
    for page_number, page_text in enumerate(extract_pdf_pages(binary), start=1):
        sections = parser.parse(page_text)
        for chunk in _chunker.chunk(page_text, sections):
            chunk.metadata = {**chunk.metadata, "page": page_number}
            all_chunks.append(chunk)
    return all_chunks


def purge_chunks_for_documents(document_ids: Iterable[UUID]) -> None:
    Chunk.objects.filter(document_id__in=document_ids).delete()
