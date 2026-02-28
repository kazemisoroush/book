import unittest
from unittest.mock import Mock
from src.cli.download_command import DownloadCommand


class TestDownloadCommand(unittest.TestCase):

    def test_execute_downloads_single_book(self):
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        command = DownloadCommand(mock_downloader)

        result = command.execute(book_id=83)

        mock_downloader.parse.assert_called_once_with("https://www.gutenberg.org/cache/epub/83/pg83-h.zip")
        self.assertTrue(result)

    def test_execute_downloads_range_of_books(self):
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        command = DownloadCommand(mock_downloader)

        result = command.execute(start_id=1, end_id=3)

        self.assertEqual(mock_downloader.parse.call_count, 3)
        self.assertTrue(result)

    def test_execute_returns_false_on_failure(self):
        mock_downloader = Mock()
        mock_downloader.parse.return_value = False
        command = DownloadCommand(mock_downloader)

        result = command.execute(book_id=83)

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
