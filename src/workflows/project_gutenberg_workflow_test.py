"""Tests for Project Gutenberg workflow."""
from unittest.mock import Mock, patch
import pytest
from src.workflows.project_gutenberg_workflow import (
    ProjectGutenbergWorkflow
)
from src.domain.models import (
    BookMetadata, BookContent, Chapter, Section
)
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser
)


class TestProjectGutenbergWorkflowFactory:
    """Tests for the factory method."""

    def test_create_returns_workflow_instance(self):
        # When
        workflow = ProjectGutenbergWorkflow.create()

        # Then
        assert isinstance(workflow, ProjectGutenbergWorkflow)

    def test_create_wires_downloader_dependency(self):
        # When
        workflow = ProjectGutenbergWorkflow.create()

        # Then
        assert isinstance(
            workflow.downloader,
            ProjectGutenbergHTMLBookDownloader
        )

    def test_create_wires_metadata_parser_dependency(self):
        # When
        workflow = ProjectGutenbergWorkflow.create()

        # Then
        assert isinstance(
            workflow.metadata_parser,
            StaticProjectGutenbergHTMLMetadataParser
        )

    def test_create_wires_content_parser_dependency(self):
        # When
        workflow = ProjectGutenbergWorkflow.create()

        # Then
        assert isinstance(
            workflow.content_parser,
            StaticProjectGutenbergHTMLContentParser
        )


class TestProjectGutenbergWorkflow:

    def test_run_downloads_and_parses_book(self):
        # Given
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "123"

        mock_metadata_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate="2020-01-01",
            language="en",
            originalPublication=None,
            credits=None
        )

        mock_content_parser = Mock()
        mock_content_parser.parse.return_value = BookContent(
            chapters=[
                Chapter(
                    number=1,
                    title="Chapter 1",
                    sections=[Section(text="Test paragraph")]
                )
            ]
        )

        workflow = ProjectGutenbergWorkflow(
            mock_downloader,
            mock_metadata_parser,
            mock_content_parser
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html', 'images'])]  # noqa: E501
            mock_open.return_value.__enter__.return_value.read.return_value = "<html>test</html>"  # noqa: E501
            book = workflow.run(url)

        # Then
        assert book.metadata.title == "Test Book"
        assert book.metadata.author == "Test Author"
        assert len(book.content.chapters) == 1
        mock_downloader.parse.assert_called_once_with(url)

    def test_run_raises_error_on_download_failure(self):
        # Given
        mock_downloader = Mock()
        mock_downloader.parse.return_value = False

        mock_metadata_parser = Mock()
        mock_content_parser = Mock()

        workflow = ProjectGutenbergWorkflow(
            mock_downloader,
            mock_metadata_parser,
            mock_content_parser
        )

        url = "https://invalid.url/bad.zip"

        # When/Then
        with pytest.raises(RuntimeError, match="Failed to download"):
            workflow.run(url)

    def test_run_raises_error_when_html_file_not_found(self):
        # Given
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "123"

        mock_metadata_parser = Mock()
        mock_content_parser = Mock()

        workflow = ProjectGutenbergWorkflow(
            mock_downloader,
            mock_metadata_parser,
            mock_content_parser
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When/Then
        with patch('os.walk') as mock_walk:
            mock_walk.return_value = [('books/123', [], ['images', 'styles.css'])]  # noqa: E501
            with pytest.raises(RuntimeError, match="No HTML file found"):
                workflow.run(url)

    def test_run_finds_html_file_with_various_extensions(self):
        # Given
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "123"

        mock_metadata_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )

        mock_content_parser = Mock()
        mock_content_parser.parse.return_value = BookContent(chapters=[])

        workflow = ProjectGutenbergWorkflow(
            mock_downloader,
            mock_metadata_parser,
            mock_content_parser
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.htm', 'images'])]  # noqa: E501
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"  # noqa: E501
            workflow.run(url)

        # Then
        mock_walk.assert_called_once()

    def test_run_finds_html_in_subdirectory(self):
        # Given - HTML file is in a subdirectory
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "456"

        mock_metadata_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Nested Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )

        mock_content_parser = Mock()
        mock_content_parser.parse.return_value = BookContent(chapters=[])

        workflow = ProjectGutenbergWorkflow(
            mock_downloader,
            mock_metadata_parser,
            mock_content_parser
        )

        url = "https://www.gutenberg.org/files/456/456-h.zip"

        # When - HTML is in subdirectory like books/456/456-h/456-h.htm
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            # Simulate directory structure with subdirectory
            mock_walk.return_value = [
                ('books/456', ['456-h'], []),
                ('books/456/456-h', [], ['456-h.htm', 'images']),
            ]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"  # noqa: E501
            book = workflow.run(url)

        # Then
        assert book.metadata.title == "Nested Test"

    def test_run_parses_metadata_and_content(self):
        # Given
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "456"

        mock_metadata_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Harry Potter",
            author="J.K. Rowling",
            releaseDate="2020-01-01",
            language="en",
            originalPublication="1997",
            credits="Test credits"
        )

        mock_content_parser = Mock()
        mock_content_parser.parse.return_value = BookContent(
            chapters=[
                Chapter(
                    number=1,
                    title="The Boy Who Lived",
                    sections=[
                        Section(text="Mr. and Mrs. Dursley...")
                    ]
                )
            ]
        )

        workflow = ProjectGutenbergWorkflow(
            mock_downloader,
            mock_metadata_parser,
            mock_content_parser
        )

        url = "https://www.gutenberg.org/files/456/456-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/456', [], ['456-h.html'])]
            test_html = "<html><body>Test content</body></html>"
            mock_open.return_value.__enter__.return_value.read.return_value = test_html  # noqa: E501
            book = workflow.run(url)

        # Then
        assert book.metadata.title == "Harry Potter"
        assert book.metadata.author == "J.K. Rowling"
        assert book.metadata.originalPublication == "1997"
        assert len(book.content.chapters) == 1
        assert book.content.chapters[0].title == "The Boy Who Lived"
        mock_metadata_parser.parse.assert_called_once_with(test_html)
        mock_content_parser.parse.assert_called_once_with(test_html)
