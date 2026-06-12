"""ElevenLabs v3 TTS provider.

Targets the ``eleven_v3`` model. The free-form :attr:`Beat.emotion` is wrapped
into an inline audio tag (``[emotion] text``) here, the AI prompt only emits
the raw label. Per-beat :attr:`Beat.voice_settings` override the fixed
permissive default. Context kwargs (``previous_text`` / ``next_text`` /
``previous_request_ids``) are silently dropped because v3 returns 400 on them.
"""
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.domain.voice_settings import VoiceSettings
from src.repository.api_artifact_store import APIArtifactStore

if TYPE_CHECKING:
    from src.audio.tts.beat_context_resolver import BeatContext

logger = structlog.get_logger(__name__)

_MODEL_ID = "eleven_v3"
_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

DEFAULT_VOICE_SETTINGS = VoiceSettings(
    stability=0.35,
    style=0.40,
    similarity_boost=0.75,
    use_speaker_boost=True,
)


def _build_text(text: str, emotion: Optional[str]) -> str:
    """Prepend ``[emotion] `` when *emotion* is set and not neutral."""
    if emotion is None:
        return text
    label = emotion.lower()
    if label == "neutral":
        return text
    return f"[{label}] {text}"


class ElevenLabsV3Provider(TTSProvider):
    """ElevenLabs TTS provider for the ``eleven_v3`` model."""

    @property
    def name(self) -> str:
        return "elevenlabs_v3"

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

    def provide(
        self,
        beat: Beat,
        voice_id: str,
        book_id: str,
        context: Optional["BeatContext"] = None,
    ) -> Optional[str]:
        """Synthesise a single beat into the per-book TTS cache directory."""
        self._beat_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts" / self.name
            / f"beat_{self._beat_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        if output_path.exists() and output_path.stat().st_size > 0:
            return None
        return self.synthesize(beat, voice_id, output_path, context)

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
        beat: Beat,
        voice_id: str,
        output_path: Path,
        context: Optional["BeatContext"] = None,
    ) -> Optional[str]:
        """Synthesise *beat* using the v3 model and return the request id."""
        from elevenlabs import VoiceSettings as SDKVoiceSettings

        client = self._get_client()
        tts_text = _build_text(beat.text, beat.emotion)
        settings = beat.voice_settings or DEFAULT_VOICE_SETTINGS
        sdk_settings = SDKVoiceSettings(
            stability=settings.stability,
            style=settings.style,
            similarity_boost=settings.similarity_boost,
            use_speaker_boost=settings.use_speaker_boost,
        )

        logger.info(
            "elevenlabs_v3_synthesize_start",
            voice_id=voice_id,
            text_length=len(tts_text),
            emotion=beat.emotion,
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
                    "text": tts_text,
                    "model_id": _MODEL_ID,
                    "voice_settings": {
                        "stability": settings.stability,
                        "style": settings.style,
                        "similarity_boost": settings.similarity_boost,
                        "use_speaker_boost": settings.use_speaker_boost,
                    },
                },
            )

        request_id: Optional[str] = None
        with client.text_to_speech.with_raw_response.convert(
            voice_id,
            text=tts_text,
            model_id=_MODEL_ID,
            voice_settings=sdk_settings,
        ) as raw_response:
            request_id = raw_response.headers.get("request-id")
            with open(output_path, "wb") as f:
                for chunk in raw_response.data:
                    f.write(chunk)

        logger.info(
            "elevenlabs_v3_synthesize_done",
            output_path=str(output_path),
            request_id=request_id,
        )
        return request_id
