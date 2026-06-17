"""Storage-backed BookRepository that writes metadata.json and book.json as JSON."""
import json
from typing import Optional

import structlog

from src.domain.models import Book, Chapter
from src.repository.book_repository import BookRepository
from src.storage.local_storage import LocalStorage
from src.storage.storage import Storage

logger = structlog.get_logger(__name__)


class FileBookRepository(BookRepository):
    """Persist Book snapshots as metadata.json and book.json via a Storage backend."""

    _METADATA_FILENAME = "metadata.json"
    _BOOK_FILENAME = "book.json"

    def __init__(
        self,
        base_dir: Optional[str] = None,
        use_book_id_subdir: bool = True,
        storage: Optional[Storage] = None,
    ) -> None:
        if storage is None:
            storage = LocalStorage(base_dir if base_dir is not None else "books")
        self._storage = storage
        self._use_book_id_subdir = use_book_id_subdir

    def save(self, book: Book) -> None:
        """Persist *book* as the final book snapshot."""
        self._write(book, self._BOOK_FILENAME)

    def save_chapter(self, book: Book, chapter: Chapter) -> None:
        """Re-persist the whole *book*; the JSON snapshot is per-book, not per-chapter."""
        del chapter
        self.save(book)

    def load(self, book_id: str) -> Optional[Book]:
        """Load the final book snapshot for *book_id*, or ``None`` if absent."""
        return self._read(book_id, self._BOOK_FILENAME)

    def exists(self, book_id: str) -> bool:
        """Return ``True`` if a non-empty book snapshot exists for *book_id*."""
        return self._storage.exists(self._key_for(book_id, self._BOOK_FILENAME))

    def save_input(self, book: Book) -> None:
        """Persist *book* as the pre-AI metadata snapshot."""
        self._write(book, self._METADATA_FILENAME)

    def load_input(self, book_id: str) -> Optional[Book]:
        """Load the pre-AI metadata snapshot for *book_id*, or ``None`` if absent."""
        return self._read(book_id, self._METADATA_FILENAME)

    def _key_for(self, book_id: str, filename: str) -> str:
        if self._use_book_id_subdir:
            return f"{book_id}/{filename}"
        return filename

    def _write(self, book: Book, filename: str) -> None:
        key = self._key_for(book.book_id, filename)
        data = json.dumps(book.to_dict(), indent=2, ensure_ascii=False)
        self._storage.write_text(key, data)
        logger.info("book_saved_to_repository", book_id=book.book_id, key=key)

    def _read(self, book_id: str, filename: str) -> Optional[Book]:
        key = self._key_for(book_id, filename)
        if not self._storage.exists(key):
            return None
        content = self._storage.read_text(key)
        if not content.strip():
            return None
        data = json.loads(content)
        logger.info("book_loaded_from_repository", book_id=book_id, key=key)
        return Book.from_dict(data)
