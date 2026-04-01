"""Project Gutenberg workflow for downloading and parsing books."""
import os
from typing import Optional
import structlog
from src.workflows.workflow import Workflow
from src.domain.models import Book
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser
)

logger = structlog.get_logger(__name__)


class ProjectGutenbergWorkflow(Workflow):
    """Workflow for processing Project Gutenberg HTML books (static parsing only).

    This workflow orchestrates:
    1. Downloading the book zip file
    2. Finding the HTML file
    3. Parsing metadata
    4. Parsing content
    5. Assembling the Book object

    This class has no knowledge of AI or section segmentation. For AI-powered
    section segmentation, use AIProjectGutenbergWorkflow.

    Follows SOLID principles:
    - Single Responsibility: Orchestrates static book processing pipeline
    - Dependency Inversion: Depends on parser/downloader abstractions
    """

    def __init__(self, downloader, metadata_parser, content_parser):
        """Initialize the workflow with dependencies.

        Args:
            downloader: BookDownloader instance
            metadata_parser: BookMetadataParser instance
            content_parser: BookContentParser instance
        """
        self.downloader = downloader
        self.metadata_parser = metadata_parser
        self.content_parser = content_parser

    @classmethod
    def create(cls) -> "ProjectGutenbergWorkflow":
        """Factory method to create workflow with default dependencies.

        Returns:
            ProjectGutenbergWorkflow instance with wired dependencies
        """
        downloader = ProjectGutenbergHTMLBookDownloader()
        metadata_parser = StaticProjectGutenbergHTMLMetadataParser()
        content_parser = StaticProjectGutenbergHTMLContentParser()

        return cls(downloader, metadata_parser, content_parser)

    def run(self, url: str, chapter_limit: int = 3) -> Book:
        """Run the workflow to download and parse a book.

        Args:
            url: Project Gutenberg book URL (e.g.,
                 https://www.gutenberg.org/files/123/123-h.zip)
            chapter_limit: Maximum number of chapters to include in the
                           returned ``Book``.  ``0`` means all chapters.
                           Defaults to 3.

        Returns:
            Parsed Book object containing at most ``chapter_limit`` chapters.

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        # Step 1: Download the book
        logger.info("workflow_started", url=url)
        if not self.downloader.parse(url):
            raise RuntimeError(f"Failed to download book from {url}")

        # Step 2: Find the downloaded HTML file
        book_id = self.downloader._extract_book_id(url)
        download_dir = f"books/{book_id}"

        html_file = self._find_html_file(download_dir)
        if not html_file:
            raise RuntimeError(f"No HTML file found in {download_dir}")

        logger.info("parsing_started", html_file=html_file)

        # Step 3: Read HTML content
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Step 4: Parse metadata and content
        metadata = self.metadata_parser.parse(html_content)
        content = self.content_parser.parse(html_content)

        # Step 5: Apply chapter limit (0 means all)
        if chapter_limit > 0:
            content.chapters = content.chapters[:chapter_limit]

        logger.info(
            "workflow_complete",
            title=metadata.title,
            chapters=len(content.chapters),
        )

        # Step 6: Assemble and return Book
        return Book(metadata=metadata, content=content)

    def _find_html_file(self, directory: str) -> Optional[str]:
        """Find the first HTML file in the directory recursively.

        Args:
            directory: Directory to search

        Returns:
            Path to HTML file, or None if not found
        """
        for root, _dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.html', '.htm')):
                    return os.path.join(root, filename)
        return None
