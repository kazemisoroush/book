"""Tests for source layout helpers."""
import os
from pathlib import Path

from src.downloader.source_layout import (
    book_source_dir,
    materialize_source,
    pg_id_from_url,
    staging_dir,
)


class TestPgIdFromUrl:
    """Numeric Project Gutenberg id is parsed from common URL shapes."""

    def test_cache_epub_url(self) -> None:
        # Arrange / Act
        result = pg_id_from_url("https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip")

        # Assert
        assert result == "1342"

    def test_files_path_url(self) -> None:
        # Arrange / Act
        result = pg_id_from_url("https://www.gutenberg.org/files/11/11-h.zip")

        # Assert
        assert result == "11"

    def test_unknown_when_no_digits(self) -> None:
        # Arrange / Act
        result = pg_id_from_url("https://example.com/no-id-here")

        # Assert
        assert result == "unknown"


class TestStagingDir:
    """Staging dir lives under {books_dir}/.sources/{pg_id}."""

    def test_default_books_dir(self) -> None:
        # Arrange / Act
        result = staging_dir(pg_id="11")

        # Assert
        assert result == Path("books/.sources/11")


class TestMaterializeSource:
    """materialize_source copies the staged sources into books/{book_id}/source/."""

    def test_copies_staged_files_to_book_source_dir(self, tmp_path: Path) -> None:
        # Arrange
        pg_dir = staging_dir(str(tmp_path), "11")
        pg_dir.mkdir(parents=True)
        (pg_dir / "pg11-images.html").write_text("<html></html>")
        (pg_dir / "images").mkdir()
        (pg_dir / "images" / "cover.png").write_bytes(b"\x89PNG")

        # Act
        materialize_source(str(tmp_path), "11", "alice:lewis_carroll")

        # Assert
        target = book_source_dir(str(tmp_path), "alice:lewis_carroll")
        assert (target / "pg11-images.html").read_text() == "<html></html>"
        assert (target / "images" / "cover.png").read_bytes() == b"\x89PNG"

    def test_skips_when_target_already_exists(self, tmp_path: Path) -> None:
        # Arrange
        pg_dir = staging_dir(str(tmp_path), "11")
        pg_dir.mkdir(parents=True)
        (pg_dir / "pg11-images.html").write_text("new content")
        target = book_source_dir(str(tmp_path), "alice:lewis_carroll")
        target.mkdir(parents=True)
        (target / "pg11-images.html").write_text("existing content")

        # Act
        materialize_source(str(tmp_path), "11", "alice:lewis_carroll")

        # Assert
        assert (target / "pg11-images.html").read_text() == "existing content"

    def test_noop_when_staging_dir_missing(self, tmp_path: Path) -> None:
        # Arrange — no staging dir created

        # Act
        materialize_source(str(tmp_path), "404", "missing_book")

        # Assert
        target = book_source_dir(str(tmp_path), "missing_book")
        assert not target.exists()


class TestDownloaderStagesUnderDotSources:
    """The downloader's cached path uses the staging convention."""

    def test_downloader_reads_existing_html_from_staging_dir(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        from src.downloader.project_gutenberg_html_book_downloader import (
            ProjectGutenbergHTMLBookDownloader,
        )

        staging = staging_dir(str(tmp_path), "1342")
        staging.mkdir(parents=True)
        (staging / "pg1342-h.html").write_text("<html>cached</html>")
        downloader = ProjectGutenbergHTMLBookDownloader(books_dir=str(tmp_path))

        # Act
        result = downloader.download(
            "https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip",
        )

        # Assert
        assert result == "<html>cached</html>"
        assert os.path.isdir(staging)
