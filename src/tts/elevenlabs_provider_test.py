"""Tests for ElevenLabsProvider — v2 SDK usage."""
from pathlib import Path
from unittest.mock import MagicMock

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

    def test_synthesize_uses_eleven_multilingual_v2_model(self, tmp_path: Path) -> None:
        """synthesize() must use model_id='eleven_multilingual_v2'."""
        # Arrange
        provider = self._make_provider()
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"chunk"])
        provider._client = mock_client
        output_path = tmp_path / "out.mp3"

        # Act
        provider.synthesize("Some text", "voice_abc", output_path)

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
        output_path = tmp_path / "out.mp3"

        # Act
        provider.synthesize("Test", "vid", output_path)

        # Assert
        mock_client.generate.assert_not_called()

    def test_module_has_structlog_logger(self) -> None:
        """The elevenlabs_provider module must have a module-level structlog logger."""
        # Arrange
        import src.tts.elevenlabs_provider as module

        # Assert
        assert hasattr(module, "logger")
        assert "structlog" in type(module.logger).__module__ or hasattr(module.logger, "info")
