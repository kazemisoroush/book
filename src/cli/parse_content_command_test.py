import unittest
from unittest.mock import Mock, mock_open, patch
from src.cli.parse_content_command import ParseContentCommand
from src.domain.models import BookContent, Chapter, Section


class TestParseContentCommand(unittest.TestCase):

    def test_execute_reads_html_file(self):
        mock_parser = Mock()
        mock_parser.parse.return_value = BookContent(chapters=[])
        command = ParseContentCommand(mock_parser)

        with patch('builtins.open', mock_open(read_data='<html></html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                result = command.execute(book_id=1)

        self.assertIsNotNone(result)

    def test_execute_calls_parser_with_content(self):
        mock_parser = Mock()
        mock_parser.parse.return_value = BookContent(chapters=[])
        command = ParseContentCommand(mock_parser)

        with patch('builtins.open', mock_open(read_data='<html>content</html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                command.execute(book_id=1)

        mock_parser.parse.assert_called_once_with('<html>content</html>')

    def test_execute_returns_book_content(self):
        chapter = Chapter(number=1, title="Chapter 1", sections=[Section(text="Content")])
        expected_content = BookContent(chapters=[chapter])
        mock_parser = Mock()
        mock_parser.parse.return_value = expected_content
        command = ParseContentCommand(mock_parser)

        with patch('builtins.open', mock_open(read_data='<html></html>')):
            with patch('glob.glob', return_value=['books/1/pg1-images.html']):
                result = command.execute(book_id=1)

        self.assertEqual(result, expected_content)


if __name__ == '__main__':
    unittest.main()
