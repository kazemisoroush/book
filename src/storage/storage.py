"""Abstract storage backend with bytes, text, and local-path access."""
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Literal

LocalPathMode = Literal["r", "w", "rw"]


class StorageBackend(ABC):
    """Key-addressed storage backend for reading, writing, and listing objects."""

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        """Return the object at *key* as bytes."""

    @abstractmethod
    def write_bytes(self, key: str, data: bytes) -> None:
        """Write *data* to *key*, creating any parent containers."""

    @abstractmethod
    def read_text(self, key: str, encoding: str = "utf-8") -> str:
        """Return the object at *key* decoded with *encoding*."""

    @abstractmethod
    def write_text(self, key: str, text: str, encoding: str = "utf-8") -> None:
        """Write *text* to *key* using *encoding*."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if *key* exists and is non-empty."""

    @abstractmethod
    def size(self, key: str) -> int:
        """Return the size in bytes of *key*, or 0 when missing."""

    @abstractmethod
    def delete(self, key: str, missing_ok: bool = True) -> None:
        """Delete *key*; do not error when missing if *missing_ok*."""

    @abstractmethod
    def list_prefix(self, prefix: str) -> list[str]:
        """Return every key whose path starts with *prefix*."""

    @abstractmethod
    def local_path(
        self, key: str, mode: LocalPathMode,
    ) -> AbstractContextManager[Path]:
        """Yield a real filesystem path for *key* for use with subprocess tools.

        For local backends this is the path itself. For remote backends the
        contract is: ``r`` downloads the object before yielding; ``w`` creates
        an empty path and uploads the written file on exit; ``rw`` does both.
        """
