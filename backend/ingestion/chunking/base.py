from abc import ABC, abstractmethod
from dataclasses import dataclass

from ingestion.parsers.base import ParsedSection


@dataclass
class ChunkData:
    heading_path: list[str]
    content: str
    start_line: int
    end_line: int
    token_count: int


class Chunker(ABC):
    """Strategy-specific: decides how ParsedSections become actual chunks
    (merge short ones, split long ones, or something else entirely).
    Interchangeable without touching the Parser or anything downstream.
    """

    @abstractmethod
    def chunk(self, text: str, sections: list[ParsedSection]) -> list[ChunkData]:
        ...
