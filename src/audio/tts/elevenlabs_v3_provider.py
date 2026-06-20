"""ElevenLabs ``eleven_v3`` TTS provider with inline emotion tags."""
import os
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.domain.voice_settings import VoiceSettings
from src.stores.artifact_store import ArtifactStore

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
    """Prepend ``[emotion]`` when *emotion* is set and not neutral."""
    if emotion is None:
        return text
    label = emotion.lower()
    if label == "neutral":
        return text
    return f"[{label}] {text}"


class ElevenLabsV3Provider(TTSProvider):
    """ElevenLabs TTS provider for ``eleven_v3``."""

    @property
    def name(self) -> str:
        return "elevenlabs_v3"

    def __init__(
        self,
        api_key: str,
        books_dir: "Path | None" = None,
        request_log: Optional[ArtifactStore] = None,
    ) -> None:
        self.api_key = api_key
        self._books_dir = books_dir or Path("books")
        self._client: Any = None
        self._beat_counter = 0
        self._request_log = request_log

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        """Synthesise one *beat* into the per-book TTS cache directory."""
        if beat.voice_id is None:
            return None
        self._beat_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts" / self.name
            / f"beat_{self._beat_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        if output_path.exists() and output_path.stat().st_size > 0:
            return None
        return self._synthesize(beat, beat.voice_id, output_path)

    def _get_client(self) -> Any:
        if self._client is None:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    def _synthesize(
        self,
        beat: Beat,
        voice_id: str,
        output_path: Path,
    ) -> Optional[str]:
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

        if self._request_log is not None:
            self._request_log.save_request(
                key=_request_key(output_path, self._books_dir),
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


def _request_key(output_path: Path, books_dir: Path) -> str:
    """Storage key for the request-log sidecar next to *output_path*."""
    return (
        output_path.with_suffix(".request.json")
        .relative_to(books_dir).as_posix()
    )
