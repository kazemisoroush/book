"""Helper for mapping URLs to book IDs in staged workflows."""


def get_book_id_from_url(url: str) -> str:
    """Derive book_id from a Project Gutenberg URL."""
    from src.downloader.project_gutenberg_html_book_downloader import (
        ProjectGutenbergHTMLBookDownloader,
    )
    from src.parsers.static_project_gutenberg_html_metadata_parser import (
        StaticProjectGutenbergHTMLMetadataParser,
    )

    downloader = ProjectGutenbergHTMLBookDownloader()
    metadata_parser = StaticProjectGutenbergHTMLMetadataParser()

    html_content = downloader.download(url)
    metadata = metadata_parser.parse(html_content)

    return metadata.book_id
