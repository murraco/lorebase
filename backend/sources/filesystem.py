from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


class BrowsePathError(Exception):
    """A requested path escapes the allowed root, or isn't a directory."""


@dataclass
class DirectoryEntry:
    name: str
    path: str  # relative to the browse root, POSIX-style
    absolute_path: str  # what actually goes into Source.config["path"]


@dataclass
class DirectoryListing:
    path: str  # relative path currently being browsed ("" for the root)
    parent: str | None  # None only at the root itself
    absolute_path: str
    entries: list[DirectoryEntry]


def browse_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def list_directory(relative_path: str) -> DirectoryListing:
    """Lists subdirectories only — this exists for the "add a local
    folder source" picker, which needs a directory, never a specific
    file. Confined to `browse_root()`: a `path` like "../../etc" resolves
    outside it and is rejected, the same way a path traversal attempt
    would be anywhere else user input turns into a filesystem path.
    """
    root = browse_root()
    target = (root / relative_path).resolve()

    if target != root and root not in target.parents:
        raise BrowsePathError(f"{relative_path!r} is outside the allowed root")
    if not target.is_dir():
        raise BrowsePathError(f"{relative_path!r} is not a directory")

    entries = sorted(
        (
            DirectoryEntry(
                name=child.name,
                path=child.relative_to(root).as_posix(),
                absolute_path=str(child),
            )
            for child in target.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ),
        key=lambda entry: entry.name.lower(),
    )

    relative = "" if target == root else target.relative_to(root).as_posix()
    parent = None if target == root else _posix_relative(target.parent, root)

    return DirectoryListing(
        path=relative, parent=parent, absolute_path=str(target), entries=entries
    )


def _posix_relative(path: Path, root: Path) -> str:
    return "" if path == root else path.relative_to(root).as_posix()
