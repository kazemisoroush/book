import os
import zipfile
from io import BytesIO
import requests  # type: ignore[import-untyped]
import structlog
from src.downloader.book_downloader import BookDownloader

logger = structlog.get_logger(__name__)


class ProjectGutenbergHTMLBookDownloader(BookDownloader):

    def parse(self, url: str) -> bool:
        book_id = self._extract_book_id(url)
        download_dir = f"books/{book_id}"
        logger.info("download_started", url=url, book_id=book_id)
        try:
            response = requests.get(url)

            os.makedirs(download_dir, exist_ok=True)

            with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
                zip_file.extractall(download_dir)

            logger.info("download_complete", url=url, book_id=book_id, directory=download_dir)
            return True
        except Exception as exc:
            logger.error("download_failed", url=url, book_id=book_id, error=str(exc))
            return False

    def _extract_book_id(self, url: str) -> str:
        parts = url.split('/')
        for part in parts:
            if part.isdigit():
                return part
        return "unknown"
