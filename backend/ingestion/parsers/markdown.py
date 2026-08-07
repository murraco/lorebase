import re

from ingestion.parsers.base import ParsedSection, Parser

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^(```|~~~)")


class MarkdownParser(Parser):
    """ATX headings only (`#` ... `######`), not Setext (`===`/`---`
    underlines) — ATX is what every note-taking tool and static site
    generator actually produces. `#` inside fenced code blocks is ignored,
    so a bash comment in a code snippet doesn't get mistaken for a heading.
    """

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

            match = _HEADING_RE.match(line)
            if match is None:
                continue

            flush(line_no - 1)
            level = len(match.group(1))
            # Siblings replace each other rather than stacking: a new level-2
            # heading drops any level-3+ headings we'd descended into, but
            # keeps the level-1 ancestor.
            heading_stack = heading_stack[: level - 1] + [match.group(2).strip()]
            current_start = line_no

        flush(len(lines))
        return sections
