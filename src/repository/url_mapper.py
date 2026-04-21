"""Helper for mapping URLs to book IDs in staged workflows."""
from src.repository.book_id import generate_book_id


def get_book_id_from_url(url: str) -> str:
    """Derive book_id from a Project Gutenberg URL.

    Downloads and parses just the metadata to generate a stable book_id.
    This enables staged workflows to load books from the repository using
    only the URL as input.

    Args:
        url: Project Gutenberg book URL

    Returns:
        book_id string (format: "Title - Author")
    """
    from src.downloader.project_gutenberg_html_book_downloader import (
        ProjectGutenbergHTMLBookDownloader
    )
    from src.parsers.static_project_gutenberg_html_metadata_parser import (
        StaticProjectGutenbergHTMLMetadataParser
    )

    downloader = ProjectGutenbergHTMLBookDownloader()
    metadata_parser = StaticProjectGutenbergHTMLMetadataParser()

    html_path = downloader.download(url)
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    metadata = metadata_parser.parse(html_content)

    return generate_book_id(metadata)
