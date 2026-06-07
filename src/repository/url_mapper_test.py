"""Tests for url_mapper."""
from unittest.mock import patch

from src.domain.models import BookMetadata
from src.repository.url_mapper import get_book_id_from_url


def test_returns_book_id_from_downloaded_html_content() -> None:
    """Downloader returns HTML content; the metadata parser receives that content directly."""
    # Arrange
    html_content = "<html><head><title>x</title></head><body>y</body></html>"
    metadata = BookMetadata(
        title="Pride and Prejudice",
        author="Austen, Jane, 1775-1817",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )
    download_target = (
        "src.downloader.project_gutenberg_html_book_downloader."
        "ProjectGutenbergHTMLBookDownloader.download"
    )
    parse_target = (
        "src.parsers.static_project_gutenberg_html_metadata_parser."
        "StaticProjectGutenbergHTMLMetadataParser.parse"
    )

    # Act
    with patch(download_target, return_value=html_content) as download_mock, \
            patch(parse_target, return_value=metadata) as parse_mock:
        book_id = get_book_id_from_url("http://example.com/book.zip")

    # Assert
    download_mock.assert_called_once_with("http://example.com/book.zip")
    parse_mock.assert_called_once_with(html_content)
    assert book_id == metadata.book_id
