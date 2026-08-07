import pytest
from django.db import IntegrityError

from sources.factories import DocumentFactory, SourceFactory
from sources.models import Source

pytestmark = pytest.mark.django_db


def test_source_defaults_to_pending_status() -> None:
    source = SourceFactory()

    assert source.status == Source.Status.PENDING


def test_document_defaults_to_version_one_and_not_deleted() -> None:
    document = DocumentFactory()

    assert document.version == 1
    assert document.deleted is False


def test_duplicate_external_id_within_same_source_is_rejected() -> None:
    source = SourceFactory()
    DocumentFactory(source=source, external_id="/notes/same.md")

    with pytest.raises(IntegrityError):
        DocumentFactory(source=source, external_id="/notes/same.md")


def test_same_external_id_is_allowed_across_different_sources() -> None:
    """external_id only needs to be unique per source, not globally."""
    document_a = DocumentFactory(external_id="/notes/same.md")
    document_b = DocumentFactory(external_id="/notes/same.md")

    assert document_a.source_id != document_b.source_id
