"""File-based BookRepository that writes metadata.json and book.json as JSON."""
import json
import os
from typing import Optional

import structlog

from src.domain.models import Book
from src.repository.book_repository import BookRepository

logger = structlog.get_logger(__name__)


class FileBookRepository(BookRepository):
    """Persist Book snapshots as metadata.json and book.json on the local filesystem."""

    _METADATA_FILENAME = "metadata.json"
    _BOOK_FILENAME = "book.json"

    def __init__(
        self,
        base_dir: str = "books",
        use_book_id_subdir: bool = True,
    ) -> None:
        self._base_dir = base_dir
        self._use_book_id_subdir = use_book_id_subdir

    def save(self, book: Book) -> None:
        """Persist *book* as the final book snapshot."""
        self._write(book, self._BOOK_FILENAME)

    def load(self, book_id: str) -> Optional[Book]:
        """Load the final book snapshot for *book_id*, or ``None`` if absent."""
        return self._read(book_id, self._BOOK_FILENAME)

    def exists(self, book_id: str) -> bool:
        """Return ``True`` if a non-empty book snapshot exists for *book_id*."""
        file_path = self._path_for(book_id, self._BOOK_FILENAME)
        if not os.path.isfile(file_path):
            return False
        return os.path.getsize(file_path) > 0

    def save_input(self, book: Book) -> None:
        """Persist *book* as the pre-AI metadata snapshot."""
        self._write(book, self._METADATA_FILENAME)

    def load_input(self, book_id: str) -> Optional[Book]:
        """Load the pre-AI metadata snapshot for *book_id*, or ``None`` if absent."""
        return self._read(book_id, self._METADATA_FILENAME)

    def _dir_for(self, book_id: str) -> str:
        if self._use_book_id_subdir:
            return os.path.join(self._base_dir, book_id)
        return self._base_dir

    def _path_for(self, book_id: str, filename: str) -> str:
        return os.path.join(self._dir_for(book_id), filename)

    def _write(self, book: Book, filename: str) -> None:
        dir_path = self._dir_for(book.book_id)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, filename)
        data = json.dumps(book.to_dict(), indent=2, ensure_ascii=False)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(data)
        logger.info(
            "book_saved_to_repository",
            book_id=book.book_id,
            path=file_path,
        )

    def _read(self, book_id: str, filename: str) -> Optional[Book]:
        file_path = self._path_for(book_id, filename)
        if not os.path.isfile(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return None
        data = json.loads(content)
        logger.info(
            "book_loaded_from_repository", book_id=book_id, path=file_path,
        )
        return Book.from_dict(data)
