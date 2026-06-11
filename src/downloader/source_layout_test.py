"""Tests for source layout helpers."""
from pathlib import Path

from src.downloader.source_layout import (
    book_source_dir,
    materialize_source,
    pg_id_from_url,
    staging_dir,
)


class TestPgIdFromUrl:
    """Parses PG numeric id from common URL shapes."""

    def test_extracts_numeric_id(self) -> None:
        # Arrange / Act / Assert
        assert pg_id_from_url("https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip") == "1342"
        assert pg_id_from_url("https://example.com/no-id-here") == "unknown"


class TestMaterializeSource:
    """Mirrors staged sources into books/{book_id}/source/."""

    def test_copies_staged_files(self, tmp_path: Path) -> None:
        # Arrange
        pg_dir = staging_dir(str(tmp_path), "11")
        pg_dir.mkdir(parents=True)
        (pg_dir / "pg11-images.html").write_text("<html></html>")

        # Act
        materialize_source(str(tmp_path), "11", "alice")

        # Assert
        assert (book_source_dir(str(tmp_path), "alice") / "pg11-images.html").read_text() == "<html></html>"

    def test_skips_when_target_exists(self, tmp_path: Path) -> None:
        # Arrange
        pg_dir = staging_dir(str(tmp_path), "11")
        pg_dir.mkdir(parents=True)
        (pg_dir / "pg11-images.html").write_text("new")
        target = book_source_dir(str(tmp_path), "alice")
        target.mkdir(parents=True)
        (target / "pg11-images.html").write_text("existing")

        # Act
        materialize_source(str(tmp_path), "11", "alice")

        # Assert
        assert (target / "pg11-images.html").read_text() == "existing"
