import re

from ingestion.parsers.base import ParsedSection, Parser

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^(```|~~~)")


class MarkdownParser(Parser):
    """ATX headings only (`#` ... `######`), not Setext (`===`/`---`
    underlines) — ATX is what every note-taking tool and static site
    generator actually produces. `#` inside fenced code blocks is ignored,
    so a bash comment in a code snippet doesn't get mistaken for a heading.

    `extra_boundary_pattern` is an escape hatch for content that has no
    Markdown headings at all but still has real structure — a flat journal
    file using a bare timestamp line to separate entries, for example.
    Without it, a file like that parses as a single giant headingless
    section: the chunker still splits it (by token budget), but blindly,
    with no anchor for what any given chunk is "about". A configured
    pattern turns whatever line format the source actually uses into a
    section boundary, the same way an ATX heading is one — same downstream
    effect (heading_path ends up in the chunk's content, so it's part of
    what gets embedded, lexically searched, and shown to the LLM), without
    hardcoding any particular date format into the parser itself. Boundary
    matches don't nest under a `heading_stack` — a flat log has no
    hierarchy — they just replace whatever heading path was current.
    """

    def __init__(self, extra_boundary_pattern: str | None = None) -> None:
        self._extra_boundary_re = (
            re.compile(extra_boundary_pattern) if extra_boundary_pattern else None
        )

    def parse(self, text: str) -> list[ParsedSection]:
        lines = text.splitlines()
        if not lines:
            return []

        sections: list[ParsedSection] = []
        heading_stack: list[str] = []
        current_start = 1
        in_fence = False

        def flush(end_line: int) -> None:
            if end_line >= current_start:
                sections.append(ParsedSection(list(heading_stack), current_start, end_line))

        for line_no, line in enumerate(lines, start=1):
            if _FENCE_RE.match(line.strip()):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            heading_match = _HEADING_RE.match(line)
            if heading_match is not None:
                flush(line_no - 1)
                level = len(heading_match.group(1))
                # Siblings replace each other rather than stacking: a new
                # level-2 heading drops any level-3+ headings we'd
                # descended into, but keeps the level-1 ancestor.
                heading_stack = heading_stack[: level - 1] + [heading_match.group(2).strip()]
                current_start = line_no
                continue

            boundary_match = (
                self._extra_boundary_re.match(line) if self._extra_boundary_re else None
            )
            if boundary_match is not None:
                flush(line_no - 1)
                label = (
                    boundary_match.group("label")
                    if "label" in boundary_match.re.groupindex
                    else boundary_match.group(0)
                )
                heading_stack = [label.strip()]
                current_start = line_no

        flush(len(lines))
        return sections
