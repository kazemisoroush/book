"""Tests for ElevenLabsProvider — v2 SDK usage."""
from pathlib import Path
from unittest.mock import MagicMock, Mock

from src.tts.elevenlabs_provider import ElevenLabsProvider


class TestElevenLabsProviderSynthesize:
    """Tests for synthesize() using the v2 ElevenLabs SDK."""

    def _make_provider(self) -> ElevenLabsProvider:
        return ElevenLabsProvider(api_key="test-api-key")

    def test_synthesize_calls_text_to_speech_convert(self, tmp_path: Path) -> None:
        """synthesize() must call client.text_to_speech.convert with voice_id and text."""
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"audio_data"])
        provider._client = mock_client

        output_path = tmp_path / "out.mp3"
        provider.synthesize("Hello world", "voice123", output_path)

        mock_client.text_to_speech.convert.assert_called_once()
        call_args = mock_client.text_to_speech.convert.call_args
        # First positional arg must be voice_id
        assert call_args.args[0] == "voice123"
        # text must be passed
        assert call_args.kwargs.get("text") == "Hello world"

    def test_synthesize_uses_eleven_multilingual_v2_model(self, tmp_path: Path) -> None:
        """synthesize() must use model_id='eleven_multilingual_v2'."""
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"chunk"])
        provider._client = mock_client

        output_path = tmp_path / "out.mp3"
        provider.synthesize("Some text", "voice_abc", output_path)

        call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
        assert call_kwargs.get("model_id") == "eleven_multilingual_v2"

    def test_synthesize_writes_chunks_to_output_path(self, tmp_path: Path) -> None:
        """synthesize() must write all bytes from the convert iterator to output_path."""
        provider = self._make_provider()

        mock_client = MagicMock()
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_client.text_to_speech.convert.return_value = iter(chunks)
        provider._client = mock_client

        output_path = tmp_path / "out.mp3"
        provider.synthesize("Text", "vid", output_path)

        assert output_path.exists()
        assert output_path.read_bytes() == b"chunk1chunk2chunk3"

    def test_synthesize_does_not_call_deprecated_generate(self, tmp_path: Path) -> None:
        """synthesize() must NOT call the deprecated client.generate()."""
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"data"])
        provider._client = mock_client

        output_path = tmp_path / "out.mp3"
        provider.synthesize("Test", "vid", output_path)

        mock_client.generate.assert_not_called()

    def test_get_available_voices_returns_name_to_id_map(self) -> None:
        """get_available_voices() returns dict[str, str] mapping voice name to voice_id."""
        provider = self._make_provider()

        mock_voice_1 = Mock()
        mock_voice_1.name = "Alice"
        mock_voice_1.voice_id = "alice_id"

        mock_voice_2 = Mock()
        mock_voice_2.name = "Bob"
        mock_voice_2.voice_id = "bob_id"

        mock_client = MagicMock()
        mock_client.voices.get_all.return_value.voices = [mock_voice_1, mock_voice_2]
        provider._client = mock_client

        result = provider.get_available_voices()

        assert result == {"Alice": "alice_id", "Bob": "bob_id"}

    def test_module_has_structlog_logger(self) -> None:
        """The elevenlabs_provider module must have a module-level structlog logger."""
        import src.tts.elevenlabs_provider as module
        assert hasattr(module, "logger")
        # structlog BoundLogger or BoundLoggerLazyProxy
        assert "structlog" in type(module.logger).__module__ or hasattr(module.logger, "info")
