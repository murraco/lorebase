from collections.abc import Callable
from dataclasses import dataclass

from ingestion.chunking.base import ChunkData, Chunker
from ingestion.chunking.tokens import count_tokens
from ingestion.parsers.base import ParsedSection

DEFAULT_MIN_TOKENS = 40
DEFAULT_MAX_TOKENS = 400

TokenCounter = Callable[[int, int], int]


@dataclass
class _Piece:
    heading_path: list[str]
    start_line: int
    end_line: int


class HeadingChunker(Chunker):
    """Starts from one piece per heading (`ParsedSection`), then:
    - splits any piece whose token count exceeds `max_tokens`, at
      paragraph boundaries only (never mid-paragraph);
    - merges consecutive pieces while the running piece is still under
      `min_tokens`, so a lone one-line subsection doesn't become its own
      near-empty chunk.
    """

    def __init__(
        self, min_tokens: int = DEFAULT_MIN_TOKENS, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> None:
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

    def chunk(self, text: str, sections: list[ParsedSection]) -> list[ChunkData]:
        all_lines = text.splitlines()

        def content_for(start_line: int, end_line: int) -> str:
            return "\n".join(all_lines[start_line - 1 : end_line])

        def tokens_for(start_line: int, end_line: int) -> int:
            return count_tokens(content_for(start_line, end_line))

        pieces = [
            piece
            for section in sections
            for piece in self._split_if_too_long(section, all_lines, tokens_for)
        ]
        merged = self._merge_short_pieces(pieces, tokens_for)

        return [
            ChunkData(
                heading_path=piece.heading_path,
                content=content_for(piece.start_line, piece.end_line),
                start_line=piece.start_line,
                end_line=piece.end_line,
                token_count=tokens_for(piece.start_line, piece.end_line),
            )
            for piece in merged
        ]

    def _split_if_too_long(
        self, section: ParsedSection, all_lines: list[str], tokens_for: TokenCounter
    ) -> list[_Piece]:
        if tokens_for(section.start_line, section.end_line) <= self.max_tokens:
            return [_Piece(section.heading_path, section.start_line, section.end_line)]

        # Paragraph slots gaplessly partition the section (no line belongs
        # to none or two of them), so packing consecutive slots together
        # never loses or double-counts a line.
        slots = self._paragraph_slots(section, all_lines)
        pieces: list[_Piece] = []
        group_start, group_end = slots[0]
        for slot_start, slot_end in slots[1:]:
            if tokens_for(group_start, slot_end) > self.max_tokens:
                pieces.append(_Piece(section.heading_path, group_start, group_end))
                group_start, group_end = slot_start, slot_end
            else:
                group_end = slot_end
        pieces.append(_Piece(section.heading_path, group_start, group_end))
        return pieces

    @staticmethod
    def _paragraph_slots(section: ParsedSection, all_lines: list[str]) -> list[tuple[int, int]]:
        starts: list[int] = []
        for line_no in range(section.start_line, section.end_line + 1):
            line = all_lines[line_no - 1]
            if not line.strip():
                continue
            prev_line = all_lines[line_no - 2] if line_no > section.start_line else None
            if line_no == section.start_line or prev_line is None or not prev_line.strip():
                starts.append(line_no)
        if not starts:
            starts = [section.start_line]

        slots: list[tuple[int, int]] = []
        for i, start in enumerate(starts):
            end = starts[i + 1] - 1 if i + 1 < len(starts) else section.end_line
            slots.append((start, end))
        return slots

    def _merge_short_pieces(self, pieces: list[_Piece], tokens_for: TokenCounter) -> list[_Piece]:
        if not pieces:
            return []
        merged: list[_Piece] = []
        buffer = pieces[0]
        for piece in pieces[1:]:
            buffer_tokens = tokens_for(buffer.start_line, buffer.end_line)
            combined_tokens = tokens_for(buffer.start_line, piece.end_line)
            if buffer_tokens < self.min_tokens and combined_tokens <= self.max_tokens:
                buffer = _Piece(buffer.heading_path, buffer.start_line, piece.end_line)
            else:
                merged.append(buffer)
                buffer = piece
        merged.append(buffer)
        return merged
