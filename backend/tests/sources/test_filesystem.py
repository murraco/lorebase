from pathlib import Path

import pytest

from sources.filesystem import BrowsePathError, list_directory


@pytest.fixture(autouse=True)
def _browse_root(settings, tmp_path: Path) -> Path:
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def test_lists_subdirectories_at_the_root(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "journal").mkdir()
    (tmp_path / "not-a-dir.txt").write_text("x")

    listing = list_directory("")

    assert listing.path == ""
    assert listing.parent is None
    assert [entry.name for entry in listing.entries] == ["journal", "notes"]


def test_entries_expose_the_absolute_path_for_use_as_source_config(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()

    listing = list_directory("")

    assert listing.entries[0].absolute_path == str(tmp_path / "notes")
    assert listing.entries[0].path == "notes"


def test_lists_a_nested_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "notes" / "2023").mkdir(parents=True)

    listing = list_directory("notes")

    assert listing.path == "notes"
    assert listing.parent == ""
    assert [entry.name for entry in listing.entries] == ["2023"]


def test_hidden_directories_are_excluded(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "notes").mkdir()

    listing = list_directory("")

    assert [entry.name for entry in listing.entries] == ["notes"]


def test_path_traversal_outside_the_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BrowsePathError):
        list_directory("../../etc")


def test_a_path_that_is_not_a_directory_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")

    with pytest.raises(BrowsePathError):
        list_directory("file.txt")


def test_a_nonexistent_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BrowsePathError):
        list_directory("does-not-exist")
