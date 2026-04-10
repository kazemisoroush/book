"""Tests for ElevenLabsTTSProvider — v2 SDK usage."""
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest

import src.tts.elevenlabs_tts_provider as provider_mod
from src.tts.elevenlabs_tts_provider import ElevenLabsTTSProvider


def _make_mock_client(
    chunks: list[bytes] | None = None,
    request_id: str | None = "test-req-id",
) -> MagicMock:
    """Create a mock ElevenLabs client with with_raw_response.convert as context manager.

    Returns a mock where ``client.text_to_speech.with_raw_response.convert``
    is a context manager yielding an object with ``.headers`` and ``.data``.
    Call args are inspectable via ``client.text_to_speech.with_raw_response.convert.call_args``.
    """
    if chunks is None:
        chunks = [b"audio"]

    mock_client = MagicMock()
    raw_convert = mock_client.text_to_speech.with_raw_response.convert

    @contextmanager
    def _convert_cm(*args: object, **kwargs: object) -> Iterator[MagicMock]:
        response = MagicMock()
        headers: dict[str, str] = {}
        if request_id is not None:
            headers["request-id"] = request_id
        response.headers = headers
        response.data = iter(chunks)
        yield response

    # Use side_effect so MagicMock still records call_args
    raw_convert.side_effect = _convert_cm
    return mock_client


class TestElevenLabsTTSProviderSynthesize:
    """Tests for synthesize() using the v2 ElevenLabs SDK."""

    def _make_provider(self) -> ElevenLabsTTSProvider:
        return ElevenLabsTTSProvider(api_key="test-api-key")

    def test_synthesize_calls_text_to_speech_convert(self, tmp_path: Path) -> None:
        """synthesize() must call with_raw_response.convert with voice_id and text."""
        # Arrange
        provider = self._make_provider()
        mock_client = _make_mock_client()
        provider._client = mock_client
        output_path = tmp_path / "out.mp3"

        # Act
        provider.synthesize("Hello world", "voice123", output_path)

        # Assert
        convert = mock_client.text_to_speech.with_raw_response.convert
        convert.assert_called_once()
        call_args = convert.call_args
        assert call_args.args[0] == "voice123"
        assert call_args.kwargs.get("text") == "Hello world"

    def test_synthesize_uses_default_model(self, tmp_path: Path) -> None:
        """synthesize() must use the active _MODEL_ID (eleven_multilingual_v2 by default)."""
        # Arrange
        provider = self._make_provider()
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("Some text", "voice_abc", tmp_path / "out.mp3")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs.get("model_id") == "eleven_multilingual_v2"

    def test_synthesize_writes_chunks_to_output_path(self, tmp_path: Path) -> None:
        """synthesize() must write all bytes from the response data to output_path."""
        # Arrange
        provider = self._make_provider()
        mock_client = _make_mock_client(chunks=[b"chunk1", b"chunk2", b"chunk3"])
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
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("Test", "vid", tmp_path / "out.mp3")

        # Assert
        mock_client.generate.assert_not_called()


# ── Voice settings presets ────────────────────────────────────────────────────


class TestElevenLabsTTSProviderVoiceSettings:
    """Tests for voice-settings preset selection."""

    def test_emotional_preset_used_for_non_neutral_emotion(self, tmp_path: Path) -> None:
        """Emotional preset (stability=0.35, style=0.40) is used for non-neutral emotion."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("Rage!", "voice123", tmp_path / "out.mp3", emotion="angry")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        voice_settings = call_kwargs.get("voice_settings")
        assert voice_settings is not None
        assert voice_settings.stability == 0.35
        assert voice_settings.style == 0.40

    def test_neutral_preset_used_for_neutral_emotion(self, tmp_path: Path) -> None:
        """Neutral preset (stability=0.65, style=0.05) is used when emotion is 'neutral'."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("She walked in.", "voice123", tmp_path / "out.mp3", emotion="neutral")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        voice_settings = call_kwargs.get("voice_settings")
        assert voice_settings is not None
        assert voice_settings.stability == 0.65
        assert voice_settings.style == 0.05

    def test_neutral_preset_used_for_none_emotion(self, tmp_path: Path) -> None:
        """Neutral preset (stability=0.65, style=0.05) is used when emotion is None."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("It was a dark night.", "voice123", tmp_path / "out.mp3", emotion=None)

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        voice_settings = call_kwargs.get("voice_settings")
        assert voice_settings is not None
        assert voice_settings.stability == 0.65
        assert voice_settings.style == 0.05

    def test_synthesize_preserves_allcaps_text_unchanged(self, tmp_path: Path) -> None:
        """The provider must not modify ALL-CAPS text — it was already uppercased by the parser."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("I told you NEVER to return!", "voice123", tmp_path / "out.mp3")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert "NEVER" in call_kwargs["text"]


# ── Model capability: inline tags (v3 only) ──────────────────────────────────


