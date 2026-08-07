from collections.abc import Iterable
from uuid import UUID

from django.db import transaction

from ingestion.chunking.heading import HeadingChunker
from ingestion.models import Chunk
from ingestion.parsers.markdown import MarkdownParser
from sources.models import Document

_parser = MarkdownParser()
_chunker = HeadingChunker()


@transaction.atomic
def process_document(document: Document, text: str) -> None:
    """Parse + chunk a document's current content and persist its Chunks,
    replacing anything left over from a previous version wholesale rather
    than diffing individual chunks — simpler, and always correct.
    """
    sections = _parser.parse(text)
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
        )
        for i, chunk in enumerate(chunks_data)
    )


def purge_chunks_for_documents(document_ids: Iterable[UUID]) -> None:
    Chunk.objects.filter(document_id__in=document_ids).delete()
