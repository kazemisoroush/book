"""File-based implementation of BookRepository.

Persists a ``Book`` as JSON to ``{base_dir}/{book_id}/book.json``.
The directory structure is human-browsable (``ls books/``).
"""
import json
import os
from typing import Optional

import structlog

from src.domain.models import Book
from src.repository.book_repository import BookRepository

logger = structlog.get_logger(__name__)


class FileBookRepository(BookRepository):
    """Persist and load ``Book`` instances as JSON files on the local filesystem.

    Storage layout::

        {base_dir}/
          {book_id}/
            book.json

    ``base_dir`` defaults to ``./books/`` but is configurable via the
    constructor.
    """

    _FILENAME = "book.json"

    def __init__(self, base_dir: str = "books") -> None:
        self._base_dir = base_dir

    def save(self, book: Book, book_id: str) -> None:
        """Persist *book* as JSON under ``{base_dir}/{book_id}/book.json``."""
        dir_path = os.path.join(self._base_dir, book_id)
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, self._FILENAME)
        data = json.dumps(book.to_dict(), indent=2, ensure_ascii=False)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(data)

        logger.info("book_saved_to_repository", book_id=book_id, path=file_path)

    def load(self, book_id: str) -> Optional[Book]:
        """Load a ``Book`` from ``{base_dir}/{book_id}/book.json``.

        Returns ``None`` when the file does not exist or is empty.
        """
        file_path = os.path.join(self._base_dir, book_id, self._FILENAME)

        if not os.path.isfile(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            return None

        data = json.loads(content)
        logger.info("book_loaded_from_repository", book_id=book_id, path=file_path)
        return Book.from_dict(data)

    def exists(self, book_id: str) -> bool:
        """Return ``True`` if a non-empty ``book.json`` exists for *book_id*."""
        file_path = os.path.join(self._base_dir, book_id, self._FILENAME)
        if not os.path.isfile(file_path):
            return False
        return os.path.getsize(file_path) > 0
