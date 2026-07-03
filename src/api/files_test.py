"""Tests for safe file listing and path resolution."""
import pytest

from src.api.files import (
    PathOutsideBookError,
    list_book_ids,
    list_files,
    resolve_within,
)


def test_list_book_ids_skips_hidden_dirs(tmp_path):
    # Arrange
    (tmp_path / "the_gambler").mkdir()
    (tmp_path / "dracula").mkdir()
    (tmp_path / ".runs").mkdir()
    (tmp_path / "loose.txt").write_text("x")

    # Act
    ids = list_book_ids(tmp_path)

    # Assert
    assert ids == ["dracula", "the_gambler"]


def test_list_files_returns_sorted_relative_paths(tmp_path):
    # Arrange
    book = tmp_path / "book"
    (book / "ai").mkdir(parents=True)
    (book / "book.json").write_text("{}")
    (book / "ai" / "response.json").write_text("{}")

    # Act
    files = list_files(book)

    # Assert
    assert files == ["ai/response.json", "book.json"]


def test_resolve_within_allows_nested_file(tmp_path):
    # Arrange
    book = tmp_path / "book"
    (book / "audio").mkdir(parents=True)

    # Act
    target = resolve_within(book, "audio/ch1.mp3")

    # Assert
    assert target == (book / "audio" / "ch1.mp3").resolve()


def test_resolve_within_rejects_traversal(tmp_path):
    # Arrange
    book = tmp_path / "book"
    book.mkdir()

    # Act / Assert
    with pytest.raises(PathOutsideBookError):
        resolve_within(book, "../secrets.txt")
