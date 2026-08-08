from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ingestion.parsers.base import ParsedSection


@dataclass
class ChunkData:
    heading_path: list[str]
    content: str
    start_line: int
    end_line: int
    token_count: int
    # Empty for plain text sources. Callers orchestrating something the
    # Chunker itself doesn't know about — e.g. which PDF page a chunk came
    # from — can tag it in after the fact without the Chunker needing any
    # format-specific awareness.
    metadata: dict[str, Any] = field(default_factory=dict)


class Chunker(ABC):
    """Strategy-specific: decides how ParsedSections become actual chunks
    (merge short ones, split long ones, or something else entirely).
    Interchangeable without touching the Parser or anything downstream.
    """

    @abstractmethod
    def chunk(self, text: str, sections: list[ParsedSection]) -> list[ChunkData]: ...
