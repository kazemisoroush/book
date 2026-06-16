"""Character voice provisioning workflow."""
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
        repositories: list[BookRepository],
        character_provider: CharacterProvider,
    ) -> None:
        self._repositories = repositories
        self._character_provider = character_provider

    def run(self, request: WorkflowRequest) -> Book:
        book_id = get_book_id_from_url(request.url)
        logger.info("characters_workflow_started", book_id=book_id)

        book = self._repositories[0].load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' workflow first."
            )

        for character in book.character_registry.characters:
            voice_id = self._character_provider.upsert(
                character, book_id, refresh=request.refresh,
            )
            book.voice_assignments[character.id] = voice_id
            logger.info(
                "character_voice_provisioned",
                character_id=character.id,
                voice_id=voice_id,
            )

        for repository in self._repositories:
            repository.save(book)
        logger.info("characters_workflow_complete", book_id=book_id)
        return book
