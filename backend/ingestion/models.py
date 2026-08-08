from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from pgvector.django import HnswIndex, VectorField

from core.models import BaseModel
from sources.models import Document


class Chunk(BaseModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    index = models.PositiveIntegerField()
    content = models.TextField()
    heading_path = models.CharField(max_length=1024, blank=True, default="")
    start_line = models.PositiveIntegerField()
    end_line = models.PositiveIntegerField()
    token_count = models.PositiveIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    # NULL until embeddings get computed — the column and its index exist
    # from day one so populating it later is a data backfill, not a schema
    # migration plus reindex of everything.
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS, null=True, blank=True)
    # DB-computed and always in sync with `content`, by Postgres itself —
    # no trigger to maintain, no risk of drifting out of date.
    # config="english" for now, even though notes are realistically a mix
    # of Spanish and English — proper per-document language config is
    # tracked as known debt in the roadmap rather than built speculatively.
    search_vector = models.GeneratedField(
        expression=SearchVector("content", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "index"], name="unique_chunk_index_per_document"
            )
        ]
        indexes = [
            GinIndex(fields=["search_vector"], name="chunk_search_vector_gin"),
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    @property
    def content_with_heading(self) -> str:
        """What retrieval should actually work over: the chunk's text with
        its heading breadcrumb prepended.

        Deliberately not folded into `content` itself — that stays a
        faithful slice of the source file, which is what makes
        start_line/end_line (and therefore every citation) exact. This is
        a derived view for embedding and prompting only.

        It exists because a chunk's own text frequently does NOT contain
        its heading: HeadingChunker splits any section over max_tokens at
        paragraph boundaries, and every piece after the first starts below
        the heading line, so it cannot include it. In a dated journal that
        means most chunks of a long entry have no date anywhere in
        `content` — the date lives only in heading_path. Embedding and
        prompting on `content` alone made those chunks effectively
        undateable, which is the root cause DateAwareRetriever was
        working around from the other end.
        """
        if not self.heading_path:
            return self.content
        return f"{self.heading_path}\n\n{self.content}"

    def __str__(self) -> str:
        return f"{self.document} #{self.index}"
