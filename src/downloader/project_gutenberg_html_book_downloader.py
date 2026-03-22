import os
import zipfile
from io import BytesIO
import requests  # type: ignore[import-untyped]
from src.downloader.book_downloader import BookDownloader


class ProjectGutenbergHTMLBookDownloader(BookDownloader):

    def parse(self, url: str) -> bool:
        try:
            response = requests.get(url)

            book_id = self._extract_book_id(url)
            download_dir = f"books/{book_id}"
            os.makedirs(download_dir, exist_ok=True)

            with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
                zip_file.extractall(download_dir)

            return True
        except Exception:
            return False

    def _extract_book_id(self, url: str) -> str:
        parts = url.split('/')
        for part in parts:
            if part.isdigit():
                return part
        return "unknown"
