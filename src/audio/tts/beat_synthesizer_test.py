"""Tests for BeatSynthesizer: pass the beat and context to the provider."""
from pathlib import Path
from unittest.mock import MagicMock

from src.audio.tts.beat_context_resolver import BeatContext
from src.audio.tts.beat_synthesizer import BeatSynthesizer
from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat, BeatType


class TestBeatSynthesizerPassthrough:
    """BeatSynthesizer forwards the beat and the context object to the provider."""

    def test_synthesize_beat_passes_beat_and_context(self, tmp_path: Path) -> None:
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-123"
        synthesizer = BeatSynthesizer(provider)

        beat = Beat(
            text="Hello, world!",
            beat_type=BeatType.NARRATION,
            character_id=1,
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
            beat, "voice-1", output_path, context,
        )
        assert request_id == "request-123"
