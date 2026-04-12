"""ElevenLabs TTS provider implementation.

Uses the v2 ElevenLabs SDK (``client.text_to_speech.convert``).
The deprecated v1 ``client.generate()`` is not used.

Model capabilities
------------------
Two models are supported, each with different feature sets:

* **eleven_multilingual_v2** (default) — supports ``previous_text`` /
  ``next_text`` for prosody continuity across segments.  Does *not*
  support inline audio tags or ALL-CAPS emphasis.
* **eleven_v3** — supports inline audio tags (``[whispers]``,
  ``[sarcastic]``, etc.) and ALL-CAPS word stress.  Does *not yet*
  support ``previous_text`` / ``next_text``.

Switch ``_MODEL_ID`` to change model.  The capability dict
``_MODEL_CAPS`` gates features automatically.

Voice settings presets
----------------------
Two presets cover the emotional spectrum:

* **Emotional** — non-None, non-neutral emotion:
  ``stability=0.35, style=0.40, similarity_boost=0.75, use_speaker_boost=True``
* **Neutral** — None or ``"neutral"`` emotion:
  ``stability=0.65, style=0.05, similarity_boost=0.75, use_speaker_boost=True``
"""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.tts_provider import TTSProvider

logger = structlog.get_logger(__name__)

_MODEL_ID = "eleven_multilingual_v2"

# Per-model feature flags.  Flip _MODEL_ID and capabilities follow.
_MODEL_CAPS: dict[str, dict[str, bool]] = {
    "eleven_v3": {
        "inline_tags": True,
        "allcaps_emphasis": True,
        "context_params": False,
    },
    "eleven_multilingual_v2": {
        "inline_tags": False,
        "allcaps_emphasis": False,
        "context_params": True,
    },
}


def _caps() -> dict[str, bool]:
    """Return the capability dict for the active model."""
    return _MODEL_CAPS[_MODEL_ID]


def _is_emotional(emotion: Optional[str]) -> bool:
    """Return True when *emotion* warrants the emotional voice-settings preset.

    Treats both ``None`` and ``"neutral"`` (case-insensitive) as non-emotional.
    """
    return emotion is not None and emotion.lower() != "neutral"



class ElevenLabsTTSProvider(TTSProvider):
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
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Synthesise text using the ElevenLabs v2 API.

        Calls ``client.text_to_speech.convert`` (v2 SDK).  The returned
        iterator of byte chunks is written sequentially to *output_path*.

        Feature behaviour depends on the active model (see ``_MODEL_CAPS``):

        * **inline_tags**: When enabled and *emotion* is non-neutral, the
          lowercased tag is prepended as ``[emotion] text``.
        * **allcaps_emphasis**: When enabled, ALL-CAPS words in *text* are
          passed through for the model to interpret as word stress.
          (When disabled, ALL-CAPS words are sent as-is — the model simply
          ignores the emphasis hint.)
        * **context_params**: When enabled, *previous_text*, *next_text*,
          and *previous_request_ids* are forwarded to the API for prosody
          and acoustic continuity.

        Args:
            text: The text to synthesise (may contain ALL-CAPS emphasised words).
            voice_id: ElevenLabs voice ID (e.g. ``"21m00Tcm4TlvDq8ikWAM"``).
            output_path: Destination file path for the MP3 output.
            emotion: Optional auditory tag describing vocal delivery
                     (e.g. ``"whispers"``, ``"sarcastic"``, ``"laughs harder"``).
                     Any value is forwarded to the API as-is (lowercased).
            previous_text: Optional text preceding this segment for prosody
                           continuity.  Only sent when model supports it.
            next_text: Optional text following this segment for natural endings.
                       Only sent when model supports it.
            previous_request_ids: Optional list of up to 3 request IDs from
                                  prior same-voice calls for acoustic continuity.

        Returns:
            The request ID from the API response, or ``None`` if unavailable.
        """
        from elevenlabs import VoiceSettings  # type: ignore[import-untyped]

        client = self._get_client()
        caps = _caps()

        # Normalise to lowercase; None stays None.
        resolved_emotion = emotion.lower() if emotion else None

        # Prepend inline audio tag for emotional segments (v3 only)
        tts_text = text
        if caps["inline_tags"] and _is_emotional(resolved_emotion):
            tts_text = f"[{resolved_emotion}] {text}"

        # Select voice settings — use LLM-provided values when available,
        # fall back to binary emotional/neutral presets for legacy segments.
        if voice_stability is not None and voice_style is not None:
            voice_settings = VoiceSettings(
                stability=voice_stability,
                style=voice_style,
                similarity_boost=0.75,
                use_speaker_boost=True,
            )
        elif _is_emotional(resolved_emotion):
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
            model=_MODEL_ID,
            output_path=str(output_path),
        )

        # Build optional context kwargs — only when model supports them.
        context_kwargs: dict[str, Any] = {}
        if caps["context_params"]:
            if previous_text is not None:
                context_kwargs["previous_text"] = previous_text
            if next_text is not None:
                context_kwargs["next_text"] = next_text
            if previous_request_ids is not None:
                context_kwargs["previous_request_ids"] = previous_request_ids

        # Use with_raw_response to access HTTP headers (for request-id).
        # The context manager yields an HttpResponse wrapping the byte iterator.
        request_id: Optional[str] = None
        with client.text_to_speech.with_raw_response.convert(
            voice_id,
            text=tts_text,
            model_id=_MODEL_ID,
            voice_settings=voice_settings,
            **context_kwargs,
        ) as raw_response:
            request_id = raw_response.headers.get("request-id")
            with open(output_path, "wb") as f:
                for chunk in raw_response.data:
                    f.write(chunk)

        logger.info(
            "elevenlabs_synthesize_done",
            output_path=str(output_path),
            request_id=request_id,
        )
        return request_id

    def get_available_voices(self) -> dict[str, str]:
        """Return available ElevenLabs voices as ``{name: voice_id}``."""
        client = self._get_client()
        voices = client.voices.get_all()
        return {voice.name: voice.voice_id for voice in voices.voices}

    def get_voices(self) -> list[dict[str, Any]]:
        """Return available ElevenLabs voices with full metadata.

        Returns:
            List of voice dictionaries, each containing:
            - voice_id: str — ElevenLabs voice ID
            - name: str — human-readable voice name
            - labels: dict[str, str] — voice metadata tags (e.g. gender, age)
        """
        client = self._get_client()
        voices = client.voices.get_all()
        return [
            {
                "voice_id": voice.voice_id,
                "name": voice.name,
                "labels": dict(voice.labels) if voice.labels else {},
            }
            for voice in voices.voices
        ]
