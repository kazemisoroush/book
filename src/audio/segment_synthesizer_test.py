"""Tests for SegmentSynthesizer — provider calls and passthrough behavior.

These tests verify:
  - SegmentSynthesizer passes all segment attributes through to the provider
  - synthesize_segment() returns the request_id from provider
"""
from pathlib import Path
from unittest.mock import MagicMock

from src.domain.models import Segment, SegmentType
from src.audio.segment_context_resolver import SegmentContext
from src.audio.segment_synthesizer import SegmentSynthesizer
from src.audio.tts_provider import TTSProvider


class TestSegmentSynthesizerPassthrough:
    """SegmentSynthesizer passes all attributes through to the provider."""

    def test_synthesize_segment_passes_all_fields(self, tmp_path: Path) -> None:
        """All segment and context fields are passed through to provider."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-123"
        synthesizer = SegmentSynthesizer(provider)

        segment = Segment(
            text="Hello, world!",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
            emotion="happy",
        )
        context = SegmentContext(
            previous_text="Previous segment.",
            next_text="Next segment.",
            previous_request_ids=["req-1", "req-2"],
            voice_stability=0.5,
            voice_style=0.7,
            voice_speed=0.8,
        )

        output_path = tmp_path / "seg_0000.mp3"

        # Act
        request_id = synthesizer.synthesize_segment(
            segment, "voice-1", output_path, context
        )

        # Assert
        provider.synthesize.assert_called_once_with(
            "Hello, world!",
            "voice-1",
            output_path,
            emotion="happy",
            previous_text="Previous segment.",
            next_text="Next segment.",
            voice_stability=0.5,
            voice_style=0.7,
            voice_speed=0.8,
            previous_request_ids=["req-1", "req-2"],
        )
        assert request_id == "request-123"

    def test_synthesize_segment_passes_none_emotion_through(self, tmp_path: Path) -> None:
        """When segment has no emotion, None is passed through to provider."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-456"
        synthesizer = SegmentSynthesizer(provider)

        segment = Segment(
            text="Plain text.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )
        context = SegmentContext(
            previous_text=None,
            next_text=None,
            previous_request_ids=None,
            voice_stability=0.65,
            voice_style=0.05,
            voice_speed=1.0,
        )

        output_path = tmp_path / "seg_0001.mp3"

        # Act
        request_id = synthesizer.synthesize_segment(
            segment, "voice-2", output_path, context
        )

        # Assert
        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["emotion"] is None
        assert call_kwargs["voice_stability"] == 0.65
        assert request_id == "request-456"


class TestSegmentSynthesizerContextPassthrough:
    """Verify context fields are passed through unchanged."""

    def test_synthesize_segment_passes_all_context_fields(
        self, tmp_path: Path
    ) -> None:
        """All context fields are passed to provider.synthesize()."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-ctx"
        synthesizer = SegmentSynthesizer(provider)

        segment = Segment(
            text="Test",
            segment_type=SegmentType.DIALOGUE,
            character_id="char-1",
        )
        context = SegmentContext(
            previous_text="p1",
            next_text="n1",
            previous_request_ids=["r1", "r2", "r3"],
            voice_stability=0.1,
            voice_style=0.2,
            voice_speed=0.3,
        )

        output_path = tmp_path / "seg_ctx.mp3"

        # Act
        synthesizer.synthesize_segment(segment, "v-ctx", output_path, context)

        # Assert
        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["previous_text"] == "p1"
        assert call_kwargs["next_text"] == "n1"
        assert call_kwargs["previous_request_ids"] == ["r1", "r2", "r3"]
