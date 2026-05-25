"""Tests for TTSWorkflow."""
from pathlib import Path

import pytest

from src.audio.tts.tts_provider import StubTTSProvider
from src.characters.character_provider import CharacterProvider
from src.domain.beat import Beat, BeatType
from src.domain.character_id import build_character_id
from src.domain.models import (
    NARRATOR_NAME,
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Character,
    CharacterRegistry,
    Section,
)
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.workflows.tts_workflow import TTSWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"


class _StubCharacterProvider(CharacterProvider):
    def __init__(self, voice_map: dict[str, str]) -> None:
        self._voice_map = voice_map

    def upsert(self, character: Character) -> str:
        return self._voice_map[character.character_id]

    def get_all(self, book: Book) -> dict[str, str]:
        return dict(self._voice_map)


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.tts_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _make_book(book_id: str) -> Book:
    """Create a test book with two narratable beats."""
    narr_id = build_character_id(book_id, NARRATOR_NAME)
    alice_id = f"{book_id}:alice"
    registry = CharacterRegistry.with_default_narrator(book_id)
    registry.add(Character(
        character_id=alice_id,
        name="Alice",
        description="A young girl",
        is_narrator=False,
        sex="female",
        age="young",
        voice_id="v_alice",
    ))
    narrator = registry.get(narr_id)
    assert narrator is not None
    narrator.voice_id = "v_narr"

    return Book(
        metadata=BookMetadata(
            title="Test Book",
            author="Test Author",
            language="en",
            releaseDate=None,
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(number=1, title="Chapter 1", sections=[
                Section(text="Test section.", section_type=None, beats=[
                    Beat(
                        text="Once upon a time.",
                        beat_type=BeatType.NARRATION,
                        character_id=narr_id,
                    ),
                    Beat(
                        text="Hello, world!",
                        beat_type=BeatType.DIALOGUE,
                        character_id=alice_id,
                    ),
                ])
            ])
        ]),
        character_registry=registry,
    )


def test_run_synthesises_narratable_beats_via_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTSWorkflow.run() calls provide() on each narratable beat."""
    # Arrange
    book = _make_book("Test Book - Test Author")
    book_id = generate_book_id(book.metadata)
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book, book_id)
    _patch_resolver(monkeypatch, book_id)

    stub_provider = StubTTSProvider()
    character_provider = _StubCharacterProvider({
        build_character_id(book_id, NARRATOR_NAME): "v_narr",
        f"{book_id}:alice": "v_alice",
    })

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=character_provider,
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert stub_provider._provide_call_count == 2


def test_run_skips_non_narratable_beats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTSWorkflow.run() skips SOUND_EFFECT beats."""
    # Arrange
    metadata = BookMetadata(
        title="Test Book", author="Author", language="en",
        releaseDate=None, originalPublication=None, credits=None,
    )
    book_id = generate_book_id(metadata)
    registry = CharacterRegistry.with_default_narrator(book_id)
    narrator = registry.get(build_character_id(book_id, NARRATOR_NAME))
    assert narrator is not None
    narrator.voice_id = "v_narr"
    book = Book(
        metadata=metadata,
        content=BookContent(chapters=[
            Chapter(number=1, title="Ch1", sections=[
                Section(text="sfx", beats=[
                    Beat(text="boom", beat_type=BeatType.SOUND_EFFECT),
                ])
            ])
        ]),
        character_registry=registry,
    )
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book, book_id)
    _patch_resolver(monkeypatch, book_id)

    stub_provider = StubTTSProvider()
    character_provider = _StubCharacterProvider({build_character_id(book_id, NARRATOR_NAME): "v_narr"})

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=character_provider,
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert stub_provider._provide_call_count == 0


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTSWorkflow.run() raises ValueError when book_id not found."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent-book-id")
    stub_provider = StubTTSProvider()
    character_provider = _StubCharacterProvider({})

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=character_provider,
        books_dir=tmp_path,
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))


def test_run_raises_when_voice_map_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTSWorkflow.run() raises when the character provider returns no voices."""
    # Arrange
    book = _make_book("Test Book - Test Author")
    book_id = generate_book_id(book.metadata)
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book, book_id)
    _patch_resolver(monkeypatch, book_id)

    stub_provider = StubTTSProvider()
    character_provider = _StubCharacterProvider({})

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=character_provider,
        books_dir=tmp_path,
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No voices registered"):
        workflow.run(WorkflowRequest(url=_URL))
