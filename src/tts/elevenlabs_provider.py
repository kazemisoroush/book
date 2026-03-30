"""ElevenLabs TTS provider implementation.

Uses the v2 ElevenLabs SDK (``client.text_to_speech.convert``).
The deprecated v1 ``client.generate()`` is not used.

Model
-----
Synthesis uses ``eleven_v3`` which responds to ALL-CAPS text for word stress
and supports inline audio tags.  ElevenLabs eleven_v3 accepts any auditory
descriptor — tags must describe a vocal quality, sound, or delivery style
(e.g. ``[whispers]``, ``[sighs]``, ``[sarcastic]``, ``[laughs harder]``).
Visual actions (``[grinning]``, ``[standing]``) are not valid tags.

Voice settings presets
----------------------
Two presets cover the emotional spectrum:

* **Emotional** — non-None, non-neutral emotion:
  ``stability=0.35, style=0.40, similarity_boost=0.75, use_speaker_boost=True``
* **Neutral** — None or ``"neutral"`` emotion:
  ``stability=0.65, style=0.05, similarity_boost=0.75, use_speaker_boost=True``

Inline audio tag
----------------
When ``emotion`` is non-None and not ``"neutral"``, the lowercased tag is
prepended as an inline eleven_v3 audio tag:
``emotion="sarcastic"`` → ``"[sarcastic] <original text>"``

All tags are forwarded to the API as-is (lowercased).
"""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.tts.tts_provider import TTSProvider

logger = structlog.get_logger(__name__)

_MODEL_ID = "eleven_v3"


def _is_emotional(emotion: Optional[str]) -> bool:
    """Return True when *emotion* warrants the emotional voice-settings preset.

    Treats both ``None`` and ``"neutral"`` (case-insensitive) as non-emotional.
    """
    return emotion is not None and emotion.lower() != "neutral"


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

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
    ) -> None:
        """Synthesise text using the ElevenLabs v2 API.

        Calls ``client.text_to_speech.convert`` (v2 SDK).  The returned
        iterator of byte chunks is written sequentially to *output_path*.

        When *emotion* is non-None and not ``"NEUTRAL"``, the lowercase
        emotion name is prepended as an inline eleven_v3 audio tag before the
        API call.  The voice-settings preset is selected based on whether the
        emotion is neutral or emotional.

        ALL-CAPS emphasis words already embedded in *text* by the parser are
        passed through unchanged — this method does not alter their casing.

        Args:
            text: The text to synthesise (may contain ALL-CAPS emphasised words).
            voice_id: ElevenLabs voice ID (e.g. ``"21m00Tcm4TlvDq8ikWAM"``).
            output_path: Destination file path for the MP3 output.
            emotion: Optional auditory tag describing vocal delivery
                     (e.g. ``"whispers"``, ``"sarcastic"``, ``"laughs harder"``).
                     Any value is forwarded to the API as-is (lowercased).
        """
        from elevenlabs import VoiceSettings  # type: ignore[import-untyped]

        client = self._get_client()

        # Normalise to lowercase; None stays None.
        resolved_emotion = emotion.lower() if emotion else None

        # Prepend inline audio tag for emotional segments
        tts_text = text
        if _is_emotional(resolved_emotion):
            tts_text = f"[{resolved_emotion}] {text}"

        # Select voice-settings preset
        if _is_emotional(resolved_emotion):
            voice_settings = VoiceSettings(
                stability=0.35,
                style=0.40,
                similarity_boost=0.75,
                use_speaker_boost=True,
            )
        else:
            voice_settings = VoiceSettings(
                stability=0.65,
                style=0.05,
                similarity_boost=0.75,
                use_speaker_boost=True,
            )

        logger.info(
            "elevenlabs_synthesize_start",
            voice_id=voice_id,
            text_length=len(tts_text),
            emotion=resolved_emotion,
            output_path=str(output_path),
        )

        audio_iter = client.text_to_speech.convert(
            voice_id,
            text=tts_text,
            model_id=_MODEL_ID,
            voice_settings=voice_settings,
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
