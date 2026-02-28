import unittest
from unittest.mock import Mock, patch, mock_open
from src.downloader.project_gutenberg_html_book_downloader import ProjectGutenbergHTMLBookDownloader


class TestProjectGutenbergHTMLBookDownloader(unittest.TestCase):

    def test_download_fetches_zip_from_url(self):
        downloader = ProjectGutenbergHTMLBookDownloader()
        mock_response = Mock()
        mock_response.content = b'fake zip content'
        mock_zip = Mock()
        mock_zip.__enter__ = Mock(return_value=mock_zip)
        mock_zip.__exit__ = Mock(return_value=False)

        with patch('requests.get', return_value=mock_response) as mock_get:
            with patch('zipfile.ZipFile', return_value=mock_zip):
                with patch('builtins.open', mock_open()):
                    result = downloader.parse("https://www.gutenberg.org/cache/epub/83/pg83-h.zip")

        mock_get.assert_called_once_with("https://www.gutenberg.org/cache/epub/83/pg83-h.zip")
        self.assertTrue(result)

    def test_download_extracts_zip_content(self):
        downloader = ProjectGutenbergHTMLBookDownloader()
        mock_response = Mock()
        mock_response.content = b'fake zip content'
        mock_zip = Mock()
        mock_zip.__enter__ = Mock(return_value=mock_zip)
        mock_zip.__exit__ = Mock(return_value=False)

        with patch('requests.get', return_value=mock_response):
            with patch('zipfile.ZipFile', return_value=mock_zip):
                with patch('builtins.open', mock_open()):
                    result = downloader.parse("https://www.gutenberg.org/cache/epub/83/pg83-h.zip")

        mock_zip.extractall.assert_called_once()
        self.assertTrue(result)

    def test_download_saves_to_books_directory(self):
        downloader = ProjectGutenbergHTMLBookDownloader()
        mock_response = Mock()
        mock_response.content = b'fake zip content'
        mock_zip = Mock()
        mock_zip.__enter__ = Mock(return_value=mock_zip)
        mock_zip.__exit__ = Mock(return_value=False)

        with patch('requests.get', return_value=mock_response):
            with patch('zipfile.ZipFile', return_value=mock_zip):
                with patch('os.makedirs') as mock_makedirs:
                    with patch('builtins.open', mock_open()):
                        result = downloader.parse("https://www.gutenberg.org/cache/epub/83/pg83-h.zip")

        mock_makedirs.assert_called()
        self.assertTrue(result)

    def test_download_returns_false_on_failure(self):
        downloader = ProjectGutenbergHTMLBookDownloader()

        with patch('requests.get', side_effect=Exception("Network error")):
            result = downloader.parse("https://www.gutenberg.org/cache/epub/83/pg83-h.zip")

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
