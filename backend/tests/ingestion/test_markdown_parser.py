from ingestion.parsers.markdown import MarkdownParser

parser = MarkdownParser()


def test_empty_text_produces_no_sections() -> None:
    assert parser.parse("") == []


def test_text_without_any_heading_is_one_section() -> None:
    sections = parser.parse("just some text\nacross two lines")

    assert len(sections) == 1
    assert sections[0].heading_path == []
    assert (sections[0].start_line, sections[0].end_line) == (1, 2)


def test_text_starting_with_a_heading_has_no_empty_preamble() -> None:
    sections = parser.parse("# Title\nbody")

    assert len(sections) == 1
    assert sections[0].heading_path == ["Title"]


def test_nested_headings_build_a_path() -> None:
    text = "\n".join(
        [
            "# A",  # 1
            "intro",  # 2
            "## B",  # 3
            "text",  # 4
            "### C",  # 5
            "text",  # 6
            "## D",  # 7
            "text",  # 8
        ]
    )

    sections = parser.parse(text)

    assert [s.heading_path for s in sections] == [
        ["A"],
        ["A", "B"],
        ["A", "B", "C"],
        ["A", "D"],  # sibling of B: drops C, keeps A
    ]
    assert [(s.start_line, s.end_line) for s in sections] == [
        (1, 2),
        (3, 4),
        (5, 6),
        (7, 8),
    ]


def test_hash_inside_fenced_code_block_is_not_a_heading() -> None:
    text = "\n".join(
        [
            "# Real heading",  # 1
            "```bash",  # 2
            "# this is a shell comment, not a heading",  # 3
            "```",  # 4
            "after the fence",  # 5
        ]
    )

    sections = parser.parse(text)

    assert len(sections) == 1
    assert sections[0].heading_path == ["Real heading"]
    assert (sections[0].start_line, sections[0].end_line) == (1, 5)
