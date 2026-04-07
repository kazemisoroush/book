"""Tests for SegmentSynthesizer — feature flag gating and provider calls.

These tests verify:
  - SegmentSynthesizer applies emotion/voice_design feature flags correctly
  - Feature flags are read from TTSOrchestrator constants (not constructor params)
  - provider.synthesize() is called with correct parameters
  - synthesize_segment() returns the request_id from provider
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.domain.models import Segment, SegmentType
from src.tts.segment_context_resolver import SegmentContext
from src.tts.segment_synthesizer import SegmentSynthesizer
from src.tts.tts_provider import TTSProvider


class TestSegmentSynthesizerWithAllFlagsEnabled:
    """When all feature flags are enabled, all segment attributes are passed."""

    def test_synthesize_segment_with_all_flags_enabled(self, tmp_path: Path) -> None:
        """With all flags enabled, emotion and voice design fields are passed."""
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
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch_class:
            mock_orch_class.EMOTION_ENABLED = True
            mock_orch_class.VOICE_DESIGN_ENABLED = True
            mock_orch_class.SCENE_CONTEXT_ENABLED = True
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


class TestSegmentSynthesizerEmotionDisabled:
    """When emotion_enabled=False, emotion is not passed."""

    def test_synthesize_segment_emotion_disabled(self, tmp_path: Path) -> None:
        """With EMOTION_ENABLED=False, emotion=None is passed."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-456"
        synthesizer = SegmentSynthesizer(provider)

        segment = Segment(
            text="Angry dialogue",
            segment_type=SegmentType.DIALOGUE,
            character_id="villain",
            emotion="angry",
        )
        context = SegmentContext(
            previous_text=None,
            next_text=None,
            previous_request_ids=None,
            voice_stability=0.5,
            voice_style=0.7,
            voice_speed=0.8,
        )

        output_path = tmp_path / "seg_0001.mp3"

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch_class:
            mock_orch_class.EMOTION_ENABLED = False
            mock_orch_class.VOICE_DESIGN_ENABLED = True
            mock_orch_class.SCENE_CONTEXT_ENABLED = True
            request_id = synthesizer.synthesize_segment(
                segment, "voice-2", output_path, context
            )

        # Assert
        provider.synthesize.assert_called_once_with(
            "Angry dialogue",
            "voice-2",
            output_path,
            emotion=None,  # emotion disabled, so None
            previous_text=None,
            next_text=None,
            voice_stability=0.5,
            voice_style=0.7,
            voice_speed=0.8,
            previous_request_ids=None,
        )
        assert request_id == "request-456"


class TestSegmentSynthesizerVoiceDesignDisabled:
    """When voice_design_enabled=False, voice design fields are not passed."""

    def test_synthesize_segment_voice_design_disabled(self, tmp_path: Path) -> None:
        """With VOICE_DESIGN_ENABLED=False, voice_stability/style/speed=None."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-789"
        synthesizer = SegmentSynthesizer(provider)

        segment = Segment(
            text="Narration",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
            emotion="neutral",
        )
        context = SegmentContext(
            previous_text="Context before.",
            next_text="Context after.",
            previous_request_ids=["req-0"],
            voice_stability=0.5,
            voice_style=0.7,
            voice_speed=0.8,
        )

        output_path = tmp_path / "seg_0002.mp3"

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch_class:
            mock_orch_class.EMOTION_ENABLED = True
            mock_orch_class.VOICE_DESIGN_ENABLED = False
            mock_orch_class.SCENE_CONTEXT_ENABLED = True
            request_id = synthesizer.synthesize_segment(
                segment, "voice-3", output_path, context
            )

        # Assert
        provider.synthesize.assert_called_once_with(
            "Narration",
            "voice-3",
            output_path,
            emotion="neutral",
            previous_text="Context before.",
            next_text="Context after.",
            voice_stability=None,  # voice design disabled
            voice_style=None,      # voice design disabled
            voice_speed=None,      # voice design disabled
            previous_request_ids=["req-0"],
        )
        assert request_id == "request-789"


class TestSegmentSynthesizerAllFlagsDisabled:
    """When all feature flags disabled, all optional fields are None."""

    def test_synthesize_segment_all_flags_disabled(self, tmp_path: Path) -> None:
        """With all flags disabled, emotion and voice design are None."""
        # Arrange
        provider = MagicMock(spec=TTSProvider)
        provider.synthesize.return_value = "request-all-disabled"
        synthesizer = SegmentSynthesizer(provider)

        segment = Segment(
            text="Pure text",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
            emotion="sad",
        )
        context = SegmentContext(
            previous_text="Previous.",
            next_text="Next.",
            previous_request_ids=["req-prev"],
            voice_stability=0.9,
            voice_style=0.6,
            voice_speed=1.2,
        )

        output_path = tmp_path / "seg_0003.mp3"

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch_class:
            mock_orch_class.EMOTION_ENABLED = False
            mock_orch_class.VOICE_DESIGN_ENABLED = False
            mock_orch_class.SCENE_CONTEXT_ENABLED = False
            request_id = synthesizer.synthesize_segment(
                segment, "voice-4", output_path, context
            )

        # Assert
        provider.synthesize.assert_called_once_with(
            "Pure text",
            "voice-4",
            output_path,
            emotion=None,
            previous_text="Previous.",
            next_text="Next.",
            voice_stability=None,
            voice_style=None,
            voice_speed=None,
            previous_request_ids=["req-prev"],
        )
        assert request_id == "request-all-disabled"


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
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch_class:
            mock_orch_class.EMOTION_ENABLED = True
            mock_orch_class.VOICE_DESIGN_ENABLED = True
            mock_orch_class.SCENE_CONTEXT_ENABLED = True
            synthesizer.synthesize_segment(segment, "v-ctx", output_path, context)

        # Assert
        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["previous_text"] == "p1"
        assert call_kwargs["next_text"] == "n1"
        assert call_kwargs["previous_request_ids"] == ["r1", "r2", "r3"]
