"""Project Gutenberg workflow for downloading and parsing books."""
from typing import Optional
import structlog
from src.workflows.workflow import Workflow
from src.domain.models import Book
from src.parsers.book_source import BookSource
from src.parsers.project_gutenberg_book_source import ProjectGutenbergBookSource
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

    This workflow delegates all download/parse infrastructure to a BookSource
    and acts as a pure orchestrator.

    This class has no knowledge of AI or section segmentation. For AI-powered
    section segmentation, use AIProjectGutenbergWorkflow.
    """

    def __init__(self, book_source: BookSource) -> None:
        self.book_source = book_source

    @classmethod
    def create(cls) -> "ProjectGutenbergWorkflow":
        """Factory method to create workflow with default dependencies."""
        downloader = ProjectGutenbergHTMLBookDownloader()
        metadata_parser = StaticProjectGutenbergHTMLMetadataParser()
        content_parser = StaticProjectGutenbergHTMLContentParser()
        book_source = ProjectGutenbergBookSource(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
        )
        return cls(book_source)

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Run the workflow to download and parse a book.

        Args:
            url: Project Gutenberg book URL
            start_chapter: Ignored for this workflow (static parse only).
            end_chapter: Ignored for this workflow (static parse only).
            refresh: Ignored for this workflow (no caching in static parse).

        Returns:
            Parsed Book object with all chapters.

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        logger.info("workflow_started", url=url)
        book = self.book_source.get_book(url)
        logger.info(
            "workflow_complete",
            title=book.metadata.title,
            chapters=len(book.content.chapters),
        )
        return book
