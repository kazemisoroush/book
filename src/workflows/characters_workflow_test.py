"""Tests for CharactersWorkflow."""
from pathlib import Path

import pytest

from src.characters.character_provider import CharacterProvider
from src.domain.character import NARRATOR_ID, Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
)
from src.stores.file_book_store import FileBookStore
from src.workflows.characters_workflow import CharactersWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"


class _RecordingCharacterProvider(CharacterProvider):
    """Counts upsert calls and returns a deterministic voice token per character."""

    def __init__(self) -> None:
        self.upserts: list[tuple[Character, str]] = []

    def upsert(
        self, character: Character, book_id: str, refresh: bool = False,
    ) -> str:
        self.upserts.append((character, book_id))
        return f"voice_for_{character.id}"


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.characters_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _save_book_with_characters(
    tmp_path: Path, *characters: Character,
) -> tuple[FileBookStore, str]:
    metadata = BookMetadata(
        title="The Book", author="Author", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    registry = CharacterRegistry(characters=[make_default_narrator()])
    for c in characters:
        registry.add(c)
    book = Book(
        metadata=metadata,
        content=BookContent(chapters=[]),
        character_registry=registry,
    )
    book_id = metadata.book_id
    store = FileBookStore(base_dir=str(tmp_path))
    store.save(book)
    return store, book_id


def test_run_upserts_every_character_and_stores_voice_assignments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store, book_id = _save_book_with_characters(
        tmp_path,
        Character(id=2, name="Alice"),
    )
    _patch_resolver(monkeypatch, book_id)
    provider = _RecordingCharacterProvider()
    workflow = CharactersWorkflow(book_stores=[store], character_provider=provider)

    # Act
    result = workflow.run(WorkflowRequest(url=_URL))

    # Assert
    upserted_ids = sorted(c.id for c, _ in provider.upserts)
    assert upserted_ids == [NARRATOR_ID, 2]
    assert result.voice_assignments == {
        NARRATOR_ID: f"voice_for_{NARRATOR_ID}",
        2: "voice_for_2",
    }


def test_run_persists_voice_assignments_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store, book_id = _save_book_with_characters(tmp_path)
    _patch_resolver(monkeypatch, book_id)
    provider = _RecordingCharacterProvider()
    workflow = CharactersWorkflow(book_stores=[store], character_provider=provider)

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    reloaded = store.load(book_id)
    assert reloaded is not None
    assert reloaded.voice_assignments[NARRATOR_ID] == f"voice_for_{NARRATOR_ID}"


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store = FileBookStore(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent")
    workflow = CharactersWorkflow(
        book_stores=[store], character_provider=_RecordingCharacterProvider(),
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))
