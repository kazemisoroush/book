"""Fish Audio TTS provider implementation."""
import os
from pathlib import Path
from typing import Any, Optional

import requests
import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.models import Beat

logger = structlog.get_logger(__name__)


class FishAudioTTSProvider(TTSProvider):
    """Fish Audio TTS provider implementation.

    Uses Fish Audio API for text-to-speech synthesis with emotion/style control.
    """

    def __init__(
        self,
        api_key: str,
        books_dir: Path = Path("books"),
        base_url: str = "https://api.fish.audio/v1",
    ) -> None:
        """Initialize Fish Audio provider.

        Args:
            api_key: Fish Audio API key
            books_dir: Base directory for book output (used by provide()).
            base_url: Fish Audio API base URL (default production endpoint)

        Raises:
            ValueError: If api_key is empty
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self._books_dir = books_dir
        self.base_url = base_url
        self._voice_cache: Optional[dict[str, str]] = None
        self._segment_counter = 0

    def provide(self, beat: Beat, voice_id: str, book_id: str) -> float:
        """Synthesize speech for a beat.

        Constructs output path, calls synthesize(), measures duration,
        and sets beat.audio_path.

        Args:
            segment: The segment to synthesize.
            voice_id: The voice identifier to use.
            book_id: The book identifier.

        Returns:
            Duration of the generated audio in seconds.
        """
        self._segment_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts"
            / f"seg_{self._segment_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        self.synthesize(
            text=beat.text,
            voice_id=voice_id,
            output_path=output_path,
            emotion=beat.emotion,
            voice_stability=beat.voice_stability,
            voice_style=beat.voice_style,
            voice_speed=beat.voice_speed,
        )

        duration = self._measure_duration(output_path)
        beat.audio_path = str(output_path)
        return duration

    @staticmethod
    def _measure_duration(path: Path) -> float:
        """Measure the duration of an audio file in seconds."""
        from mutagen.mp3 import MP3  # type: ignore[import-not-found]
        audio = MP3(str(path))
        return float(audio.info.length)

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Synthesize text using Fish Audio API.

        Args:
            text: Text to synthesize
            voice_id: Fish Audio reference_id (voice model ID)
            output_path: Where to save the audio file
            emotion: Optional emotion parameter (logged if unsupported)
            previous_text: Not supported by Fish Audio, logged at debug
            next_text: Not supported by Fish Audio, logged at debug
            voice_stability: Not supported by Fish Audio, logged at debug
            voice_style: Not supported by Fish Audio, logged at debug
            voice_speed: Optional speed parameter (0.5-2.0 range)
            previous_request_ids: Not supported by Fish Audio, logged at debug

        Returns:
            None (Fish Audio doesn't provide request IDs for continuity)
        """
        # Log unsupported parameters at debug level
        if previous_text or next_text:
            logger.debug(
                "fish_audio_prosody_context_not_supported",
                previous_text_provided=previous_text is not None,
                next_text_provided=next_text is not None,
            )

        if voice_stability is not None or voice_style is not None:
            logger.debug(
                "fish_audio_voice_modifiers_not_supported",
                voice_stability=voice_stability,
                voice_style=voice_style,
            )

        if previous_request_ids:
            logger.debug(
                "fish_audio_request_continuity_not_supported",
                previous_request_ids=previous_request_ids,
            )

        # Build request body
        request_body: dict[str, Any] = {
            "text": text,
            "reference_id": voice_id,
        }

        if voice_speed is not None:
            request_body["speed"] = voice_speed

        if emotion:
            request_body["emotion"] = emotion

        logger.info(
            "fish_audio_synthesize_start",
            voice_id=voice_id,
            text_length=len(text),
            output_path=str(output_path),
        )

        try:
            # Call Fish Audio API
            response = requests.post(
                f"{self.base_url}/tts",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_body,
                timeout=60,
            )
            response.raise_for_status()

            # Write audio to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            logger.info(
                "fish_audio_synthesize_done",
                output_path=str(output_path),
            )

            return None  # Fish Audio doesn't provide request IDs

        except requests.RequestException as e:
            logger.warning(
                "fish_audio_synthesize_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(e.response, "status_code", None),
            )
            return None

    def get_available_voices(self) -> dict[str, str]:
        """Get available voices from Fish Audio API.

        Returns:
            Dictionary mapping voice names to voice IDs.
            Result is cached in memory for the lifetime of the provider instance.
        """
        if self._voice_cache is not None:
            return self._voice_cache

        try:
            response = requests.get(
                f"{self.base_url}/voices",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            response.raise_for_status()

            voices_data = response.json()
            # Map voice names to IDs
            self._voice_cache = {
                voice["name"]: voice["id"] for voice in voices_data.get("voices", [])
            }

            logger.debug(
                "fish_audio_voices_fetched",
                voice_count=len(self._voice_cache),
            )

            return self._voice_cache

        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
            # Auth / billing errors are not transient — let them propagate
            if status in (401, 402, 403):
                logger.error(
                    "fish_audio_voices_auth_error",
                    status_code=status,
                    error=str(e),
                )
                raise
            logger.warning(
                "fish_audio_voices_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {}
        except requests.RequestException as e:
            logger.warning(
                "fish_audio_voices_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {}

    def get_voices(self) -> list[dict[str, Any]]:
        """Get available voices with metadata.

        Returns:
            List of voice dictionaries with minimal metadata.
        """
        voices = self.get_available_voices()
        return [
            {
                "voice_id": voice_id,
                "name": name,
                "labels": {},
            }
            for name, voice_id in voices.items()
        ]
