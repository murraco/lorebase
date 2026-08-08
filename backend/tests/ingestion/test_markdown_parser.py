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


def test_extra_boundary_pattern_splits_headingless_content_into_sections() -> None:
    # Real shape of the bug this exists for: a flat journal with no
    # Markdown headings at all, entries separated by a bare date line.
    text = "\n".join(
        [
            "2023-05-15 12:16:25-0300",  # 1
            "did some work",  # 2
            "",  # 3
            "2023-05-16 08:31:28-0300",  # 4
            "did other work",  # 5
        ]
    )
    dated_parser = MarkdownParser(extra_boundary_pattern=r"^\d{4}-\d{2}-\d{2}.*$")

    sections = dated_parser.parse(text)

    assert [s.heading_path for s in sections] == [
        ["2023-05-15 12:16:25-0300"],
        ["2023-05-16 08:31:28-0300"],
    ]
    assert [(s.start_line, s.end_line) for s in sections] == [(1, 3), (4, 5)]


def test_extra_boundary_pattern_uses_a_named_label_group_when_present() -> None:
    text = "2023-05-15 12:16:25-0300 (standup)\nbody"
    dated_parser = MarkdownParser(extra_boundary_pattern=r"^(?P<label>\d{4}-\d{2}-\d{2}).*$")

    sections = dated_parser.parse(text)

    assert sections[0].heading_path == ["2023-05-15"]


def test_extra_boundary_pattern_does_not_affect_ordinary_markdown() -> None:
    # No pattern configured -> identical behavior to plain ATX parsing.
    text = "# Title\nbody"

    assert MarkdownParser(extra_boundary_pattern=None).parse(text) == parser.parse(text)


def test_atx_headings_take_precedence_over_the_extra_boundary_pattern() -> None:
    text = "# 2023-05-15 heading\nbody"
    dated_parser = MarkdownParser(extra_boundary_pattern=r"^\d{4}-\d{2}-\d{2}.*$")

    sections = dated_parser.parse(text)

    assert sections[0].heading_path == ["2023-05-15 heading"]


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
