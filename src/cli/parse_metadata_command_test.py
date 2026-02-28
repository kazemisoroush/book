import unittest
from unittest.mock import Mock, mock_open, patch
from src.cli.parse_metadata_command import ParseMetadataCommand
from src.domain.models import BookMetadata


class TestParseMetadataCommand(unittest.TestCase):

    def test_execute_reads_html_file(self):
        mock_parser = Mock()
        mock_parser.parse.return_value = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        command = ParseMetadataCommand(mock_parser)

        with patch('builtins.open', mock_open(read_data='<html></html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                result = command.execute(book_id=1)

        self.assertIsNotNone(result)

    def test_execute_calls_parser_with_content(self):
        mock_parser = Mock()
        mock_parser.parse.return_value = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        command = ParseMetadataCommand(mock_parser)

        with patch('builtins.open', mock_open(read_data='<html>content</html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                command.execute(book_id=1)

        mock_parser.parse.assert_called_once_with('<html>content</html>')

    def test_execute_returns_metadata(self):
        expected_metadata = BookMetadata(
            title="Pride and Prejudice",
            author="Austen, Jane",
            releaseDate="2026-01-01",
            language="en",
            originalPublication=None,
            credits=None
        )
        mock_parser = Mock()
        mock_parser.parse.return_value = expected_metadata
        command = ParseMetadataCommand(mock_parser)

        with patch('builtins.open', mock_open(read_data='<html></html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                result = command.execute(book_id=1)

        self.assertEqual(result, expected_metadata)


if __name__ == '__main__':
    unittest.main()
