"""Tests for BeatSynthesizer: pass beat and context fields to the provider."""
from pathlib import Path
from unittest.mock import MagicMock

from src.audio.tts.beat_context_resolver import BeatContext
from src.audio.tts.beat_synthesizer import BeatSynthesizer
from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat, BeatType


class TestBeatSynthesizerPassthrough:
    """BeatSynthesizer forwards beat and context fields to the provider."""

    def test_synthesize_beat_passes_all_fields(self, tmp_path: Path) -> None:
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
        )

        output_path = tmp_path / "beat_0000.mp3"

        # Act
        request_id = synthesizer.synthesize_beat(beat, "voice-1", output_path, context)

        # Assert
        provider.synthesize.assert_called_once_with(
            "Hello, world!",
            "voice-1",
            output_path,
            emotion="happy",
            previous_text="Previous beat.",
            next_text="Next beat.",
            previous_request_ids=["req-1", "req-2"],
        )
        assert request_id == "request-123"

    def test_synthesize_beat_passes_none_emotion_through(self, tmp_path: Path) -> None:
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
        )

        output_path = tmp_path / "beat_0001.mp3"

        # Act
        synthesizer.synthesize_beat(beat, "voice-2", output_path, context)

        # Assert
        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["emotion"] is None
