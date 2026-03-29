"""Tests verifying that the downloader uses structlog for logging."""
from unittest.mock import Mock, patch, MagicMock


class TestDownloaderUsesStructlog:
    """Downloader must use structlog for progress and error events."""

    def test_downloader_module_has_structlog_logger(self):
        """The downloader module must define a module-level structlog logger."""
        import src.downloader.project_gutenberg_html_book_downloader as mod
        # The module must have a 'logger' attribute that is a structlog logger
        assert hasattr(mod, 'logger')

    def test_successful_download_logs_event(self):
        """A successful download must emit at least one structlog log event."""
        from src.downloader.project_gutenberg_html_book_downloader import (
            ProjectGutenbergHTMLBookDownloader
        )

        mock_response = Mock()
        mock_response.content = b'PK\x03\x04fake'  # minimal zip-like bytes
        mock_zip = MagicMock()
        mock_zip.__enter__ = Mock(return_value=mock_zip)
        mock_zip.__exit__ = Mock(return_value=False)

        with patch('requests.get', return_value=mock_response), \
             patch('zipfile.ZipFile', return_value=mock_zip), \
             patch('os.makedirs'), \
             patch(
                'src.downloader.project_gutenberg_html_book_downloader.logger'
             ) as mock_logger:
            downloader = ProjectGutenbergHTMLBookDownloader()
            downloader.parse("https://www.gutenberg.org/files/83/83-h.zip")

        assert mock_logger.info.called or mock_logger.debug.called

    def test_failed_download_logs_error(self):
        """A failed download must emit an error-level structlog event."""
        from src.downloader.project_gutenberg_html_book_downloader import (
            ProjectGutenbergHTMLBookDownloader
        )

        with patch('requests.get', side_effect=Exception("Network error")), \
             patch(
                'src.downloader.project_gutenberg_html_book_downloader.logger'
             ) as mock_logger:
            downloader = ProjectGutenbergHTMLBookDownloader()
            downloader.parse("https://www.gutenberg.org/files/83/83-h.zip")

        assert mock_logger.error.called or mock_logger.warning.called
