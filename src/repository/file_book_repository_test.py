"""Unit tests for FileBookRepository."""
import os
import tempfile

from src.domain.beat import Beat, BeatType
from src.domain.character import Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
)
from src.repository.file_book_repository import FileBookRepository


def _make_book() -> Book:
    """Build a realistic Book with beats, characters, and metadata."""
    registry = CharacterRegistry(characters=[make_default_narrator("book")])
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


_BOOK_ID = "pride_and_prejudice:jane_austen"


class TestFileBookRepositorySaveAndLoad:
    """save() then load() round-trips a Book losslessly."""

    def test_save_then_load_round_trips_a_book(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            book = _make_book()

            # Act
            repo.save(book)
            loaded = repo.load(_BOOK_ID)

            # Assert
            assert loaded is not None
            assert loaded.to_dict() == book.to_dict()


class TestFileBookRepositoryLoadMissing:
    """load() returns None when no file exists."""

    def test_load_returns_none_when_no_file_exists(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)

            # Act / Assert
            assert repo.load("nonexistent-book") is None
            assert repo.load_input("nonexistent-book") is None


class TestFileBookRepositoryExists:
    """exists() reflects the output snapshot, not the input snapshot."""

    def test_exists_returns_false_before_save(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)

            # Act / Assert
            assert repo.exists("no-such-book") is False

    def test_exists_returns_true_after_save(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            book = _make_book()

            # Act
            repo.save(book)

            # Assert
            assert repo.exists(_BOOK_ID) is True

    def test_exists_ignores_input_only_snapshot(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            repo.save_input(_make_book())

            # Act / Assert
            assert repo.exists(_BOOK_ID) is False


class TestFileBookRepositoryInputSnapshot:
    """save_input() / load_input() round-trip the pre-AI snapshot."""

    def test_save_input_then_load_input_round_trips(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            book = _make_book()

            # Act
            repo.save_input(book)
            loaded = repo.load_input(_BOOK_ID)

            # Assert
            assert loaded is not None
            assert loaded.to_dict() == book.to_dict()

    def test_input_and_output_snapshots_are_independent(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)
            book = _make_book()
            repo.save_input(book)

            # Act / Assert — saving input doesn't materialize an output
            assert repo.load(_BOOK_ID) is None


class TestFileBookRepositoryFilesystemLayout:
    """Files land at the documented paths."""

    def test_save_writes_output_json_under_book_id_subdir(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)

            # Act
            repo.save(_make_book())

            # Assert
            assert os.path.isfile(os.path.join(tmp_dir, _BOOK_ID, "output.json"))

    def test_save_input_writes_input_json_under_book_id_subdir(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir)

            # Act
            repo.save_input(_make_book())

            # Assert
            assert os.path.isfile(os.path.join(tmp_dir, _BOOK_ID, "input.json"))

    def test_use_book_id_subdir_false_writes_directly_under_base_dir(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir, use_book_id_subdir=False)

            # Act
            repo.save(_make_book())
            repo.save_input(_make_book())

            # Assert
            assert os.path.isfile(os.path.join(tmp_dir, "output.json"))
            assert os.path.isfile(os.path.join(tmp_dir, "input.json"))

    def test_use_book_id_subdir_false_round_trip(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = FileBookRepository(base_dir=tmp_dir, use_book_id_subdir=False)
            book = _make_book()

            # Act
            repo.save(book)
            repo.save_input(book)

            # Assert
            assert repo.load("any-book-id-is-ignored") is not None
            assert repo.load_input("any-book-id-is-ignored") is not None
