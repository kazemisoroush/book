"""Unit tests for LocalFileStorage."""
from pathlib import Path

import pytest

from src.storage.local_file_storage import LocalStorageBackend


class TestReadWriteBytes:
    """write_bytes / read_bytes round-trip arbitrary bytes."""

    def test_round_trip(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act
        storage.write_bytes("nested/dir/file.mp3", b"\x00\x01\x02")

        # Assert
        assert (tmp_path / "nested" / "dir" / "file.mp3").read_bytes() == b"\x00\x01\x02"
        assert storage.read_bytes("nested/dir/file.mp3") == b"\x00\x01\x02"

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act
        storage.write_bytes("a/b/c/d.bin", b"x")

        # Assert
        assert (tmp_path / "a" / "b" / "c" / "d.bin").is_file()


class TestReadWriteText:
    """write_text / read_text round-trip UTF-8 strings."""

    def test_round_trip_unicode(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act
        storage.write_text("notes.md", "héllo — world")

        # Assert
        assert storage.read_text("notes.md") == "héllo — world"


class TestExists:
    """exists() reports True only when the key is a non-empty file."""

    def test_missing_returns_false(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act / Assert
        assert storage.exists("nope.json") is False

    def test_present_non_empty_returns_true(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)
        storage.write_text("greet.txt", "hi")

        # Act / Assert
        assert storage.exists("greet.txt") is True

    def test_empty_file_returns_false(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)
        storage.write_bytes("empty.bin", b"")

        # Act / Assert
        assert storage.exists("empty.bin") is False


class TestSize:
    """size() returns byte length or 0 for missing files."""

    def test_size_of_known_payload(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)
        storage.write_bytes("blob", b"abcdef")

        # Act / Assert
        assert storage.size("blob") == 6

    def test_size_of_missing_file_is_zero(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act / Assert
        assert storage.size("missing") == 0


class TestDelete:
    """delete() removes existing keys and tolerates missing ones."""

    def test_delete_existing(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)
        storage.write_text("doomed.txt", "x")

        # Act
        storage.delete("doomed.txt")

        # Assert
        assert storage.exists("doomed.txt") is False

    def test_delete_missing_no_error(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act / Assert
        storage.delete("never_existed.txt")


class TestListPrefix:
    """list_prefix() returns every nested file under a key prefix."""

    def test_lists_recursive_files_only(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)
        storage.write_text("books/a/book.json", "{}")
        storage.write_text("books/a/ai/chapter_001/prompt.md", "p")
        storage.write_text("books/b/book.json", "{}")

        # Act
        keys = storage.list_prefix("books/a")

        # Assert
        assert sorted(keys) == sorted([
            "books/a/ai/chapter_001/prompt.md",
            "books/a/book.json",
        ])

    def test_missing_prefix_returns_empty(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act / Assert
        assert storage.list_prefix("nope") == []


class TestLocalPathReadMode:
    """local_path in read mode yields the real path."""

    def test_yields_existing_path(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)
        storage.write_bytes("clip.mp3", b"audio")

        # Act
        with storage.local_path("clip.mp3", "r") as path:
            data = path.read_bytes()

        # Assert
        assert data == b"audio"
        assert path == tmp_path / "clip.mp3"


class TestLocalPathWriteMode:
    """local_path in write mode prepares parent dirs."""

    def test_parent_dir_created(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act
        with storage.local_path("deep/nest/out.wav", "w") as path:
            path.write_bytes(b"new")

        # Assert
        assert (tmp_path / "deep" / "nest" / "out.wav").read_bytes() == b"new"


class TestAbsoluteKeyRejected:
    """Absolute keys are a programming error and are rejected."""

    def test_absolute_key_raises(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)

        # Act / Assert
        with pytest.raises(ValueError):
            storage.write_bytes("/etc/passwd", b"oops")


class TestCopyWithin:
    """copy_within copies one key to another without going through Python buffers."""

    def test_copies_bytes(self, tmp_path: Path) -> None:
        # Arrange
        storage = LocalStorageBackend(tmp_path)
        storage.write_bytes("a.mp3", b"sound")

        # Act
        storage.copy_within("a.mp3", "nested/b.mp3")

        # Assert
        assert storage.read_bytes("nested/b.mp3") == b"sound"
