"""Abstract interface for downloading book content from external sources.

Defines the ``BookDownloader`` ABC that all concrete downloaders must implement.
The downloader layer is responsible for fetching book content (HTML, EPUB, etc.)
and returning it as a string.
"""
from abc import ABC, abstractmethod


class BookDownloader(ABC):
    """Abstract base class for book downloaders.

    Concrete implementations handle fetching book content from external
    sources (HTTP, filesystem, etc.) and returning it as a string.
    """


    @abstractmethod
    def download(self, url: str) -> str:
        """Download the book at *url* and return its HTML content.

        Raises:
            RuntimeError: If the download or extraction fails.
        """
