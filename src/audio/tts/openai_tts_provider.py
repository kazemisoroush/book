"""OpenAI TTS provider implementation."""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.tts.tts_provider import TTSProvider

logger = structlog.get_logger(__name__)

# OpenAI's fixed voice set
_OPENAI_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
_DEFAULT_VOICE = "alloy"

# Speed range constraints
_MIN_SPEED = 0.25
_MAX_SPEED = 4.0


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS provider implementation.

    Uses OpenAI's text-to-speech API with a fixed set of 6 voices.
    Supports speed control but not emotion tags or prosody context.
    """

    def __init__(self, api_key: str, model: str = "tts-1") -> None:
        """Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key
            model: TTS model ID ("tts-1" or "tts-1-hd")

        Raises:
            ValueError: If api_key is empty
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.model = model
        self._client: Optional[Any] = None
        self.logger = logger

    def provide(self, segment: Any, voice_id: str, book_id: str) -> float:
        """Not yet implemented for OpenAI provider."""
        raise NotImplementedError("OpenAITTSProvider.provide() not yet implemented")

    def _get_client(self) -> Any:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "openai package is required. Install with: pip install openai"
                )
        return self._client

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
        """Synthesize text using OpenAI TTS API.

        Args:
            text: Text to synthesize
            voice_id: Voice identifier (one of OpenAI's 6 voices)
            output_path: Where to save the audio file
            emotion: Ignored (not supported by OpenAI)
            previous_text: Ignored (not supported by OpenAI)
            next_text: Ignored (not supported by OpenAI)
            voice_stability: Ignored (not supported by OpenAI)
            voice_style: Ignored (not supported by OpenAI)
            voice_speed: Optional speed multiplier (clamped to 0.25-4.0)
            previous_request_ids: Ignored (not supported by OpenAI)

        Returns:
            None (OpenAI doesn't provide request IDs)
        """
        client = self._get_client()

        # Clamp voice_id to valid set
        resolved_voice = voice_id if voice_id in _OPENAI_VOICES else _DEFAULT_VOICE
        if resolved_voice != voice_id:
            logger.warning(
                "openai_voice_not_found_using_default",
                requested_voice=voice_id,
                default_voice=_DEFAULT_VOICE,
            )

        # Build request kwargs
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "voice": resolved_voice,
            "input": text,
        }

        # Clamp speed if provided
        if voice_speed is not None:
            clamped_speed = max(_MIN_SPEED, min(_MAX_SPEED, voice_speed))
            request_kwargs["speed"] = clamped_speed

        logger.info(
            "openai_synthesize_start",
            voice=resolved_voice,
            text_length=len(text),
            model=self.model,
            output_path=str(output_path),
        )

        try:
            # Call OpenAI API
            response = client.audio.speech.create(**request_kwargs)

            # Write audio to output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            logger.info(
                "openai_synthesize_done",
                output_path=str(output_path),
            )

            return None  # OpenAI doesn't provide request IDs

        except Exception as e:
            logger.warning(
                "openai_synthesize_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def get_available_voices(self) -> dict[str, str]:
        """Get available voices.

        Returns:
            Dictionary mapping voice names to voice IDs.
            For OpenAI, names and IDs are identical.
        """
        return {voice: voice for voice in _OPENAI_VOICES}

    def get_voices(self) -> list[dict[str, Any]]:
        """Get available voices with metadata.

        Returns:
            List of voice dictionaries. For OpenAI, minimal metadata is available.
        """
        return [
            {
                "voice_id": voice,
                "name": voice,
                "labels": {},
            }
            for voice in _OPENAI_VOICES
        ]
