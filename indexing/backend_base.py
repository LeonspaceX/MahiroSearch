from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, AsyncIterator


@dataclass
class FileEntry:
    path: Path
    name: str
    size: int           # bytes
    modified_at: float  # Unix timestamp
    extension: str


class AbstractFileIndexBackend(ABC):
    """Provides an iterator over all indexed file paths on the system."""

    @abstractmethod
    def iter_all_files(
        self,
        exclusion_rules: "ExclusionRules",
        include_paths: list[Path] | None = None,
    ) -> Iterator[FileEntry]:
        """
        Yield every non-excluded file entry.
        If include_paths is non-empty, only those directories are scanned.
        """
        ...

    @abstractmethod
    async def watch_changes(
        self,
        exclusion_rules: "ExclusionRules",
        include_paths: list[Path] | None = None,
    ) -> AsyncIterator[tuple[str, "FileEntry | Path"]]:
        """
        Yield (event_type, payload) tuples.
        event_type: "created" | "modified" | "deleted"
        payload: FileEntry for created/modified, Path for deleted.
        """
        ...

    @abstractmethod
    def get_all_roots(self) -> list[Path]:
        """Return list of top-level scan roots (drive letters or mount points)."""
        ...
