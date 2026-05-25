"""Character voice provisioning workflow.

Loads the book produced by the AI workflow, upserts every character on
the configured :class:`CharacterProvider`, stamps the resulting voice
token on each character, and persists the book back to the repository.
"""
from dataclasses import replace as dc_replace

import structlog

from src.characters.character_provider import CharacterProvider
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)


class CharactersWorkflow(Workflow):
    """Make sure every character in the book has a voice on the TTS vendor."""

    def __init__(
        self,
        repository: BookRepository,
        character_provider: CharacterProvider,
    ) -> None:
        self._repository = repository
        self._character_provider = character_provider

    def run(self, request: WorkflowRequest) -> Book:
        book_id = get_book_id_from_url(request.url)
        logger.info("characters_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' workflow first."
            )

        for i, character in enumerate(book.character_registry.characters):
            voice_id = self._character_provider.upsert(book, character)
            book.character_registry.characters[i] = dc_replace(character, voice_id=voice_id)
            logger.info(
                "character_voice_provisioned",
                character_id=character.character_id,
                voice_id=voice_id,
            )

        self._repository.save(book, book_id)
        logger.info("characters_workflow_complete", book_id=book_id)
        return book
