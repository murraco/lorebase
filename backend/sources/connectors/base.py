from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


class ConnectorConfigError(Exception):
    """Raised by validate_config() when a Source's config is invalid."""


class ConnectorConnectionError(Exception):
    """Raised by test_connection() when the source can't be reached."""


@dataclass
class RawDocument:
    """What a connector hands back for one document, before it becomes a
    `Document` row. `content` and `binary` are mutually exclusive: text
    formats (Markdown) set `content`, binary formats (PDF) set `binary`
    instead.

    `content_hash` is an opaque, connector-defined fingerprint: it only has
    to change if and only if the document's content changed. Connectors are
    free to derive it however makes sense for their source — a sha256 of
    the raw bytes for local files, a git blob SHA for the GitHub connector —
    reconciliation only ever compares it as a string, never how it was made.
    """

    external_id: str
    path: str
    title: str
    content_hash: str
    content: str | None = None
    binary: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Connector(ABC):
    """Contract every source type (local folder, GitHub, ...) must
    implement. Everything downstream — reconciliation, chunking,
    embeddings — only ever talks to this interface, never to a concrete
    connector directly.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    def validate_config(self) -> None:
        """Raise ConnectorConfigError if self.config is missing or malformed."""

    @abstractmethod
    def test_connection(self) -> None:
        """Raise ConnectorConnectionError if the source isn't reachable."""

    @abstractmethod
    def fetch_documents(self) -> Iterator[RawDocument]:
        """Yield every document currently present at the source."""
