"""Tests for CharactersWorkflow."""
from pathlib import Path

import pytest

from src.characters.character_provider import CharacterProvider
from src.domain.character import NARRATOR_NAME, Character, make_default_narrator
from src.domain.character_id import build_character_id
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
)
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.workflows.characters_workflow import CharactersWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"


class _RecordingCharacterProvider(CharacterProvider):
    """Counts upsert calls and returns a deterministic voice token."""

    def __init__(self) -> None:
        self.upserts: list[Character] = []

    def upsert(self, character: Character) -> str:
        self.upserts.append(character)
        return f"voice_for_{character.character_id}"

    def get_all(self, book: Book) -> dict[str, str]:
        return {
            c.character_id: c.voice_id
            for c in book.character_registry.characters
            if c.voice_id is not None
        }


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.characters_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _save_book_with_characters(
    tmp_path: Path, *characters: Character,
) -> tuple[FileBookRepository, str]:
    metadata = BookMetadata(
        title="The Book", author="Author", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    registry = CharacterRegistry(characters=[make_default_narrator(generate_book_id(metadata))])
    for c in characters:
        registry.add(c)
    book = Book(
        metadata=metadata,
        content=BookContent(chapters=[]),
        character_registry=registry,
    )
    book_id = generate_book_id(metadata)
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book, book_id)
    return repository, book_id


def test_run_upserts_every_character_and_stamps_voice_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each character is upserted once; voice_id ends up persisted on the book."""
    # Arrange
    book_id_str = "The Book - Author"
    alice_id = f"{book_id_str}:alice"
    repository, book_id = _save_book_with_characters(
        tmp_path,
        Character(character_id=alice_id, name="Alice"),
    )
    _patch_resolver(monkeypatch, book_id)
    provider = _RecordingCharacterProvider()
    workflow = CharactersWorkflow(repository=repository, character_provider=provider)

    # Act
    result = workflow.run(WorkflowRequest(url=_URL))

    # Assert
    upserted_ids = sorted(c.character_id for c in provider.upserts)
    assert upserted_ids == sorted([build_character_id(book_id, NARRATOR_NAME), alice_id])
    voice_map = {c.character_id: c.voice_id for c in result.character_registry.characters}
    assert voice_map == {
        build_character_id(book_id, NARRATOR_NAME): f"voice_for_{build_character_id(book_id, NARRATOR_NAME)}",
        alice_id: f"voice_for_{alice_id}",
    }


def test_run_persists_updated_book(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The book on disk carries the voice_ids after the workflow runs."""
    # Arrange
    repository, book_id = _save_book_with_characters(tmp_path)
    _patch_resolver(monkeypatch, book_id)
    provider = _RecordingCharacterProvider()
    workflow = CharactersWorkflow(repository=repository, character_provider=provider)

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    reloaded = repository.load(book_id)
    assert reloaded is not None
    narr = reloaded.character_registry.get(build_character_id(book_id, NARRATOR_NAME))
    assert narr is not None
    assert narr.voice_id == f"voice_for_{build_character_id(book_id, NARRATOR_NAME)}"


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run() raises ValueError when the book is not in the repository."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent")
    workflow = CharactersWorkflow(
        repository=repository, character_provider=_RecordingCharacterProvider(),
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))
