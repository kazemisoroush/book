"""Tests for ElevenLabsV2Provider."""
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from unittest.mock import MagicMock

from src.audio.tts.elevenlabs_v2_provider import (
    DEFAULT_VOICE_SETTINGS,
    ElevenLabsV2Provider,
)
from src.domain.beat import Beat, BeatType
from src.domain.models import Chapter
from src.domain.voice_settings import VoiceSettings


def _make_mock_client(
    chunks: list[bytes] | None = None,
    request_id: str | None = "test-req-id",
) -> MagicMock:
    """Mock ElevenLabs client whose with_raw_response.convert acts as a context manager."""
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


def _make_provider(tmp_path: Path) -> ElevenLabsV2Provider:
    return ElevenLabsV2Provider(api_key="test-key", books_dir=tmp_path)


def _beat(
    text: str,
    *,
    voice_id: Optional[str] = "v1",
    emotion: Optional[str] = None,
    voice_settings: Optional[VoiceSettings] = None,
) -> Beat:
    return Beat(
        text=text,
        beat_type=BeatType.NARRATION,
        character_id=1,
        emotion=emotion,
        voice_settings=voice_settings,
        voice_id=voice_id,
    )


class TestName:
    """Provider name identifier."""

    def test_name_is_elevenlabs_v2(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider(tmp_path)

        # Act / Assert
        assert provider.name == "elevenlabs_v2"


class TestSynthesizeCall:
    """provide_collection forwards each beat's voice_id, text, and model_id to the SDK."""

    def test_calls_convert_with_voice_id_text_model_and_writes_chunks(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        mock_client = _make_mock_client(chunks=[b"x", b"y"])
        provider._client = mock_client

        # Act
        provider.provide_collection(Chapter(number=1, title='', beats=[_beat("Hello world", voice_id="voice123")]), "book")

        # Assert
        convert = mock_client.text_to_speech.with_raw_response.convert
        convert.assert_called_once()
        call_args = convert.call_args
        assert call_args.args[0] == "voice123"
        assert call_args.kwargs["text"] == "Hello world"
        assert call_args.kwargs["model_id"] == "eleven_multilingual_v2"
        output_path = tmp_path / "book" / "audio" / "tts" / "elevenlabs_v2" / "beat_0001.mp3"
        assert output_path.read_bytes() == b"xy"


class TestNoInlineTag:
    """V2 never prepends an audio tag — multilingual_v2 would speak the brackets."""

    def test_emotion_does_not_alter_text(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.provide_collection(Chapter(number=1, title='', beats=[_beat("I refuse!", emotion="angry")]), "book")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert call_kwargs["text"] == "I refuse!"


class TestVoiceSettings:
    """Per-beat voice_settings override and default preset."""

    def test_default_preset_is_used_when_voice_settings_is_none(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.provide_collection(Chapter(number=1, title='', beats=[_beat("hi")]), "book")

        # Assert
        vs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs["voice_settings"]
        assert vs.stability == DEFAULT_VOICE_SETTINGS.stability
        assert vs.style == DEFAULT_VOICE_SETTINGS.style
        assert vs.similarity_boost == DEFAULT_VOICE_SETTINGS.similarity_boost
        assert vs.use_speaker_boost is DEFAULT_VOICE_SETTINGS.use_speaker_boost

    def test_beat_voice_settings_override_default(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        mock_client = _make_mock_client()
        provider._client = mock_client
        override = VoiceSettings(
            stability=0.20,
            style=0.80,
            similarity_boost=0.50,
            use_speaker_boost=False,
        )

        # Act
        provider.provide_collection(Chapter(number=1, title='', beats=[_beat("hi", voice_settings=override)]), "book")

        # Assert
        vs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs["voice_settings"]
        assert vs.stability == 0.20
        assert vs.style == 0.80
        assert vs.similarity_boost == 0.50
        assert vs.use_speaker_boost is False


class TestContextParams:
    """provide_collection forwards previous_text / next_text / previous_request_ids."""

    def test_continuity_threads_previous_text_and_request_ids(
        self, tmp_path: Path,
    ) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        request_ids = iter(["r1", "r2", "r3"])

        @contextmanager
        def _convert(*args: object, **kwargs: object) -> Iterator[MagicMock]:
            response = MagicMock()
            response.headers = {"request-id": next(request_ids)}
            response.data = iter([b"x"])
            yield response

        mock_client = MagicMock()
        mock_client.text_to_speech.with_raw_response.convert.side_effect = _convert
        provider._client = mock_client
        beats = [
            _beat("First line."),
            _beat("Second line."),
            _beat("Third line."),
        ]

        # Act
        provider.provide_collection(Chapter(number=1, title='', beats=beats), "book")

        # Assert
        calls = mock_client.text_to_speech.with_raw_response.convert.call_args_list
        first_call = calls[0].kwargs
        second_call = calls[1].kwargs
        third_call = calls[2].kwargs
        assert "previous_text" not in first_call
        assert second_call["previous_text"] == "First line."
        assert second_call["next_text"] == "Third line."
        assert second_call["previous_request_ids"] == ["r1"]
        assert third_call["previous_request_ids"] == ["r1", "r2"]

    def test_provide_omits_context_for_a_lone_beat(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        mock_client = _make_mock_client()
        provider._client = mock_client

        # Act
        provider.provide(_beat("solo."), "book")

        # Assert
        call_kwargs = mock_client.text_to_speech.with_raw_response.convert.call_args.kwargs
        assert "previous_text" not in call_kwargs
        assert "next_text" not in call_kwargs
        assert "previous_request_ids" not in call_kwargs


class TestRequestId:
    """Request id is returned from the response headers."""

    def test_returns_request_id_when_present(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        mock_client = _make_mock_client(request_id="abc-123")
        provider._client = mock_client

        # Act
        result = provider.provide_collection(Chapter(number=1, title='', beats=[_beat("hi")]), "book")

        # Assert
        assert result == ["abc-123"]

    def test_returns_none_when_header_missing(self, tmp_path: Path) -> None:
        # Arrange
        provider = _make_provider(tmp_path)
        mock_client = _make_mock_client(request_id=None)
        provider._client = mock_client

        # Act
        result = provider.provide_collection(Chapter(number=1, title='', beats=[_beat("hi")]), "book")

        # Assert
        assert result == [None]
