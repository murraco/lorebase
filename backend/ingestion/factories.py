import factory
from factory.django import DjangoModelFactory

from ingestion.models import Chunk
from sources.factories import DocumentFactory


class ChunkFactory(DjangoModelFactory):
    class Meta:
        model = Chunk

    document = factory.SubFactory(DocumentFactory)
    index = factory.Sequence(lambda n: n)
    content = factory.Sequence(lambda n: f"Chunk content {n}")
    heading_path = ""
    start_line = 1
    end_line = 1
    token_count = 3
