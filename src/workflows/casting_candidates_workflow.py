"""Shortlists voices for every uncast character and saves them with playable previews."""
import json

import structlog

from src.characters.character_provider import (
    DEFAULT_CANDIDATE_LIMIT,
    CharacterProvider,
)
from src.characters.voice_candidate import VoiceCandidate
from src.domain.character import Character
from src.domain.character_id import slugify_name
from src.domain.models import Book
from src.downloader.file_downloader import FileDownloader
from src.repository.book_repository import BookRepository
from src.repository.project_gutenberg_url_mapper import get_book_id_from_url
from src.storage.storage import Storage
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)

_CASTING_DIR = "casting"
_CANDIDATES_FILENAME = "candidates.json"


class CastingCandidatesWorkflow(Workflow):
    """Write a shortlist of voices, with previews, for every character without one."""

    def __init__(
        self,
        repositories: list[BookRepository],
        character_provider: CharacterProvider,
        downloader: FileDownloader,
        storage: Storage,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> None:
        self._repositories = repositories
        self._character_provider = character_provider
        self._downloader = downloader
        self._storage = storage
        self._candidate_limit = candidate_limit

    def run(self, request: WorkflowRequest) -> Book:
        """Shortlist voices for each uncast character in the book."""
        book_id = get_book_id_from_url(request.url)
        logger.info("casting_candidates_workflow_started", book_id=book_id)

        book = self._repositories[0].load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in store for book_id={book_id!r}. "
                "Run the 'ai' workflow first."
            )

        for character in book.character_registry.characters:
            if character.id in book.voice_assignments:
                logger.info(
                    "casting_candidates_already_cast", character_id=character.id,
                )
                continue
            self._shortlist(book_id, character)

        logger.info("casting_candidates_workflow_complete", book_id=book_id)
        return book

    def _shortlist(self, book_id: str, character: Character) -> None:
        """Fetch, store previews for, and record the candidates for one character."""
        candidates = self._character_provider.candidates(
            character, self._candidate_limit,
        )
        playable: list[dict] = []  # type: ignore[type-arg]
        for candidate in candidates:
            preview_path = self._store_preview(book_id, character, candidate)
            if preview_path is None:
                continue
            playable.append({**candidate.to_dict(), "preview_path": preview_path})

        self._storage.write_text(
            self._candidates_key(book_id, character),
            json.dumps(
                {
                    "character_id": character.id,
                    "character_name": character.name,
                    "candidates": playable,
                },
                indent=2,
                ensure_ascii=False,
            ),
        )
        logger.info(
            "casting_candidates_saved",
            character_id=character.id, count=len(playable),
        )

    def _store_preview(
        self, book_id: str, character: Character, candidate: VoiceCandidate,
    ) -> "str | None":
        """Return the book-relative preview path, or None when it cannot be fetched."""
        path = (
            f"{_CASTING_DIR}/{slugify_name(character.name)}/"
            f"preview_{candidate.voice_id}.mp3"
        )
        key = f"{book_id}/{path}"
        if self._storage.exists(key):
            return path
        try:
            audio = self._downloader.download_bytes(candidate.preview_url)
        except RuntimeError as err:
            # One dead preview URL must not cost the whole shortlist.
            logger.warning(
                "casting_candidate_preview_failed",
                character_id=character.id, voice_id=candidate.voice_id, error=str(err),
            )
            return None
        self._storage.write_bytes(key, audio)
        return path

    @staticmethod
    def _candidates_key(book_id: str, character: Character) -> str:
        return (
            f"{book_id}/{_CASTING_DIR}/{slugify_name(character.name)}/"
            f"{_CANDIDATES_FILENAME}"
        )
