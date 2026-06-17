"""ElevenLabs Text-to-Dialogue TTS provider for chapter-level multi-voice synthesis."""
from typing import Any, Optional

import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.domain.models import Chapter
from src.storage.audio_store import AudioStore
from src.storage.objects import APIRequest, TTSChunk, TTSChunkRef

logger = structlog.get_logger(__name__)

_MODEL_ID = "eleven_v3"
_DIALOGUE_URL = "https://api.elevenlabs.io/v1/text-to-dialogue"
_MAX_CHARS_PER_REQUEST = 2000
_MAX_UNIQUE_VOICES_PER_REQUEST = 10


class ElevenLabsDialogueProvider(TTSProvider):
    """ElevenLabs Text-to-Dialogue provider."""

    @property
    def name(self) -> str:
        return "elevenlabs_dialogue"

    def __init__(self, api_key: str, audio_store: AudioStore) -> None:
        self.api_key = api_key
        self._audio_store = audio_store
        self._client: Any = None

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        raise NotImplementedError(
            "ElevenLabsDialogueProvider only operates via provide_collection",
        )

    def provide_collection(
        self, chapter: Chapter, book_id: str,
    ) -> list[Optional[str]]:
        request_ids: list[Optional[str]] = []
        for chunk_index, chunk_beats in enumerate(_chunk_beats(chapter.beats), start=1):
            ref = TTSChunkRef(
                book_id=book_id,
                provider=self.name,
                chapter_slug=chapter.dir_slug,
                index=chunk_index,
            )
            request_id = self._synthesize_chunk(chunk_beats, ref)
            request_ids.extend([request_id] * len(chunk_beats))
        return request_ids

    def _get_client(self) -> Any:
        if self._client is None:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    def _synthesize_chunk(
        self, beats: list[Beat], ref: TTSChunkRef,
    ) -> Optional[str]:
        if not beats:
            return None
        if self._audio_store.has_tts_chunk(ref):
            return None

        inputs = [
            {"text": _with_emotion_tag(beat), "voice_id": beat.voice_id}
            for beat in beats
        ]

        logger.info(
            "elevenlabs_dialogue_synthesize_start",
            line_count=len(inputs),
            total_chars=sum(len(beat.text) for beat in beats),
            unique_voices=len({beat.voice_id for beat in beats}),
            chunk_index=ref.index,
            chapter_slug=ref.chapter_slug,
        )

        api_request = APIRequest(
            method="POST",
            url=_DIALOGUE_URL,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            body={"inputs": inputs, "model_id": _MODEL_ID},
        )

        client = self._get_client()
        request_id: Optional[str] = None
        with client.text_to_dialogue.with_raw_response.convert(
            inputs=inputs,
            model_id=_MODEL_ID,
        ) as raw_response:
            request_id = raw_response.headers.get("request-id")
            audio_bytes = b"".join(raw_response.data)

        self._audio_store.save_tts_chunk(
            TTSChunk(
                book_id=ref.book_id,
                provider=ref.provider,
                chapter_slug=ref.chapter_slug,
                index=ref.index,
                audio=audio_bytes,
            ),
            api_request=api_request,
        )

        logger.info(
            "elevenlabs_dialogue_synthesize_done",
            chunk_index=ref.index,
            chapter_slug=ref.chapter_slug,
            request_id=request_id,
        )
        return request_id


def _with_emotion_tag(beat: Beat) -> str:
    """Prepend an inline ``[emotion]`` tag when *beat.emotion* is set and not neutral."""
    if beat.emotion is None:
        return beat.text
    label = beat.emotion.lower()
    if label == "neutral":
        return beat.text
    return f"[{label}] {beat.text}"


def _chunk_beats(beats: list[Beat]) -> list[list[Beat]]:
    """Group narratable *beats* into chunks under the dialogue API limits."""
    chunks: list[list[Beat]] = []
    current: list[Beat] = []
    current_chars = 0
    current_voices: set[str] = set()
    for beat in beats:
        if not beat.is_narratable or beat.voice_id is None:
            continue
        text_len = len(beat.text)
        if text_len > _MAX_CHARS_PER_REQUEST:
            if current:
                chunks.append(current)
                current = []
                current_chars = 0
                current_voices = set()
            chunks.append([beat])
            continue
        would_overflow_chars = current_chars + text_len > _MAX_CHARS_PER_REQUEST
        adds_new_voice = beat.voice_id not in current_voices
        would_overflow_voices = (
            adds_new_voice
            and len(current_voices) >= _MAX_UNIQUE_VOICES_PER_REQUEST
        )
        if current and (would_overflow_chars or would_overflow_voices):
            chunks.append(current)
            current = []
            current_chars = 0
            current_voices = set()
        current.append(beat)
        current_chars += text_len
        current_voices.add(beat.voice_id)
    if current:
        chunks.append(current)
    return chunks