class TestElevenLabsTTSProviderInlineTags:
    """Tests for inline audio tag behaviour gated by model capabilities."""

    def test_v3_prepends_audio_tag_for_emotion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, emotion='angry' prepends '[angry] ' to text."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("I refuse!", "voice123", tmp_path / "out.mp3", emotion="angry")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["text"].startswith("[angry] ")

    def test_v2_does_not_prepend_audio_tag(self, tmp_path: Path) -> None:
        """With eleven_multilingual_v2 (default), no inline tag is prepended."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("I refuse!", "voice123", tmp_path / "out.mp3", emotion="angry")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert not call_kwargs["text"].startswith("[")

    def test_v3_does_not_prepend_tag_for_neutral(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, neutral emotion does not prepend a tag."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("She walked in.", "voice123", tmp_path / "out.mp3", emotion="neutral")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert not call_kwargs["text"].startswith("[")

    def test_v3_lowercases_emotion_tag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, emotion='ANGRY' is lowercased to '[angry] '."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("Rage!", "voice123", tmp_path / "out.mp3", emotion="ANGRY")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["text"].startswith("[angry] ")


# ── Model capability: context params (v2 only for now) ───────────────────────


class TestElevenLabsTTSProviderContextParams:
    """Tests for previous_text and next_text passthrough (US-019 Fix 1)."""

    def test_previous_text_passed_to_sdk(self, tmp_path: Path) -> None:
        """synthesize(previous_text='Before.') passes previous_text to convert()."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "Current text.", "voice123", tmp_path / "out.mp3", previous_text="Before this.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["previous_text"] == "Before this."

    def test_next_text_passed_to_sdk(self, tmp_path: Path) -> None:
        """synthesize(next_text='After.') passes next_text to convert()."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "Current text.", "voice123", tmp_path / "out.mp3", next_text="After this.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["next_text"] == "After this."

    def test_both_context_params_passed_together(self, tmp_path: Path) -> None:
        """Both previous_text and next_text are forwarded when provided."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "Middle text.", "voice123", tmp_path / "out.mp3",
            previous_text="Before.", next_text="After.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["previous_text"] == "Before."
        assert call_kwargs["next_text"] == "After."

    def test_none_context_params_not_passed_to_sdk(self, tmp_path: Path) -> None:
        """When previous_text and next_text are None, they are not in the SDK call kwargs."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("Solo text.", "voice123", tmp_path / "out.mp3")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert "previous_text" not in call_kwargs
        assert "next_text" not in call_kwargs

    def test_v3_does_not_send_context_params(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, context params are NOT sent even when provided."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "Text.", "voice123", tmp_path / "out.mp3",
            previous_text="Before.", next_text="After.",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert "previous_text" not in call_kwargs
        assert "next_text" not in call_kwargs


# ── LLM-provided voice settings (US-019 Fix 3) ──────────────────────────────


class TestElevenLabsTTSProviderLLMVoiceSettings:
    """Tests for LLM-provided voice_stability/voice_style passthrough."""

    def test_llm_voice_settings_used_when_provided(self, tmp_path: Path) -> None:
        """voice_stability and voice_style from LLM are forwarded to VoiceSettings."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "I WILL DESTROY YOU!", "voice123", tmp_path / "out.mp3",
            voice_stability=0.25, voice_style=0.60,
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        vs = call_kwargs["voice_settings"]
        assert vs.stability == 0.25
        assert vs.style == 0.60

    def test_none_voice_settings_falls_back_to_binary_emotional(self, tmp_path: Path) -> None:
        """When voice settings are None, emotion='angry' uses old emotional preset."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "Rage!", "voice123", tmp_path / "out.mp3",
            emotion="angry",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        vs = call_kwargs["voice_settings"]
        assert vs.stability == 0.35
        assert vs.style == 0.40

    def test_none_voice_settings_falls_back_to_binary_neutral(self, tmp_path: Path) -> None:
        """When voice settings are None, emotion=None uses old neutral preset."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "It was quiet.", "voice123", tmp_path / "out.mp3",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        vs = call_kwargs["voice_settings"]
        assert vs.stability == 0.65
        assert vs.style == 0.05

    def test_voice_settings_override_emotion_based_logic(self, tmp_path: Path) -> None:
        """LLM voice settings take priority over emotion-based binary logic."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act — emotion says "angry" but LLM says mild settings
        provider.synthesize(
            "Hmm.", "voice123", tmp_path / "out.mp3",
            emotion="angry", voice_stability=0.50, voice_style=0.20,
        )

        # Assert — LLM values win
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        vs = call_kwargs["voice_settings"]
        assert vs.stability == 0.50
        assert vs.style == 0.20


# -- US-019 Fix 2: previous_request_ids chaining --------------------------


class TestElevenLabsTTSProviderRequestIdChaining:
    """Tests for previous_request_ids passthrough and request ID extraction."""

    def test_previous_request_ids_passed_to_sdk(self, tmp_path: Path) -> None:
        """When previous_request_ids is provided, it is forwarded to convert()."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "Hello.", "voice123", tmp_path / "out.mp3",
            previous_request_ids=["req-1", "req-2"],
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["previous_request_ids"] == ["req-1", "req-2"]

    def test_previous_request_ids_not_sent_when_none(self, tmp_path: Path) -> None:
        """When previous_request_ids is None, it is not in the SDK call kwargs."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("Hello.", "voice123", tmp_path / "out.mp3")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert "previous_request_ids" not in call_kwargs

    def test_previous_request_ids_not_sent_for_v3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With eleven_v3, previous_request_ids is NOT sent even when provided."""
        # Arrange
        monkeypatch.setattr(provider_mod, "_MODEL_ID", "eleven_v3")
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "Hello.", "voice123", tmp_path / "out.mp3",
            previous_request_ids=["req-1"],
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert "previous_request_ids" not in call_kwargs

    def test_synthesize_returns_request_id_from_response(self, tmp_path: Path) -> None:
        """synthesize() returns the request ID string from the response headers."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client(request_id="abc-123")
        provider._client = mock_client

        # Act
        result = provider.synthesize("Hello.", "voice123", tmp_path / "out.mp3")

        # Assert
        assert result == "abc-123"

    def test_synthesize_returns_none_when_no_request_id_header(self, tmp_path: Path) -> None:
        """synthesize() returns None when request-id header is absent."""
        # Arrange
        provider = ElevenLabsTTSProvider(api_key="test-key")
        mock_client = _make_mock_client(request_id=None)
        provider._client = mock_client

        # Act
        result = provider.synthesize("Hello.", "voice123", tmp_path / "out.mp3")

        # Assert
        assert result is None
