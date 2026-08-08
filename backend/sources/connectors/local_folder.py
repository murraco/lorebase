import hashlib
import logging
from collections.abc import Iterator
from pathlib import Path

import frontmatter
from django.conf import settings

from sources.connectors.base import (
    Connector,
    ConnectorConfigError,
    ConnectorConnectionError,
    RawDocument,
)
from sources.connectors.registry import register_connector

logger = logging.getLogger(__name__)


@register_connector("local_folder")
class LocalFolderConnector(Connector):
    """Reads Markdown notes, plain text files, and PDFs from a local
    directory, recursively. The path relative to the configured root is
    used as both `external_id` and `path`, so identity survives even if
    the whole folder is later moved to a different absolute location.
    """

    def validate_config(self) -> None:
        path = self.config.get("path")
        if not path or not isinstance(path, str):
            raise ConnectorConfigError("config must include a non-empty 'path' string")

    def test_connection(self) -> None:
        root = self._root()
        if not root.is_dir():
            raise ConnectorConnectionError(f"{root} is not a directory")

    def fetch_documents(self) -> Iterator[RawDocument]:
        root = self._root()
        file_paths = sorted([*root.rglob("*.md"), *root.rglob("*.txt"), *root.rglob("*.pdf")])
        for file_path in file_paths:
            size = file_path.stat().st_size
            if size > settings.MAX_DOCUMENT_SIZE_BYTES:
                logger.warning(
                    "Skipping %s: %d bytes exceeds MAX_DOCUMENT_SIZE_BYTES (%d)",
                    file_path,
                    size,
                    settings.MAX_DOCUMENT_SIZE_BYTES,
                )
                continue

            if file_path.suffix == ".pdf":
                yield self._read_pdf(file_path, root)
            else:
                yield self._read_text_file(file_path, root)

    def _read_text_file(self, file_path: Path, root: Path) -> RawDocument:
        # Markdown and plain text share this path: front matter parsing is
        # a harmless no-op on a .txt file with no `---` block (it just
        # returns empty metadata and the text unchanged), and a .txt file
        # with no headings chunks exactly like a headingless .md file
        # already does — nothing downstream needs to know which one it was.
        relative_path = file_path.relative_to(root).as_posix()
        raw_bytes = file_path.read_bytes()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        full_text = raw_bytes.decode("utf-8")
        post = frontmatter.loads(full_text)
        # YAML front matter can hold any type; metadata.get() is typed as
        # `object`, so coerce explicitly rather than trust the YAML author.
        raw_title = post.metadata.get("title")
        title = str(raw_title) if raw_title else file_path.stem

        return RawDocument(
            external_id=relative_path,
            path=relative_path,
            title=title,
            content_hash=content_hash,
            # The FULL file text, front matter included — not post.content
            # (front matter stripped). Chunk line numbers must match the
            # real file on disk for citations to be verifiable; stripping
            # the front matter here would shift every line number by
            # however many lines it occupied.
            content=full_text,
            metadata=post.metadata,
        )

    def _read_pdf(self, file_path: Path, root: Path) -> RawDocument:
        relative_path = file_path.relative_to(root).as_posix()
        raw_bytes = file_path.read_bytes()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        return RawDocument(
            external_id=relative_path,
            path=relative_path,
            title=file_path.stem,
            content_hash=content_hash,
            binary=raw_bytes,
        )

    def _root(self) -> Path:
        return Path(self.config["path"])
