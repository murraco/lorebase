from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParsedSection:
    """A contiguous span of the source text living under one heading (or,
    for text before the first heading, under none). Only line numbers are
    stored, not a copy of the text — the chunker slices the original text
    on demand. That's deliberate: citations depend on exact line numbers,
    and reconstructing text from copied/concatenated fragments elsewhere is
    exactly how off-by-one line bugs creep in. One source of truth only.
    """

    heading_path: list[str]
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive


class Parser(ABC):
    """Format-specific: knows how to find heading structure in one kind of
    document (Markdown today, PDF-via-Markdown in Etapa 8). Never decides
    chunk sizes — that's the Chunker's job.
    """

    @abstractmethod
    def parse(self, text: str) -> list[ParsedSection]:
        """Split text into sections by heading hierarchy, in document order."""
