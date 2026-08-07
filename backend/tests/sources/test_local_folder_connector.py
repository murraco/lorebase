import logging
from pathlib import Path

import pytest

from sources.connectors.base import ConnectorConfigError, ConnectorConnectionError
from sources.connectors.local_folder import LocalFolderConnector


def test_validate_config_requires_path() -> None:
    connector = LocalFolderConnector({})

    with pytest.raises(ConnectorConfigError):
        connector.validate_config()


def test_test_connection_requires_existing_directory(tmp_path: Path) -> None:
    connector = LocalFolderConnector({"path": str(tmp_path / "does-not-exist")})

    with pytest.raises(ConnectorConnectionError):
        connector.test_connection()


def test_fetch_documents_reads_plain_markdown(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("Just some content.")

    connector = LocalFolderConnector({"path": str(tmp_path)})
    (doc,) = list(connector.fetch_documents())

    assert doc.external_id == "note.md"
    assert doc.title == "note"  # falls back to the filename stem
    assert doc.content == "Just some content."
    assert doc.metadata == {}


def test_fetch_documents_parses_front_matter(tmp_path: Path) -> None:
    raw_text = "---\ntitle: My Note\ntags: [rag, llm]\n---\nBody text."
    (tmp_path / "note.md").write_text(raw_text)

    connector = LocalFolderConnector({"path": str(tmp_path)})
    (doc,) = list(connector.fetch_documents())

    assert doc.title == "My Note"
    assert doc.metadata == {"title": "My Note", "tags": ["rag", "llm"]}
    # The front matter block itself stays in `content` — line numbers must
    # match the real file on disk, so nothing gets stripped here.
    assert doc.content == raw_text


def test_fetch_documents_recurses_into_subdirectories(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.md").write_text("nested")
    (tmp_path / "top.md").write_text("top")

    connector = LocalFolderConnector({"path": str(tmp_path)})
    external_ids = {doc.external_id for doc in connector.fetch_documents()}

    assert external_ids == {"sub/nested.md", "top.md"}


def test_fetch_documents_ignores_non_markdown_files(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("keep")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")

    connector = LocalFolderConnector({"path": str(tmp_path)})
    external_ids = {doc.external_id for doc in connector.fetch_documents()}

    assert external_ids == {"note.md"}


def test_content_hash_changes_when_content_changes(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("version one")
    connector = LocalFolderConnector({"path": str(tmp_path)})
    (first,) = list(connector.fetch_documents())

    note.write_text("version two")
    (second,) = list(connector.fetch_documents())

    assert first.content_hash != second.content_hash


def test_content_hash_is_stable_when_content_is_unchanged(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("stable content")
    connector = LocalFolderConnector({"path": str(tmp_path)})

    first = next(connector.fetch_documents()).content_hash
    second = next(connector.fetch_documents()).content_hash

    assert first == second


def test_oversized_file_is_skipped_and_logged(
    tmp_path: Path, settings, caplog: pytest.LogCaptureFixture
) -> None:
    settings.MAX_DOCUMENT_SIZE_BYTES = 10
    (tmp_path / "huge.md").write_text("this is definitely more than ten bytes")
    (tmp_path / "small.md").write_text("ok")

    connector = LocalFolderConnector({"path": str(tmp_path)})
    with caplog.at_level(logging.WARNING):
        external_ids = {doc.external_id for doc in connector.fetch_documents()}

    assert external_ids == {"small.md"}
    assert "huge.md" in caplog.text
