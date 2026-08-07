from collections.abc import Callable

from ingestion.parsers.pdf import extract_pdf_pages


def test_extract_pdf_pages_returns_one_markdown_string_per_page(
    make_pdf_bytes: Callable[[list[tuple[str, str]]], bytes],
) -> None:
    pdf_bytes = make_pdf_bytes(
        [
            ("Page One", "First page body."),
            ("Page Two", "Second page body."),
        ]
    )

    pages = extract_pdf_pages(pdf_bytes)

    assert len(pages) == 2
    assert "Page One" in pages[0]
    assert "First page body." in pages[0]
    assert "Page Two" in pages[1]
    assert "Page Two" not in pages[0]


def test_extract_pdf_pages_infers_a_heading_from_larger_font(
    make_pdf_bytes: Callable[[list[tuple[str, str]]], bytes],
) -> None:
    pdf_bytes = make_pdf_bytes([("A Heading", "Body text.")])

    (page,) = extract_pdf_pages(pdf_bytes)

    assert page.lstrip().startswith("#")
