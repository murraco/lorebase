import factory
from factory.django import DjangoModelFactory

from core.factories import WorkspaceFactory
from sources.models import Document, Source


class SourceFactory(DjangoModelFactory):
    class Meta:
        model = Source

    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"Source {n}")
    type = Source.SourceType.LOCAL_FOLDER


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document

    source = factory.SubFactory(SourceFactory)
    external_id = factory.Sequence(lambda n: f"/notes/note-{n}.md")
    path = factory.LazyAttribute(lambda o: o.external_id)
    title = factory.Sequence(lambda n: f"Note {n}")
    content_hash = factory.Faker("sha256")
