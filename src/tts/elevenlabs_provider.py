"""ElevenLabs TTS provider implementation."""
from pathlib import Path
from src.tts.tts_provider import TTSProvider


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs TTS provider."""

    def __init__(self, api_key: str):
        """
        Initialize ElevenLabs provider.

        Args:
            api_key: ElevenLabs API key
        """
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        """Lazy initialization of ElevenLabs client."""
        if self._client is None:
            try:
                from elevenlabs.client import ElevenLabs
                self._client = ElevenLabs(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "elevenlabs package is required. "
                    "Install with: pip install elevenlabs"
                )
        return self._client

    def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
        """Synthesize text using ElevenLabs."""
        client = self._get_client()

        audio = client.generate(
            text=text,
            voice=voice_id,
            model="eleven_monolingual_v1"
        )

        # Save audio to file
        with open(output_path, 'wb') as f:
            for chunk in audio:
                f.write(chunk)

    def get_available_voices(self) -> dict[str, str]:
        """Get available ElevenLabs voices."""
        client = self._get_client()
        voices = client.voices.get_all()

        return {voice.name: voice.voice_id for voice in voices.voices}
