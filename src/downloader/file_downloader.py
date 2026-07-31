"""Abstract interface for fetching a single binary file from an external source."""
from abc import ABC, abstractmethod


class FileDownloader(ABC):
    """Fetches one file's raw bytes.

    Separate from :class:`BookDownloader`, which returns decoded text for a whole book.
    """

    @abstractmethod
    def download_bytes(self, url: str) -> bytes:
        """Return the bytes at *url*.

        Raises:
            RuntimeError: If the download fails or the server reports an error.
        """
