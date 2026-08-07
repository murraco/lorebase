import pymupdf
import pymupdf4llm


def extract_pdf_pages(binary: bytes) -> list[str]:
    """One Markdown string per page, in page order (page N of the return
    value is page N+1 of the PDF — pymupdf4llm's own page_number is
    1-indexed and matches list order, verified against a real PDF).

    Not a `Parser`: a Parser turns text into `ParsedSection`s, but a PDF is
    binary and produces *multiple* per-page texts, not one. The per-page
    Markdown this returns still goes through the same `MarkdownParser` +
    `HeadingChunker` as any other note — see ingestion/pipeline.py.
    """
    doc = pymupdf.open(stream=binary, filetype="pdf")
    try:
        pages = pymupdf4llm.to_markdown(doc, page_chunks=True)
    finally:
        doc.close()
    return [page["text"] for page in pages]
