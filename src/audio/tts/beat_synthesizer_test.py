"""Tests for BeatSynthesizer — provider calls and passthrough behavior.

These tests verify:
  - BeatSynthesizer passes all beat attributes through to the provider
  - synthesize_beat() returns the request_id from provider
"""
from pathlib import Path
from unittest.mock import MagicMock

from src.audio.tts.beat_context_resolver import BeatContext
from src.audio.tts.beat_synthesizer import BeatSynthesizer
from src.audio.tts.tts_provider import TTSProvider
from src.domain.models import Beat, BeatType


class TestBeatSynthesizerPassthrough:
    """BeatSynthesizer passes all attributes through to the provider."""

    def test_synthesize_beat_passes_all_fields(self, tmp_path: Path) -> None:
        """All beat and context fields are passed through to provider."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-123"
        synthesizer = BeatSynthesizer(provider)

        beat = Beat(
            text="Hello, world!",
            beat_type=BeatType.NARRATION,
            character_id="narrator",
            emotion="happy",
        )
        context = BeatContext(
            previous_text="Previous beat.",
            next_text="Next beat.",
            previous_request_ids=["req-1", "req-2"],
            voice_stability=0.5,
            voice_style=0.7,
            voice_speed=0.8,
        )

        output_path = tmp_path / "beat_0000.mp3"

        # Act
        request_id = synthesizer.synthesize_beat(
            beat, "voice-1", output_path, context
        )

        # Assert
        provider.synthesize.assert_called_once_with(
            "Hello, world!",
            "voice-1",
            output_path,
            emotion="happy",
            previous_text="Previous beat.",
            next_text="Next beat.",
            voice_stability=0.5,
            voice_style=0.7,
            voice_speed=0.8,
            previous_request_ids=["req-1", "req-2"],
        )
        assert request_id == "request-123"

    def test_synthesize_beat_passes_none_emotion_through(self, tmp_path: Path) -> None:
        """When beat has no emotion, None is passed through to provider."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-456"
        synthesizer = BeatSynthesizer(provider)

        beat = Beat(
            text="Plain text.",
            beat_type=BeatType.NARRATION,
            character_id="narrator",
        )
        context = BeatContext(
            previous_text=None,
            next_text=None,
            previous_request_ids=None,
            voice_stability=0.65,
            voice_style=0.05,
            voice_speed=1.0,
        )

        output_path = tmp_path / "beat_0001.mp3"

        # Act
        request_id = synthesizer.synthesize_beat(
            beat, "voice-2", output_path, context
        )

        # Assert
        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["emotion"] is None
        assert call_kwargs["voice_stability"] == 0.65
        assert request_id == "request-456"


class TestBeatSynthesizerContextPassthrough:
    """Verify context fields are passed through unchanged."""

    def test_synthesize_beat_passes_all_context_fields(
        self, tmp_path: Path
    ) -> None:
        """All context fields are passed to provider.synthesize()."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-ctx"
        synthesizer = BeatSynthesizer(provider)

        beat = Beat(
            text="Test",
            beat_type=BeatType.DIALOGUE,
            character_id="char-1",
        )
        context = BeatContext(
            previous_text="p1",
            next_text="n1",
            previous_request_ids=["r1", "r2", "r3"],
            voice_stability=0.1,
            voice_style=0.2,
            voice_speed=0.3,
        )

        output_path = tmp_path / "beat_ctx.mp3"

        # Act
        synthesizer.synthesize_beat(beat, "v-ctx", output_path, context)

        # Assert
        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["previous_text"] == "p1"
        assert call_kwargs["next_text"] == "n1"
        assert call_kwargs["previous_request_ids"] == ["r1", "r2", "r3"]
