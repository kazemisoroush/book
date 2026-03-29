"""ElevenLabs TTS provider implementation.

Uses the v2 ElevenLabs SDK (``client.text_to_speech.convert``).
The deprecated v1 ``client.generate()`` is not used.
"""
from pathlib import Path
from typing import Any

import structlog

from src.tts.tts_provider import TTSProvider

logger = structlog.get_logger(__name__)


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs TTS provider.

    Wraps the ElevenLabs Python SDK v2.  All synthesis calls go through
    ``client.text_to_speech.convert`` which returns an iterator of bytes
    chunks that are streamed to the output file.
    """

    def __init__(self, api_key: str) -> None:
        """Initialise ElevenLabs provider.

        Args:
            api_key: ElevenLabs API key
        """
        self.api_key = api_key
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy initialisation of the ElevenLabs client."""
        if self._client is None:
            try:
                from elevenlabs.client import ElevenLabs  # type: ignore[import-untyped]
                self._client = ElevenLabs(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "elevenlabs package is required. "
                    "Install with: pip install elevenlabs"
                )
        return self._client

    def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
        """Synthesise text using the ElevenLabs v2 API.

        Calls ``client.text_to_speech.convert`` (v2 SDK).  The returned
        iterator of byte chunks is written sequentially to *output_path*.

        Args:
            text: The text to synthesise.
            voice_id: ElevenLabs voice ID (e.g. ``"21m00Tcm4TlvDq8ikWAM"``).
            output_path: Destination file path for the MP3 output.
        """
        client = self._get_client()

        logger.info(
            "elevenlabs_synthesize_start",
            voice_id=voice_id,
            text_length=len(text),
            output_path=str(output_path),
        )

        audio_iter = client.text_to_speech.convert(
            voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
        )

        with open(output_path, "wb") as f:
            for chunk in audio_iter:
                f.write(chunk)

        logger.info("elevenlabs_synthesize_done", output_path=str(output_path))

    def get_available_voices(self) -> dict[str, str]:
        """Return available ElevenLabs voices as ``{name: voice_id}``."""
        client = self._get_client()
        voices = client.voices.get_all()
        return {voice.name: voice.voice_id for voice in voices.voices}
