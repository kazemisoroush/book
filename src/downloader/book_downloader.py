from abc import ABC, abstractmethod


class BookDownloader(ABC):

    @abstractmethod
    def download(self, url: str) -> str:
        """Download the book at *url* and return its HTML content.

        Raises:
            RuntimeError: If the download or extraction fails.
        """
