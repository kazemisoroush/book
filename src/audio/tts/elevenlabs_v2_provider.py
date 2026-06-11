"""ElevenLabs multilingual v2 TTS provider.

Targets the ``eleven_multilingual_v2`` model. Inline emotion tags are not
supported (the model would speak the brackets verbatim) so :attr:`Beat.emotion`
is ignored at synthesis time. Per-beat :attr:`Beat.voice_settings` override the
fixed neutral default. Context kwargs (``previous_text`` / ``next_text`` /
``previous_request_ids``) are forwarded for prosody and acoustic continuity.
"""
import os
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.domain.voice_settings import VoiceSettings
from src.repository.api_artifact_store import APIArtifactStore

logger = structlog.get_logger(__name__)

_MODEL_ID = "eleven_multilingual_v2"
_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

DEFAULT_VOICE_SETTINGS = VoiceSettings(
    stability=0.65,
    style=0.05,
    similarity_boost=0.75,
    use_speaker_boost=True,
)


class ElevenLabsV2Provider(TTSProvider):
    """ElevenLabs TTS provider for the ``eleven_multilingual_v2`` model."""

    @property
    def name(self) -> str:
        return "elevenlabs_v2"

    def __init__(
        self,
        api_key: str,
        books_dir: "Path | None" = None,
        artifact_store: Optional[APIArtifactStore] = None,
    ) -> None:
        """Initialise the provider."""
        self.api_key = api_key
        self._books_dir = books_dir or Path("books")
        self._client: Any = None
        self._beat_counter = 0
        self._artifact_store = artifact_store

    def provide(self, beat: Beat, voice_id: str, book_id: str) -> None:
        """Synthesise a single beat into the per-book TTS cache directory."""
        self._beat_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts" / self.name
            / f"beat_{self._beat_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        if not (output_path.exists() and output_path.stat().st_size > 0):
            self.synthesize(
                text=beat.text,
                voice_id=voice_id,
                output_path=output_path,
                voice_settings=beat.voice_settings,
            )

    def _get_client(self) -> Any:
        """Lazily create the ElevenLabs client."""
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

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        voice_settings: Optional[VoiceSettings] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Synthesise *text* using the multilingual_v2 model and return the request id."""
        from elevenlabs import VoiceSettings as SDKVoiceSettings

        client = self._get_client()
        settings = voice_settings or DEFAULT_VOICE_SETTINGS
        sdk_settings = SDKVoiceSettings(
            stability=settings.stability,
            style=settings.style,
            similarity_boost=settings.similarity_boost,
            use_speaker_boost=settings.use_speaker_boost,
        )

        context_kwargs: dict[str, Any] = {}
        if previous_text is not None:
            context_kwargs["previous_text"] = previous_text
        if next_text is not None:
            context_kwargs["next_text"] = next_text
        if previous_request_ids is not None:
            context_kwargs["previous_request_ids"] = previous_request_ids

        logger.info(
            "elevenlabs_v2_synthesize_start",
            voice_id=voice_id,
            text_length=len(text),
            output_path=str(output_path),
        )

        if self._artifact_store is not None:
            self._artifact_store.save_request(
                path=output_path.with_suffix(".request.json"),
                method="POST",
                url=_TTS_URL.format(voice_id=voice_id),
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                body={
                    "text": text,
                    "model_id": _MODEL_ID,
                    "voice_settings": {
                        "stability": settings.stability,
                        "style": settings.style,
                        "similarity_boost": settings.similarity_boost,
                        "use_speaker_boost": settings.use_speaker_boost,
                    },
                    **context_kwargs,
                },
            )

        request_id: Optional[str] = None
        with client.text_to_speech.with_raw_response.convert(
            voice_id,
            text=text,
            model_id=_MODEL_ID,
            voice_settings=sdk_settings,
            **context_kwargs,
        ) as raw_response:
            request_id = raw_response.headers.get("request-id")
            with open(output_path, "wb") as f:
                for chunk in raw_response.data:
                    f.write(chunk)

        logger.info(
            "elevenlabs_v2_synthesize_done",
            output_path=str(output_path),
            request_id=request_id,
        )
        return request_id
