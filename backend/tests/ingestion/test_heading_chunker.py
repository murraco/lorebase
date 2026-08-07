from ingestion.chunking.heading import HeadingChunker
from ingestion.chunking.tokens import count_tokens
from ingestion.parsers.base import ParsedSection


def test_chunk_content_matches_the_source_lines_for_its_range() -> None:
    text = "line1\nline2\nline3\nline4"
    section = ParsedSection([], 1, 4)
    chunker = HeadingChunker(min_tokens=1000, max_tokens=1000)

    chunks = chunker.chunk(text, [section])

    assert len(chunks) == 1
    assert chunks[0].content == text


def test_short_sections_merge_forward() -> None:
    """The worked example: a short intro and a short trailing section
    around one normal-sized section. S1 merges into S2 (buffer still short
    after S1 alone); S3 is last, so nothing merges into it (see the
    'merge only merges forward' entry in the roadmap's known-debt list).
    """
    text = "\n".join(
        [
            "# RAG notes",  # 1
            "",  # 2
            "Some intro text about retrieval augmented generation.",  # 3
            "",  # 4
            "## Hybrid search",  # 5
            "",  # 6
            "Hybrid search combines BM25 (lexical, keyword-based) with dense vector",  # 7
            "similarity search. BM25 catches exact terms and rare identifiers that",  # 8
            "embeddings often miss, while dense search catches paraphrases and",  # 9
            "semantic similarity that keyword matching misses entirely. Combining both",  # 10
            "with something like Reciprocal Rank Fusion gives better results than",  # 11
            "either alone.",  # 12
            "",  # 13
            "## Reranking",  # 14
            "",  # 15
            "A second pass over the top candidates.",  # 16
        ]
    )
    sections = [
        ParsedSection(["RAG notes"], 1, 4),
        ParsedSection(["RAG notes", "Hybrid search"], 5, 13),
        ParsedSection(["RAG notes", "Reranking"], 14, 16),
    ]
    chunker = HeadingChunker(min_tokens=40, max_tokens=400)

    chunks = chunker.chunk(text, sections)

    assert len(chunks) == 2
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 13)
    assert chunks[0].heading_path == ["RAG notes"]
    assert (chunks[1].start_line, chunks[1].end_line) == (14, 16)
    assert chunks[1].heading_path == ["RAG notes", "Reranking"]


def test_single_paragraph_exceeding_max_tokens_is_not_split_mid_paragraph() -> None:
    text = "One giant paragraph with several words and no blank line separators."
    section = ParsedSection([], 1, 1)
    chunker = HeadingChunker(min_tokens=0, max_tokens=1)

    chunks = chunker.chunk(text, [section])

    assert len(chunks) == 1
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 1)


def test_long_section_split_never_loses_or_duplicates_lines() -> None:
    """The property that matters most: however a section gets split, the
    pieces must gaplessly and non-overlappingly cover the whole section —
    citations depend on this being exactly right.
    """
    text = "\n".join(
        [
            "## Big section",  # 1
            "",  # 2
            "Paragraph one has some words in it here today.",  # 3
            "",  # 4
            "Paragraph two also has a handful of words present.",  # 5
            "",  # 6
            "Paragraph three rounds things out with more words.",  # 7
        ]
    )
    section = ParsedSection(["Big section"], 1, 7)
    para_one = count_tokens("## Big section\n\nParagraph one has some words in it here today.")
    # Small enough that the whole section doesn't fit, but roughly one
    # paragraph's worth does -> forces at least one split.
    chunker = HeadingChunker(min_tokens=0, max_tokens=para_one)

    chunks = chunker.chunk(text, [section])

    assert len(chunks) > 1
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 7
    for current, following in zip(chunks, chunks[1:], strict=False):
        assert following.start_line == current.end_line + 1


def test_empty_sections_produce_no_chunks() -> None:
    chunker = HeadingChunker()

    assert chunker.chunk("", []) == []
