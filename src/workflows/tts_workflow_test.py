"""Tests for TTSWorkflow."""
from pathlib import Path

import pytest

from src.audio.tts.tts_provider import StubTTSProvider
from src.characters.character_provider import CharacterProvider
from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_ID, Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
)
from src.repository.file_book_repository import FileBookRepository
from src.workflows.tts_workflow import TTSWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"
_ALICE_ID = 2


class _UnusedCharacterProvider(CharacterProvider):
    """Satisfies the constructor type; TTSWorkflow no longer calls it."""

    def upsert(
        self, character: Character, book_id: str, refresh: bool = False,
    ) -> str:
        raise AssertionError("upsert should not be called by TTSWorkflow")


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.tts_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _make_book(voice_assignments: dict[int, str] | None = None) -> Book:
    registry = CharacterRegistry(characters=[make_default_narrator()])
    registry.add(Character(
        id=_ALICE_ID, name="Alice",
        gender="female", age="young", accent="british",
    ))
    chapter = Chapter(
        number=1, title="Chapter 1",
        beats=[
            Beat(text="Once upon a time.", beat_type=BeatType.NARRATION, character_id=NARRATOR_ID),
            Beat(text="Hello, world!", beat_type=BeatType.DIALOGUE, character_id=_ALICE_ID),
        ],
    )
    return Book(
        metadata=BookMetadata(
            title="Test Book", author="Test Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[chapter]),
        character_registry=registry,
        voice_assignments=voice_assignments or {},
    )


def _two_chapter_book(voices: dict[int, str]) -> Book:
    registry = CharacterRegistry(characters=[make_default_narrator()])
    return Book(
        metadata=BookMetadata(
            title="Test Book", author="Test Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(
                number=1, title="Chapter 1",
                beats=[Beat(
                    text="Ch1 beat.", beat_type=BeatType.NARRATION,
                    character_id=NARRATOR_ID,
                )],
            ),
            Chapter(
                number=2, title="Chapter 2",
                beats=[Beat(
                    text="Ch2 beat.", beat_type=BeatType.NARRATION,
                    character_id=NARRATOR_ID,
                )],
            ),
        ]),
        character_registry=registry,
        voice_assignments=voices,
    )


def test_run_hands_each_chapter_beat_list_to_the_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _make_book({NARRATOR_ID: "v_narr", _ALICE_ID: "v_alice"})
    store = FileBookRepository(base_dir=str(tmp_path))
    store.save(book)
    _patch_resolver(monkeypatch, book.book_id)
    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repositories=[store],
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert len(stub_provider.collection_calls) == 1
    handed_off = stub_provider.collection_calls[0].beats
    assert [b.text for b in handed_off] == ["Once upon a time.", "Hello, world!"]


def test_run_stamps_voice_id_on_each_narratable_beat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _make_book({NARRATOR_ID: "v_narr", _ALICE_ID: "v_alice"})
    store = FileBookRepository(base_dir=str(tmp_path))
    store.save(book)
    _patch_resolver(monkeypatch, book.book_id)
    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repositories=[store],
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    handed_off = stub_provider.collection_calls[0].beats
    assert handed_off[0].voice_id == "v_narr"
    assert handed_off[1].voice_id == "v_alice"


def test_run_respects_chapter_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _two_chapter_book({NARRATOR_ID: "v_narr"})
    store = FileBookRepository(base_dir=str(tmp_path))
    store.save(book)
    _patch_resolver(monkeypatch, book.book_id)
    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repositories=[store],
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL, start_chapter=2, end_chapter=2))

    # Assert
    assert len(stub_provider.collection_calls) == 1
    assert [b.text for b in stub_provider.collection_calls[0].beats] == ["Ch2 beat."]


def test_run_leaves_non_narratable_beats_without_voice_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    metadata = BookMetadata(
        title="Test Book", author="Author", language="en",
        releaseDate=None, originalPublication=None, credits=None,
    )
    registry = CharacterRegistry(characters=[make_default_narrator()])
    book = Book(
        metadata=metadata,
        content=BookContent(chapters=[
            Chapter(
                number=1, title="Ch1",
                beats=[
                    Beat(text="boom", beat_type=BeatType.SOUND_EFFECT),
                    Beat(
                        text="Hi.", beat_type=BeatType.NARRATION,
                        character_id=NARRATOR_ID,
                    ),
                ],
            ),
        ]),
        character_registry=registry,
        voice_assignments={NARRATOR_ID: "v_narr"},
    )
    store = FileBookRepository(base_dir=str(tmp_path))
    store.save(book)
    _patch_resolver(monkeypatch, book.book_id)
    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repositories=[store],
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    handed_off = stub_provider.collection_calls[0].beats
    assert handed_off[0].voice_id is None
    assert handed_off[1].voice_id == "v_narr"


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store = FileBookRepository(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent-book-id")
    workflow = TTSWorkflow(
        repositories=[store],
        tts_provider=StubTTSProvider(),
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))


def test_run_raises_when_voice_assignments_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _make_book()
    store = FileBookRepository(base_dir=str(tmp_path))
    store.save(book)
    _patch_resolver(monkeypatch, book.book_id)
    workflow = TTSWorkflow(
        repositories=[store],
        tts_provider=StubTTSProvider(),
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No voices registered"):
        workflow.run(WorkflowRequest(url=_URL))
