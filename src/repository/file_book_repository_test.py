"""Unit tests for FileBookRepository."""
import os
import tempfile

from src.domain.models import (
    Beat,
    BeatType,
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Character,
    CharacterRegistry,
    Section,
)
from src.repository.file_book_repository import FileBookRepository


def _make_book() -> Book:
    """Build a realistic Book with segments, characters, and metadata."""
    registry = CharacterRegistry.with_default_narrator()
    registry.upsert(
        Character(
            character_id="elizabeth",
            name="Elizabeth Bennet",
            sex="female",
            age="young_adult",
            description="witty and intelligent young woman",
        )
    )

    section = Section(
        text="It is a truth universally acknowledged.",
        beats=[
            Beat(
                text="It is a truth universally acknowledged.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
            ),
        ],
        section_type=None,
    )
    chapter = Chapter(number=1, title="Chapter I", sections=[section])
    content = BookContent(chapters=[chapter])
    metadata = BookMetadata(
        title="Pride and Prejudice",
        author="Jane Austen",
        releaseDate="1998-06-01",
        language="English",
        originalPublication="1813",
        credits="Someone",
    )
    return Book(metadata=metadata, content=content, character_registry=registry)


class TestFileBookRepositorySaveAndLoad:
    """save() then load() round-trips a Book losslessly."""

    def test_save_then_load_round_trips_a_book(self) -> None:
        """A book saved to the repository can be loaded back identically."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            book = _make_book()
            book_id = "Pride and Prejudice - Jane Austen"

            # Act
            repo.save(book, book_id)
            loaded = repo.load(book_id)

            # Assert
            assert loaded is not None
            assert loaded.to_dict() == book.to_dict()


class TestFileBookRepositoryLoadMissing:
    """load() returns None when no file exists."""

    def test_load_returns_none_when_no_file_exists(self) -> None:
        """Loading a non-existent book_id returns None."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)

            # Act
            result = repo.load("nonexistent-book")

            # Assert
            assert result is None


class TestFileBookRepositoryExists:
    """exists() returns True after save(), False before."""

    def test_exists_returns_false_before_save(self) -> None:
        """exists() returns False for a book_id that has never been saved."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)

            # Act / Assert
            assert repo.exists("no-such-book") is False

    def test_exists_returns_true_after_save(self) -> None:
        """exists() returns True after a book has been saved."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            book = _make_book()
            book_id = "Pride and Prejudice - Jane Austen"

            # Act
            repo.save(book, book_id)

            # Assert
            assert repo.exists(book_id) is True


class TestFileBookRepositoryFilesystemLayout:
    """The repository writes to {base_dir}/{book_id}/book.json."""

    def test_save_creates_book_json_at_expected_path(self) -> None:
        """After save, the file exists at {base_dir}/{book_id}/book.json."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            book = _make_book()
            book_id = "Pride and Prejudice - Jane Austen"

            # Act
            repo.save(book, book_id)

            # Assert
            expected_path = os.path.join(tmp_dir, book_id, "book.json")
            assert os.path.isfile(expected_path)
