"""Project Gutenberg HTML book downloader.

Downloads zip archives from Project Gutenberg URLs, extracts the HTML file,
and returns its content as a string.  Stages downloads under
``books/.sources/{pg_id}/`` so caching is keyed by the URL's numeric id.
"""
import os
import zipfile
from io import BytesIO

import requests
import structlog

from src.downloader.book_downloader import BookDownloader
from src.downloader.source_layout import pg_id_from_url, staging_dir

logger = structlog.get_logger(__name__)


class ProjectGutenbergHTMLBookDownloader(BookDownloader):
    """Downloader for Project Gutenberg HTML books.

    Downloads zip archives from Project Gutenberg URLs, extracts HTML,
    and returns content. Implements disk caching to skip redundant downloads.
    """

    def __init__(self, books_dir: str = "books") -> None:
        self._books_dir = books_dir


    def download(self, url: str) -> str:
        """Download the book zip, extract, find the HTML file, and return its content.

        If the HTML file already exists on disk from a previous download,
        skips the network request and returns the cached file directly.

        Raises:
            RuntimeError: If download, extraction, or HTML lookup fails.
        """
        pg_id = pg_id_from_url(url)
        download_dir = str(staging_dir(self._books_dir, pg_id))

        existing_html = (
            self._find_html_file(download_dir)
            or self._find_materialized_source(pg_id)
        )
        if existing_html:
            logger.info(
                "download_skipped_cached", url=url, pg_id=pg_id, html_file=existing_html,
            )
            with open(existing_html, "r", encoding="utf-8") as f:
                return f.read()

        logger.info("download_started", url=url, pg_id=pg_id)
        try:
            response = requests.get(url)

            os.makedirs(download_dir, exist_ok=True)

            with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
                zip_file.extractall(download_dir)

            logger.info(
                "download_complete", url=url, pg_id=pg_id, directory=download_dir,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to download book from {url}: {exc}") from exc

        html_file = self._find_html_file(download_dir)
        if not html_file:
            raise RuntimeError(f"No HTML file found in {download_dir}")

        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()

    def _find_materialized_source(self, pg_id: str) -> str | None:
        """Search ``{books_dir}/*/source/`` for an HTML file from this PG id."""
        books_path = self._books_dir
        if not os.path.isdir(books_path):
            return None
        prefix = f"pg{pg_id}"
        for book_dir in os.listdir(books_path):
            source = os.path.join(books_path, book_dir, "source")
            if not os.path.isdir(source):
                continue
            for filename in os.listdir(source):
                if filename.startswith(prefix) and filename.endswith(('.html', '.htm')):
                    return os.path.join(source, filename)
        return None

    @staticmethod
    def _find_html_file(directory: str) -> str | None:
        """Find the first HTML file in *directory* recursively."""
        for root, _dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.html', '.htm')):
                    return os.path.join(root, filename)
        return None
