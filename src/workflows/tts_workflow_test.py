"""Tests for TTSWorkflow."""
from pathlib import Path

import pytest

from src.audio.tts.tts_provider import StubTTSProvider
from src.audio.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Character,
    CharacterRegistry,
    Section,
    Beat,
    BeatType,
)
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.workflows.tts_workflow import TTSWorkflow


def _make_book() -> Book:
    """Create a test book with two narratable segments."""
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


def test_run_synthesises_narratable_segments_via_provider(tmp_path: Path) -> None:
    """TTSWorkflow.run() calls provide() on each narratable segment and stores duration."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    stub_provider = StubTTSProvider(_make_voices(), fixed_duration=2.5)
    voice_assigner = VoiceAssigner(stub_provider)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        voice_assigner=voice_assigner,
        books_dir=tmp_path,
    )

    # Act
    result = workflow.run(book_id=book_id)

    # Assert
    segments = result.content.chapters[0].sections[0].beats
    assert segments is not None
    assert beats[0].audio_path is not None
    assert beats[0].duration_seconds == 2.5
    assert beats[1].audio_path is not None
    assert beats[1].duration_seconds == 2.5
    assert stub_provider._provide_call_count == 2


def test_run_saves_book_back_to_repository(tmp_path: Path) -> None:
    """TTSWorkflow saves book with audio metadata to repository after synthesis."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    stub_provider = StubTTSProvider(_make_voices())
    voice_assigner = VoiceAssigner(stub_provider)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        voice_assigner=voice_assigner,
        books_dir=tmp_path,
    )

    # Act
    workflow.run(book_id=book_id)

    # Assert
    loaded = repository.load(book_id)
    assert loaded is not None
    segments = loaded.content.chapters[0].sections[0].beats
    assert segments is not None
    first_seg = beats[0]
    assert first_seg.audio_path is not None
    assert first_seg.duration_seconds is not None


def test_run_skips_non_narratable_segments(tmp_path: Path) -> None:
    """TTSWorkflow.run() skips SOUND_EFFECT segments."""
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

    stub_provider = StubTTSProvider(_make_voices())
    voice_assigner = VoiceAssigner(stub_provider)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        voice_assigner=voice_assigner,
        books_dir=tmp_path,
    )

    # Act
    result = workflow.run(book_id=book_id)

    # Assert — provider was never called
    assert stub_provider._provide_call_count == 0
    segments = result.content.chapters[0].sections[0].beats
    assert segments is not None
    seg = beats[0]
    assert seg.audio_path is None


def test_run_raises_when_book_not_found(tmp_path: Path) -> None:
    """TTSWorkflow.run() raises ValueError when book_id not found."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
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
        workflow.run(book_id="nonexistent-book-id")


def test_create_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """create() raises ValueError when FISH_AUDIO_API_KEY is missing."""
    # Arrange
    from src.config import reload_config
    monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)
    reload_config()

    # Act & Assert
    with pytest.raises(ValueError, match="FISH_AUDIO_API_KEY"):
        TTSWorkflow.create()
