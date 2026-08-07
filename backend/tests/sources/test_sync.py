from collections.abc import Callable
from pathlib import Path

import pytest
from django.db import connection

from sources.factories import SourceFactory
from sources.models import Document, Source
from sources.sync import sync_source

pytestmark = pytest.mark.django_db


def make_local_source(tmp_path: Path) -> Source:
    return SourceFactory(config={"path": str(tmp_path)})


def test_first_sync_creates_documents(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Title\n\nSome content.")
    (tmp_path / "b.md").write_text("b")
    source = make_local_source(tmp_path)

    stats = sync_source(source)

    assert (stats.added, stats.updated, stats.deleted) == (2, 0, 0)
    assert source.documents.count() == 2

    document_a = source.documents.get(external_id="a.md")
    chunk = document_a.chunks.get()
    assert chunk.heading_path == "Title"
    assert (chunk.start_line, chunk.end_line) == (1, 3)


def test_second_sync_with_no_changes_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a")
    source = make_local_source(tmp_path)
    sync_source(source)

    with connection.execute_wrapper(_forbid_writes):
        stats = sync_source(source)

    assert (stats.added, stats.updated, stats.deleted) == (0, 0, 0)


def test_modified_file_is_updated_and_version_bumped(tmp_path: Path) -> None:
    note = tmp_path / "a.md"
    note.write_text("original")
    source = make_local_source(tmp_path)
    sync_source(source)

    note.write_text("changed")
    stats = sync_source(source)

    document = source.documents.get(external_id="a.md")
    assert (stats.added, stats.updated, stats.deleted) == (0, 1, 0)
    assert document.version == 2
    assert document.content_hash  # updated, not asserting the exact value


def test_modified_file_gets_its_chunks_replaced(tmp_path: Path) -> None:
    note = tmp_path / "a.md"
    note.write_text("# Original\n\noriginal content")
    source = make_local_source(tmp_path)
    sync_source(source)
    document = source.documents.get(external_id="a.md")
    old_chunk_id = document.chunks.get().id

    note.write_text("# Changed\n\nnew content")
    sync_source(source)

    document.refresh_from_db()
    chunk = document.chunks.get()
    assert chunk.id != old_chunk_id
    assert chunk.heading_path == "Changed"


def test_removed_file_is_soft_deleted(tmp_path: Path) -> None:
    note = tmp_path / "a.md"
    note.write_text("a")
    source = make_local_source(tmp_path)
    sync_source(source)
    document = source.documents.get(external_id="a.md")
    assert document.chunks.exists()

    note.unlink()
    stats = sync_source(source)

    document.refresh_from_db()
    assert (stats.added, stats.updated, stats.deleted) == (0, 0, 1)
    assert document.deleted is True
    assert not document.chunks.exists()


def test_readded_file_revives_the_soft_deleted_document(tmp_path: Path) -> None:
    """A document coming back from deletion must be revived in place, not
    collide with the unique (source, external_id) constraint."""
    note = tmp_path / "a.md"
    note.write_text("a")
    source = make_local_source(tmp_path)
    sync_source(source)
    note.unlink()
    sync_source(source)

    note.write_text("a is back")
    stats = sync_source(source)

    assert (stats.added, stats.updated, stats.deleted) == (1, 0, 0)
    assert source.documents.filter(external_id="a.md").count() == 1
    document = source.documents.get(external_id="a.md")
    assert document.deleted is False
    # v1 on create; soft-delete only flips a status flag, no content
    # changed, so no bump; revive sets content again -> v2.
    assert document.version == 2


def test_sync_reports_all_three_kinds_of_change_together(tmp_path: Path) -> None:
    (tmp_path / "unchanged.md").write_text("unchanged")
    (tmp_path / "to_modify.md").write_text("original")
    (tmp_path / "to_delete.md").write_text("bye")
    source = make_local_source(tmp_path)
    sync_source(source)

    (tmp_path / "to_modify.md").write_text("modified")
    (tmp_path / "to_delete.md").unlink()
    (tmp_path / "new.md").write_text("new")
    stats = sync_source(source)

    assert (stats.added, stats.updated, stats.deleted) == (1, 1, 1)
    assert Document.objects.filter(source=source, deleted=False).count() == 3


def test_pdf_sync_caches_the_original_and_tags_chunks_with_page(
    tmp_path: Path, make_pdf_bytes: Callable[[list[tuple[str, str]]], bytes]
) -> None:
    (tmp_path / "paper.pdf").write_bytes(
        make_pdf_bytes(
            [
                ("Page One", "First page body."),
                ("Page Two", "Second page body."),
            ]
        )
    )
    source = make_local_source(tmp_path)

    stats = sync_source(source)

    assert (stats.added, stats.updated, stats.deleted) == (1, 0, 0)
    document = source.documents.get(external_id="paper.pdf")
    assert document.original_file.name
    assert document.original_file.read()  # the cached bytes are readable back

    chunks = list(document.chunks.order_by("index"))
    assert len(chunks) == 2
    assert chunks[0].metadata == {"page": 1}
    assert chunks[1].metadata == {"page": 2}


def _forbid_writes(execute, sql, params, many, context):  # type: ignore[no-untyped-def]
    if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
        raise AssertionError(f"unexpected write query: {sql}")
    return execute(sql, params, many, context)
