"""ElevenLabs Text-to-Dialogue TTS provider for chapter-level multi-voice synthesis."""
import os
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.tts.tts_provider import TTSProvider
from src.domain.beat import Beat
from src.repository.api_artifact_store import APIArtifactStore

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

    def __init__(
        self,
        api_key: str,
        books_dir: "Path | None" = None,
        artifact_store: Optional[APIArtifactStore] = None,
    ) -> None:
        self.api_key = api_key
        self._books_dir = books_dir or Path("books")
        self._client: Any = None
        self._chunk_counter = 0
        self._artifact_store = artifact_store

    def provide(self, beat: Beat, book_id: str) -> Optional[str]:
        """Synthesise a single *beat* as a one-line dialogue chunk."""
        return self._synthesize_chunk([beat], book_id)

    def provide_collection(
        self, beats: list[Beat], book_id: str,
    ) -> list[Optional[str]]:
        """Chunk *beats* under the dialogue API limits and synthesise each chunk."""
        request_ids: list[Optional[str]] = []
        for chunk in _chunk_beats(beats):
            request_id = self._synthesize_chunk(chunk, book_id)
            request_ids.extend([request_id] * len(chunk))
        return request_ids

    def _get_client(self) -> Any:
        if self._client is None:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    def _synthesize_chunk(
        self, beats: list[Beat], book_id: str,
    ) -> Optional[str]:
        if not beats:
            return None
        self._chunk_counter += 1
        output_path = (
            self._books_dir / book_id / "audio" / "tts" / self.name
            / f"chunk_{self._chunk_counter:04d}.mp3"
        )
        os.makedirs(output_path.parent, exist_ok=True)
        if output_path.exists() and output_path.stat().st_size > 0:
            return None

        inputs = [
            {"text": beat.text, "voice_id": beat.voice_id}
            for beat in beats
        ]

        logger.info(
            "elevenlabs_dialogue_synthesize_start",
            line_count=len(inputs),
            total_chars=sum(len(beat.text) for beat in beats),
            unique_voices=len({beat.voice_id for beat in beats}),
            output_path=str(output_path),
        )

        if self._artifact_store is not None:
            self._artifact_store.save_request(
                path=output_path.with_suffix(".request.json"),
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
            with open(output_path, "wb") as f:
                for chunk in raw_response.data:
                    f.write(chunk)

        logger.info(
            "elevenlabs_dialogue_synthesize_done",
            output_path=str(output_path),
            request_id=request_id,
        )
        return request_id


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
