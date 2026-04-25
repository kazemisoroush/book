"""Project Gutenberg HTML book downloader.

Downloads zip archives from Project Gutenberg URLs, extracts the HTML file,
and returns its content as a string.  This downloader handles the zip → HTML
extraction pipeline for Project Gutenberg books.
"""
import os
import zipfile
from io import BytesIO

import requests
import structlog

from src.downloader.book_downloader import BookDownloader

logger = structlog.get_logger(__name__)


class ProjectGutenbergHTMLBookDownloader(BookDownloader):
    """Downloader for Project Gutenberg HTML books.

    Downloads zip archives from Project Gutenberg URLs, extracts HTML,
    and returns content. Implements disk caching to skip redundant downloads.
    """


    def download(self, url: str) -> str:
        """Download the book zip, extract, find the HTML file, and return its content.

        If the HTML file already exists on disk from a previous download,
        skips the network request and returns the cached file directly.

        Raises:
            RuntimeError: If download, extraction, or HTML lookup fails.
        """
        book_id = self._extract_book_id(url)
        download_dir = f"books/{book_id}"

        # Skip download if HTML already exists on disk
        existing_html = self._find_html_file(download_dir)
        if existing_html:
            logger.info("download_skipped_cached", url=url, book_id=book_id, html_file=existing_html)
            with open(existing_html, "r", encoding="utf-8") as f:
                return f.read()

        logger.info("download_started", url=url, book_id=book_id)
        try:
            response = requests.get(url)

            os.makedirs(download_dir, exist_ok=True)

            with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
                zip_file.extractall(download_dir)

            logger.info("download_complete", url=url, book_id=book_id, directory=download_dir)
        except Exception as exc:
            raise RuntimeError(f"Failed to download book from {url}: {exc}") from exc

        html_file = self._find_html_file(download_dir)
        if not html_file:
            raise RuntimeError(f"No HTML file found in {download_dir}")

        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()

    def _extract_book_id(self, url: str) -> str:
        parts = url.split('/')
        for part in parts:
            if part.isdigit():
                return part
        return "unknown"

    @staticmethod
    def _find_html_file(directory: str) -> str | None:
        """Find the first HTML file in *directory* recursively."""
        for root, _dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.html', '.htm')):
                    return os.path.join(root, filename)
        return None
