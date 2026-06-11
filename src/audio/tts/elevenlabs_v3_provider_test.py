"""Tests for ElevenLabsV3Provider."""
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

from src.audio.tts.elevenlabs_v3_provider import (
    DEFAULT_VOICE_SETTINGS,
    ElevenLabsV3Provider,
)
from src.domain.voice_settings import VoiceSettings


def _make_mock_client(
    chunks: list[bytes] | None = None,
    request_id: str | None = "test-req-id",
) -> MagicMock:
    """Build a mock ElevenLabs client whose with_raw_response.convert is a context manager."""
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

    raw_convert.side_effect = _convert_cm
    return mock_client


def _make_provider() -> ElevenLabsV3Provider:
    return ElevenLabsV3Provider(api_key="test-key")


class TestName:
    """Provider name identifier."""

    def test_name_is_elevenlabs_v3(self) -> None:
        # Arrange
        provider = _make_provider()

        # Act & Assert
        assert provider.name == "elevenlabs_v3"


class TestSynthesizeCall:
    """Core synthesize() call shape."""

    def test_calls_convert_with_voice_id_text_model_and_writes_chunks(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client(chunks=[b"a", b"b", b"c"])
        provider._client = mock_client
        output_path = tmp_path / "out.mp3"

        # Act
        provider.synthesize("Hello world", "voice123", output_path)

        # Assert
        convert = mock_client.text_to_speech.with_raw_response.convert
        convert.assert_called_once()
        call_args = convert.call_args
        assert call_args.args[0] == "voice123"
        assert call_args.kwargs["text"] == "Hello world"
        assert call_args.kwargs["model_id"] == "eleven_v3"
        assert output_path.read_bytes() == b"abc"


class TestInlineEmotionTag:
    """V3 wraps free-form emotion as an inline audio tag."""

    def test_non_neutral_emotion_is_prepended_lowercased(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "I refuse!", "v1", tmp_path / "out.mp3", emotion="ANGRY",
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["text"] == "[angry] I refuse!"

    def test_neutral_or_none_emotion_does_not_prepend_a_tag(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("plain.", "v1", tmp_path / "a.mp3", emotion="neutral")
        provider.synthesize("plain.", "v1", tmp_path / "b.mp3", emotion=None)

        # Assert
        calls = mock_client.text_to_speech.with_raw_response.convert.call_args_list
        assert calls[0].kwargs["text"] == "plain."
        assert calls[1].kwargs["text"] == "plain."


class TestVoiceSettings:
    """Per-beat voice_settings override and default preset."""

    def test_default_preset_is_used_when_voice_settings_is_none(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize("hi", "v1", tmp_path / "out.mp3")

        # Assert
        vs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs["voice_settings"]
        assert vs.stability == DEFAULT_VOICE_SETTINGS.stability
        assert vs.style == DEFAULT_VOICE_SETTINGS.style
        assert vs.similarity_boost == DEFAULT_VOICE_SETTINGS.similarity_boost
        assert vs.use_speaker_boost is DEFAULT_VOICE_SETTINGS.use_speaker_boost

    def test_beat_voice_settings_override_default(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client()
        provider._client = mock_client
        override = VoiceSettings(
            stability=0.10,
            style=0.90,
            similarity_boost=0.55,
            use_speaker_boost=False,
        )

        # Act
        provider.synthesize(
            "hi", "v1", tmp_path / "out.mp3", voice_settings=override,
        )

        # Assert
        vs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs["voice_settings"]
        assert vs.stability == 0.10
        assert vs.style == 0.90
        assert vs.similarity_boost == 0.55
        assert vs.use_speaker_boost is False


class TestContextParamsNeverSent:
    """V3 must NOT forward context kwargs (the API would 400)."""

    def test_previous_next_request_ids_dropped(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.synthesize(
            "middle.", "v1", tmp_path / "out.mp3",
            previous_text="before.", next_text="after.",
            previous_request_ids=["r1"],
        )

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert "previous_text" not in call_kwargs
        assert "next_text" not in call_kwargs
        assert "previous_request_ids" not in call_kwargs


class TestRequestId:
    """Request id is returned from the response headers."""

    def test_returns_request_id_when_present(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client(request_id="abc-123")
        provider._client = mock_client

        # Act
        result = provider.synthesize("hi", "v1", tmp_path / "out.mp3")

        # Assert
        assert result == "abc-123"

    def test_returns_none_when_header_missing(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider()
        mock_client = _make_mock_client(request_id=None)
        provider._client = mock_client

        # Act
        result = provider.synthesize("hi", "v1", tmp_path / "out.mp3")

        # Assert
        assert result is None
