"""Tests for TTSOrchestrator — emotion wiring."""
from pathlib import Path
from unittest.mock import MagicMock

from src.domain.models import (
    Book, BookContent, BookMetadata, Chapter, Section, Segment, SegmentType,
    CharacterRegistry,
)
from src.tts.tts_orchestrator import TTSOrchestrator


def _make_book_with_segment(segment: Segment) -> Book:
    section = Section(text="Test.", segments=[segment])
    chapter = Chapter(number=1, title="Chapter I", sections=[section])
    metadata = BookMetadata(
        title="T", author=None, releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    return Book(
        metadata=metadata,
        content=BookContent(chapters=[chapter]),
        character_registry=CharacterRegistry.with_default_narrator(),
    )


class TestTTSOrchestratorEmotionWiring:
    """TTSOrchestrator passes segment.emotion to the TTS provider."""

    def test_orchestrator_passes_emotion_value_to_provider(self, tmp_path: Path) -> None:
        """synthesize_chapter() must pass emotion string to provider.synthesize()."""
        # Arrange
        segment = Segment(
            text="I told you NEVER to return!",
            segment_type=SegmentType.DIALOGUE,
            character_id="villain",
            emotion="angry",
        )
        book = _make_book_with_segment(segment)
        voice_assignment = {"villain": "voice123", "narrator": "voice000"}

        mock_provider = MagicMock()
        mock_provider.synthesize.return_value = None

        orchestrator = TTSOrchestrator(mock_provider, output_dir=tmp_path)
        orchestrator._stitch_with_ffmpeg = MagicMock()  # type: ignore[method-assign]

        # Act
        orchestrator.synthesize_chapter(book, chapter_number=1, voice_assignment=voice_assignment)

        # Assert
        call_kwargs = mock_provider.synthesize.call_args.kwargs
        assert call_kwargs.get("emotion") == "angry"

    def test_orchestrator_passes_none_emotion_for_narration_segments(
        self, tmp_path: Path
    ) -> None:
        """synthesize_chapter() must pass emotion=None for narrator segments."""
        # Arrange
        segment = Segment(
            text="It was a dark and stormy night.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
            emotion=None,
        )
        book = _make_book_with_segment(segment)
        voice_assignment = {"narrator": "voice000"}

        mock_provider = MagicMock()
        mock_provider.synthesize.return_value = None

        orchestrator = TTSOrchestrator(mock_provider, output_dir=tmp_path)
        orchestrator._stitch_with_ffmpeg = MagicMock()  # type: ignore[method-assign]

        # Act
        orchestrator.synthesize_chapter(book, chapter_number=1, voice_assignment=voice_assignment)

        # Assert
        call_kwargs = mock_provider.synthesize.call_args.kwargs
        assert call_kwargs.get("emotion") is None
