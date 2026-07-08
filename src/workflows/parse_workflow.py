"""Parse workflow: download and parse a book without AI beatation."""
from dataclasses import replace

import structlog

from src.domain.character import make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book
from src.parsers.book_source import BookSource
from src.repository.book_repository import BookRepository
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class ParseWorkflow(Workflow):
    """Download and parse a book into chapters and sections."""

    def __init__(
        self,
        book_source: BookSource,
        repositories: list[BookRepository],
    ) -> None:
        self._book_source = book_source
        self._repositories = repositories

    def run(self, request: WorkflowRequest) -> Book:
        logger.info("parse_workflow_started", url=request.url)

        ctx = self._book_source.get_book(
            request.url,
            request.start_chapter,
            request.end_chapter,
            request.refresh,
        )

        book = Book(
            metadata=replace(ctx.book.metadata, source_url=request.url),
            content=ctx.content,
            character_registry=CharacterRegistry(
                characters=[make_default_narrator()],
            ),
        )

        for repo in self._repositories:
            repo.save(book)

        logger.info(
            "parse_workflow_complete",
            title=book.metadata.title,
            total_chapters=len(book.content.chapters),
        )
        return book
