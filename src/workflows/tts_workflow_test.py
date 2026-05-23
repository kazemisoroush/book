"""Tests for TTSWorkflow."""
from pathlib import Path

import pytest

from src.audio.tts.tts_provider import StubTTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.domain.beat import Beat, BeatType
from src.domain.models import (
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


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.tts_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _make_book() -> Book:
    """Create a test book with two narratable beats."""
    registry = CharacterRegistry.with_default_narrator()
    registry.add(Character(
        character_id="alice",
        name="Alice",
        description="A young girl",
        is_narrator=False,
        sex="female",
        age="young",
    ))

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
                        character_id="narrator",
                    ),
                    Beat(
                        text="Hello, world!",
                        beat_type=BeatType.DIALOGUE,
                        character_id="alice",
                    ),
                ])
            ])
        ]),
        character_registry=registry,
    )


def _make_voices() -> list[VoiceEntry]:
    return [
        VoiceEntry(voice_id="v1", name="Voice 1", labels={}),
        VoiceEntry(voice_id="v2", name="Voice 2", labels={}),
    ]


def test_run_synthesises_narratable_beats_via_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTSWorkflow.run() calls provide() on each narratable beat and stores duration."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)
    _patch_resolver(monkeypatch, book_id)

    stub_provider = StubTTSProvider(_make_voices(), fixed_duration=2.5)
    voice_assigner = VoiceAssigner(stub_provider)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        voice_assigner=voice_assigner,
        books_dir=tmp_path,
    )

    # Act
    result = workflow.run(WorkflowRequest(url=_URL))

    # Assert
    beats = result.content.chapters[0].sections[0].beats
    assert beats is not None
    assert beats[0].audio_path is not None
    assert beats[0].duration_seconds == 2.5
    assert beats[1].audio_path is not None
    assert beats[1].duration_seconds == 2.5
    assert stub_provider._provide_call_count == 2


def test_run_skips_non_narratable_beats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTSWorkflow.run() skips SOUND_EFFECT beats."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = Book(
        metadata=BookMetadata(
            title="Test Book", author="Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(number=1, title="Ch1", sections=[
                Section(text="sfx", beats=[
                    Beat(text="boom", beat_type=BeatType.SOUND_EFFECT),
                ])
            ])
        ]),
    )
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)
    _patch_resolver(monkeypatch, book_id)

    stub_provider = StubTTSProvider(_make_voices())
    voice_assigner = VoiceAssigner(stub_provider)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        voice_assigner=voice_assigner,
        books_dir=tmp_path,
    )

    # Act
    result = workflow.run(WorkflowRequest(url=_URL))

    # Assert — provider was never called
    assert stub_provider._provide_call_count == 0
    beats = result.content.chapters[0].sections[0].beats
    assert beats is not None
    seg = beats[0]
    assert seg.audio_path is None


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTSWorkflow.run() raises ValueError when book_id not found."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent-book-id")
    stub_provider = StubTTSProvider(_make_voices())
    voice_assigner = VoiceAssigner(stub_provider)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        voice_assigner=voice_assigner,
        books_dir=tmp_path,
    )

    # Act & Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))
