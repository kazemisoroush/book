"""ElevenLabs multilingual v2 TTS provider with internal prosody continuity."""
import os
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.tts.beat_context_resolver import BeatContext, BeatContextResolver
from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.domain.models import Chapter
from src.domain.voice_settings import VoiceSettings
from src.repository.artifact_repository import ArtifactRepository

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
    """ElevenLabs TTS provider for ``eleven_multilingual_v2``."""

    @property
    def name(self) -> str:
        return "elevenlabs_v2"

    def __init__(
        self,
        api_key: str,
        books_dir: "Path | None" = None,
        request_log: Optional[ArtifactRepository] = None,
    ) -> None:
        self.api_key = api_key
        self._books_dir = books_dir or Path("books")
        self._client: Any = None
        self._beat_counter = 0
        self._request_log = request_log

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        """Synthesise one *beat* without continuity context."""
        return self._provide_one(beat, book_id, context=None)

    def provide_collection(
        self, chapter: Chapter, book_id: str,
    ) -> list[Optional[str]]:
        """Synthesise every narratable *beat* in *chapter* with same-character continuity."""
        resolver = BeatContextResolver(chapter.beats)
        request_ids: list[Optional[str]] = []
        for beat_index, beat in enumerate(chapter.beats):
            if not beat.is_narratable or beat.voice_id is None:
                request_ids.append(None)
                continue
            context = resolver.resolve(beat_index, voice_id=beat.voice_id)
            request_id = self._provide_one(beat, book_id, context=context)
            resolver.record_request_id(beat.voice_id, request_id)
            request_ids.append(request_id)
        return request_ids

    def _provide_one(
        self,
        beat: Beat,
        book_id: str,
        context: Optional[BeatContext],
    ) -> Optional[str]:
        self._beat_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts" / self.name
            / f"beat_{self._beat_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)

        if output_path.exists() and output_path.stat().st_size > 0:
            return None
        if beat.voice_id is None:
            return None
        return self._synthesize(beat, beat.voice_id, output_path, context)

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
        context: Optional[BeatContext],
    ) -> Optional[str]:
        from elevenlabs import VoiceSettings as SDKVoiceSettings

        client = self._get_client()
        settings = beat.voice_settings or DEFAULT_VOICE_SETTINGS
        sdk_settings = SDKVoiceSettings(
            stability=settings.stability,
            style=settings.style,
            similarity_boost=settings.similarity_boost,
            use_speaker_boost=settings.use_speaker_boost,
        )

        context_kwargs: dict[str, Any] = {}
        if context is not None:
            if context.previous_text is not None:
                context_kwargs["previous_text"] = context.previous_text
            if context.next_text is not None:
                context_kwargs["next_text"] = context.next_text
            if context.previous_request_ids is not None:
                context_kwargs["previous_request_ids"] = context.previous_request_ids

        logger.info(
            "elevenlabs_v2_synthesize_start",
            voice_id=voice_id,
            text_length=len(beat.text),
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
                    "text": beat.text,
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
            text=beat.text,
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


def _request_key(output_path: Path, books_dir: Path) -> str:
    """Storage key for the request-log sidecar next to *output_path*."""
    return (
        output_path.with_suffix(".request.json")
        .relative_to(books_dir).as_posix()
    )
