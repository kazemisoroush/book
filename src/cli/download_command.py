from src.downloader.book_downloader import BookDownloader


class DownloadCommand:

    def __init__(self, downloader: BookDownloader):
        self._downloader = downloader

    def execute(self, book_id: int = None, start_id: int = None, end_id: int = None) -> bool:
        if book_id is not None:
            return self._download_single(book_id)
        elif start_id is not None and end_id is not None:
            return self._download_range(start_id, end_id)
        return False

    def _download_single(self, book_id: int) -> bool:
        url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}-h.zip"
        return self._downloader.parse(url)

    def _download_range(self, start_id: int, end_id: int) -> bool:
        success = True
        for book_id in range(start_id, end_id + 1):
            result = self._download_single(book_id)
            if not result:
                success = False
        return success
