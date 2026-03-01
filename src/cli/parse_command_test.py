import unittest
from unittest.mock import Mock, mock_open, patch
from src.cli.parse_command import ParseCommand
from src.domain.models import Book, BookMetadata, BookContent, Chapter, Section


class TestParseCommand(unittest.TestCase):

    def test_execute_reads_html_file(self):
        mock_metadata_parser = Mock()
        mock_content_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Test", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None
        )
        mock_content_parser.parse.return_value = BookContent(chapters=[])
        command = ParseCommand(mock_metadata_parser, mock_content_parser)

        with patch('builtins.open', mock_open(read_data='<html></html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                result = command.execute(book_id=1)

        self.assertIsNotNone(result)

    def test_execute_calls_both_parsers(self):
        mock_metadata_parser = Mock()
        mock_content_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Test", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None
        )
        mock_content_parser.parse.return_value = BookContent(chapters=[])
        command = ParseCommand(mock_metadata_parser, mock_content_parser)

        with patch('builtins.open', mock_open(read_data='<html>content</html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                command.execute(book_id=1)

        mock_metadata_parser.parse.assert_called_once_with('<html>content</html>')
        mock_content_parser.parse.assert_called_once_with('<html>content</html>')

    def test_execute_returns_complete_book(self):
        metadata = BookMetadata(
            title="Alice in Wonderland", author="Carroll, Lewis",
            releaseDate="2026-01-01", language="en",
            originalPublication=None, credits=None
        )
        chapter = Chapter(number=1, title="Chapter 1", sections=[Section(text="Content")])
        content = BookContent(chapters=[chapter])

        mock_metadata_parser = Mock()
        mock_content_parser = Mock()
        mock_metadata_parser.parse.return_value = metadata
        mock_content_parser.parse.return_value = content
        command = ParseCommand(mock_metadata_parser, mock_content_parser)

        with patch('builtins.open', mock_open(read_data='<html></html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                result = command.execute(book_id=1)

        self.assertIsInstance(result, Book)
        self.assertEqual(result.metadata, metadata)
        self.assertEqual(result.content, content)


if __name__ == '__main__':
    unittest.main()
