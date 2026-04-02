"""Tests for ElevenLabsProvider — v2 SDK usage."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import src.tts.elevenlabs_provider as provider_mod
from src.tts.elevenlabs_provider import ElevenLabsProvider


class TestElevenLabsProviderSynthesize:
    """Tests for synthesize() using the v2 ElevenLabs SDK."""

    def _make_provider(self) -> ElevenLabsProvider:
        return ElevenLabsProvider(api_key="test-api-key")

    def test_synthesize_calls_text_to_speech_convert(self, tmp_path: Path) -> None:
        """synthesize() must call client.text_to_speech.convert with voice_id and text."""
        # Arrange
        provider = self._make_provider()
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"audio_data"])
        provider._client = mock_client
        output_path = tmp_path / "out.mp3"

        # Act
        provider.synthesize("Hello world", "voice123", output_path)

        # Assert
        mock_client.text_to_speech.convert.assert_called_once()
        call_args = mock_client.text_to_speech.convert.call_args
        assert call_args.args[0] == "voice123"
        assert call_args.kwargs.get("text") == "Hello world"

    def test_synthesize_uses_default_model(self, tmp_path: Path) -> None:
        """synthesize() must use the active _MODEL_ID (eleven_multilingual_v2 by default)."""
        # Arrange
        provider = self._make_provider()
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"chunk"])
        provider._client = mock_client

        # Act
        provider.synthesize("Some text", "voice_abc", tmp_path / "out.mp3")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert call_kwargs.get("model_id") == "eleven_multilingual_v2"

    def test_synthesize_writes_chunks_to_output_path(self, tmp_path: Path) -> None:
        """synthesize() must write all bytes from the convert iterator to output_path."""
        # Arrange
        provider = self._make_provider()
        mock_client = MagicMock()
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_client.text_to_speech.convert.return_value = iter(chunks)
        provider._client = mock_client
        output_path = tmp_path / "out.mp3"

        # Act
        provider.synthesize("Text", "vid", output_path)

        # Assert
        assert output_path.exists()
        assert output_path.read_bytes() == b"chunk1chunk2chunk3"

    def test_synthesize_does_not_call_deprecated_generate(self, tmp_path: Path) -> None:
        """synthesize() must NOT call the deprecated client.generate()."""
        # Arrange
        provider = self._make_provider()
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"data"])
        provider._client = mock_client

        # Act
        provider.synthesize("Test", "vid", tmp_path / "out.mp3")

        # Assert
        mock_client.generate.assert_not_called()


# ── Voice settings presets ────────────────────────────────────────────────────


class TestElevenLabsProviderVoiceSettings:
    """Tests for voice-settings preset selection."""

    def _make_provider_with_mock_client(self) -> tuple[ElevenLabsProvider, MagicMock]:
        provider = ElevenLabsProvider(api_key="test-key")
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"audio"])
        provider._client = mock_client
        return provider, mock_client

    def test_emotional_preset_used_for_non_neutral_emotion(self, tmp_path: Path) -> None:
        """Emotional preset (stability=0.35, style=0.40) is used for non-neutral emotion."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("Rage!", "voice123", tmp_path / "out.mp3", emotion="angry")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        voice_settings = call_kwargs.get("voice_settings")
        assert voice_settings is not None
        assert voice_settings.stability == 0.35
        assert voice_settings.style == 0.40

    def test_neutral_preset_used_for_neutral_emotion(self, tmp_path: Path) -> None:
        """Neutral preset (stability=0.65, style=0.05) is used when emotion is 'neutral'."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("She walked in.", "voice123", tmp_path / "out.mp3", emotion="neutral")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        voice_settings = call_kwargs.get("voice_settings")
        assert voice_settings is not None
        assert voice_settings.stability == 0.65
        assert voice_settings.style == 0.05

    def test_neutral_preset_used_for_none_emotion(self, tmp_path: Path) -> None:
        """Neutral preset (stability=0.65, style=0.05) is used when emotion is None."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("It was a dark night.", "voice123", tmp_path / "out.mp3", emotion=None)

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        voice_settings = call_kwargs.get("voice_settings")
        assert voice_settings is not None
        assert voice_settings.stability == 0.65
        assert voice_settings.style == 0.05

    def test_synthesize_preserves_allcaps_text_unchanged(self, tmp_path: Path) -> None:
        """The provider must not modify ALL-CAPS text — it was already uppercased by the parser."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("I told you NEVER to return!", "voice123", tmp_path / "out.mp3")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert "NEVER" in call_kwargs["text"]


# ── Model capability: inline tags (v3 only) ──────────────────────────────────


class TestElevenLabsProviderInlineTags:
    """Tests for inline audio tag behaviour gated by model capabilities."""

    def _make_provider_with_mock_client(self) -> tuple[ElevenLabsProvider, MagicMock]:
        provider = ElevenLabsProvider(api_key="test-key")
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"audio"])
        provider._client = mock_client
        return provider, mock_client

    def test_v3_prepends_audio_tag_for_emotion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, emotion='angry' prepends '[angry] ' to text."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("I refuse!", "voice123", tmp_path / "out.mp3", emotion="angry")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert call_kwargs["text"].startswith("[angry] ")

    def test_v2_does_not_prepend_audio_tag(self, tmp_path: Path) -> None:
        """With eleven_multilingual_v2 (default), no inline tag is prepended."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("I refuse!", "voice123", tmp_path / "out.mp3", emotion="angry")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert not call_kwargs["text"].startswith("[")

    def test_v3_does_not_prepend_tag_for_neutral(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, neutral emotion does not prepend a tag."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("She walked in.", "voice123", tmp_path / "out.mp3", emotion="neutral")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert not call_kwargs["text"].startswith("[")

    def test_v3_lowercases_emotion_tag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, emotion='ANGRY' is lowercased to '[angry] '."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("Rage!", "voice123", tmp_path / "out.mp3", emotion="ANGRY")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert call_kwargs["text"].startswith("[angry] ")


# ── Model capability: context params (v2 only for now) ───────────────────────


class TestElevenLabsProviderContextParams:
    """Tests for previous_text and next_text passthrough (US-019 Fix 1)."""

    def _make_provider_with_mock_client(self) -> tuple[ElevenLabsProvider, MagicMock]:
        provider = ElevenLabsProvider(api_key="test-key")
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"audio"])
        provider._client = mock_client
        return provider, mock_client

    def test_previous_text_passed_to_sdk(self, tmp_path: Path) -> None:
        """synthesize(previous_text='Before.') passes previous_text to convert()."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize(
            "Current text.", "voice123", tmp_path / "out.mp3", previous_text="Before this.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert call_kwargs["previous_text"] == "Before this."

    def test_next_text_passed_to_sdk(self, tmp_path: Path) -> None:
        """synthesize(next_text='After.') passes next_text to convert()."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize(
            "Current text.", "voice123", tmp_path / "out.mp3", next_text="After this.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert call_kwargs["next_text"] == "After this."

    def test_both_context_params_passed_together(self, tmp_path: Path) -> None:
        """Both previous_text and next_text are forwarded when provided."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize(
            "Middle text.", "voice123", tmp_path / "out.mp3",
            previous_text="Before.", next_text="After.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert call_kwargs["previous_text"] == "Before."
        assert call_kwargs["next_text"] == "After."

    def test_none_context_params_not_passed_to_sdk(self, tmp_path: Path) -> None:
        """When previous_text and next_text are None, they are not in the SDK call kwargs."""
        # Arrange
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize("Solo text.", "voice123", tmp_path / "out.mp3")

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert "previous_text" not in call_kwargs
        assert "next_text" not in call_kwargs

    def test_v3_does_not_send_context_params(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, context params are NOT sent even when provided."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider, mock_client = self._make_provider_with_mock_client()

        # Act
        provider.synthesize(
            "Text.", "voice123", tmp_path / "out.mp3",
            previous_text="Before.", next_text="After.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert "previous_text" not in call_kwargs
        assert "next_text" not in call_kwargs
