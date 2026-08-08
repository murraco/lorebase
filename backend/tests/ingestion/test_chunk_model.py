import pytest

from ingestion.factories import ChunkFactory
from ingestion.pipeline import process_document
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_prepends_the_heading_path_to_the_content() -> None:
    chunk = ChunkFactory(heading_path="2025-07-21 > Work", content="Finished the refactor.")

    assert chunk.content_with_heading == "2025-07-21 > Work\n\nFinished the refactor."


def test_returns_content_unchanged_when_there_is_no_heading_path() -> None:
    chunk = ChunkFactory(heading_path="", content="Some floating text.")

    assert chunk.content_with_heading == "Some floating text."


def test_leaves_content_itself_untouched() -> None:
    """content stays a faithful slice of the source file — start_line and
    end_line (and therefore citations) are only exact because of that.
    """
    chunk = ChunkFactory(heading_path="A > B", content="body")

    assert chunk.content == "body"


def test_split_sections_keep_their_heading_only_via_the_property() -> None:
    """The regression this property exists for: a section too long for one
    chunk is split at paragraph boundaries, and every piece after the
    first starts below the heading line — so the heading is absent from
    their `content` entirely. Without content_with_heading, those chunks
    get embedded and sent to the LLM with no trace of which day/section
    they belong to.
    """
    paragraph = " ".join(["word"] * 120)
    text = "# 2025-07-21\n\n" + "\n\n".join([paragraph] * 6)
    document = DocumentFactory()
    process_document(document, text=text)

    chunks = list(document.chunks.order_by("index"))
    assert len(chunks) > 1, "expected the long section to be split into several chunks"

    later_chunks = chunks[1:]
    assert all("2025-07-21" not in chunk.content for chunk in later_chunks)
    assert all("2025-07-21" in chunk.content_with_heading for chunk in later_chunks)
