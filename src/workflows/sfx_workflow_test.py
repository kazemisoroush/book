"""Tests for SfxWorkflow."""
from pathlib import Path

import pytest

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
    Segment,
    SegmentType,
)
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.workflows.sfx_workflow import SfxWorkflow


class StubSfxProvider(SoundEffectProvider):
    """Test stub that sets segment.audio_path and returns a fixed duration."""

    def __init__(self, fixed_duration: float = 1.5) -> None:
        self._fixed_duration = fixed_duration
        self.provide_call_count = 0

    def provide(self, segment: "Segment", book_id: str) -> float:
        self.provide_call_count += 1
        segment.audio_path = f"books/{book_id}/audio/sfx/seg_{self.provide_call_count:04d}.mp3"
        return self._fixed_duration

    def _generate(self, description: str, output_path: Path, duration_seconds: float = 2.0) -> Path | None:
        raise NotImplementedError


def _make_sfx_book() -> Book:
    return Book(
        metadata=BookMetadata(
            title="SFX Book", author="Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(number=1, title="Ch1", sections=[
                Section(text="sounds", segments=[
                    Segment(text="door knock", segment_type=SegmentType.SOUND_EFFECT),
                    Segment(text="sigh", segment_type=SegmentType.VOCAL_EFFECT),
                    Segment(text="narration", segment_type=SegmentType.NARRATION, character_id="narrator"),
                ])
            ])
        ]),
    )


def test_run_calls_provider_for_sfx_and_vocal_segments(tmp_path: Path) -> None:
    """run() calls provide() for SOUND_EFFECT and VOCAL_EFFECT segments only."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_sfx_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    stub = StubSfxProvider(fixed_duration=1.5)
    workflow = SfxWorkflow(repository=repository, provider=stub, books_dir=tmp_path)

    # Act
    result = workflow.run(book_id=book_id)

    # Assert — 2 segments match (SOUND_EFFECT + VOCAL_EFFECT), narration skipped
    assert stub.provide_call_count == 2
    segments = result.content.chapters[0].sections[0].segments
    assert segments is not None
    assert segments[0].audio_path is not None
    assert segments[0].duration_seconds == 1.5
    assert segments[1].audio_path is not None
    assert segments[1].duration_seconds == 1.5
    assert segments[2].audio_path is None  # narration untouched


def test_run_saves_book_to_repository(tmp_path: Path) -> None:
    """run() persists the book with SFX audio paths back to the repository."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_sfx_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    stub = StubSfxProvider()
    workflow = SfxWorkflow(repository=repository, provider=stub, books_dir=tmp_path)

    # Act
    workflow.run(book_id=book_id)

    # Assert
    loaded = repository.load(book_id)
    assert loaded is not None
    segments = loaded.content.chapters[0].sections[0].segments
    assert segments is not None
    seg = segments[0]
    assert seg.audio_path is not None


def test_run_raises_when_book_not_found(tmp_path: Path) -> None:
    """run() raises ValueError when book_id not found in repository."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    stub = StubSfxProvider()
    workflow = SfxWorkflow(repository=repository, provider=stub, books_dir=tmp_path)

    # Act & Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(book_id="nonexistent")
