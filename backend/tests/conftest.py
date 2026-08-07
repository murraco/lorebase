from collections.abc import Callable

import pymupdf
import pytest


@pytest.fixture
def make_pdf_bytes() -> Callable[[list[tuple[str, str]]], bytes]:
    """Factory fixture: build a minimal real PDF, one page per (heading,
    body) pair, using a font-size step-down so pymupdf4llm infers a
    heading + body paragraph per page — verified against the real library
    output, not assumed.
    """

    def _make(pages: list[tuple[str, str]]) -> bytes:
        doc = pymupdf.open()
        for heading, body in pages:
            page = doc.new_page()
            page.insert_text((72, 72), heading, fontsize=20)
            page.insert_text((72, 110), body, fontsize=11)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    return _make
