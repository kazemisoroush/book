"""HTTP implementation of :class:`FileDownloader`."""
import requests
import structlog

from src.downloader.file_downloader import FileDownloader

logger = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30


class HTTPFileDownloader(FileDownloader):
    """Fetches a file over HTTP with a bounded timeout."""

    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds

    def download_bytes(self, url: str) -> bytes:
        """Return the response body at *url*."""
        try:
            response = requests.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as err:
            raise RuntimeError(f"Failed to download {url!r}") from err
        logger.info("file_downloaded", url=url, bytes=len(response.content))
        return response.content
