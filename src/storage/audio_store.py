"""Per-book audio store. Callers pass value objects; the store owns all layout."""
import json
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Iterator, Literal, Mapping, Optional

from src.storage.objects import (
    APIRequest,
    MixOutputRef,
    SFXBeat,
    SFXBeatRef,
    SilenceClipRef,
    TrimStepRef,
    TTSBeat,
    TTSBeatRef,
    TTSChunk,
    TTSChunkRef,
    VoiceRequestRef,
)
from src.storage.storage import Storage

_AUTH_REDACTED = "Bearer ***"
_KEY_REDACTED = "***"
_SECRET_HEADER_NAMES = {"authorization", "xi-api-key", "x-api-key", "api-key"}


class AudioStore:
    """Single owner of the audio/voice artifact layout in storage."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def has_tts_beat(self, ref: TTSBeatRef) -> bool:
        return self._storage.exists(_tts_beat_key(ref))

    def save_tts_beat(
        self, beat: TTSBeat, api_request: Optional[APIRequest] = None,
    ) -> None:
        key = _tts_beat_key(beat.ref)
        self._storage.write_bytes(key, beat.audio)
        if api_request is not None:
            self._save_api_request(_sibling_request_key(key), api_request)

    def open_tts_beat(
        self, ref: TTSBeatRef, mode: Literal["r"] = "r",
    ) -> AbstractContextManager[Path]:
        return self._storage.local_path(_tts_beat_key(ref), mode)

    def has_tts_chunk(self, ref: TTSChunkRef) -> bool:
        return self._storage.exists(_tts_chunk_key(ref))

    def save_tts_chunk(
        self, chunk: TTSChunk, api_request: Optional[APIRequest] = None,
    ) -> None:
        key = _tts_chunk_key(chunk.ref)
        self._storage.write_bytes(key, chunk.audio)
        if api_request is not None:
            self._save_api_request(_sibling_request_key(key), api_request)

    def list_tts_chunks(
        self, book_id: str, provider: str, chapter_slug: str,
    ) -> list[TTSChunkRef]:
        prefix = _tts_chunk_dir(book_id, provider, chapter_slug)
        refs: list[TTSChunkRef] = []
        for key in self._storage.list_prefix(prefix):
            if not key.endswith(".mp3"):
                continue
            name = key.rsplit("/", 1)[-1]
            if not name.startswith("chunk_"):
                continue
            stem = name.removesuffix(".mp3").removeprefix("chunk_")
            try:
                index = int(stem)
            except ValueError:
                continue
            refs.append(TTSChunkRef(book_id, provider, chapter_slug, index))
        refs.sort(key=lambda r: r.index)
        return refs

    def has_tts_provider_outputs(self, book_id: str, provider: str) -> bool:
        prefix = _tts_provider_dir(book_id, provider)
        return bool(self._storage.list_prefix(prefix))

    def has_sfx_beat(self, ref: SFXBeatRef) -> bool:
        return self._storage.exists(_sfx_beat_key(ref))

    def save_sfx_beat(self, beat: SFXBeat) -> None:
        self._storage.write_bytes(_sfx_beat_key(beat.ref), beat.audio)

    def open_sfx_beat(
        self, ref: SFXBeatRef, mode: Literal["r", "w", "rw"],
    ) -> AbstractContextManager[Path]:
        return self._storage.local_path(_sfx_beat_key(ref), mode)

    def has_silence_clip(self, ref: SilenceClipRef) -> bool:
        return self._storage.exists(_silence_clip_key(ref))

    def open_silence_clip(
        self, ref: SilenceClipRef, mode: Literal["r", "w", "rw"],
    ) -> AbstractContextManager[Path]:
        return self._storage.local_path(_silence_clip_key(ref), mode)

    def open_mix_output(
        self, ref: MixOutputRef, mode: Literal["w"] = "w",
    ) -> AbstractContextManager[Path]:
        return self._storage.local_path(_mix_output_key(ref), mode)

    def open_trim_step(
        self, ref: TrimStepRef, mode: Literal["r", "w"],
    ) -> AbstractContextManager[Path]:
        return self._storage.local_path(_trim_step_key(ref), mode)

    def open_final_trimmed_beat(
        self, ref: TTSBeatRef, mode: Literal["r"] = "r",
    ) -> AbstractContextManager[Path]:
        return self._storage.local_path(
            _trim_step_key(TrimStepRef(beat=ref, step="final")), mode,
        )

    def delete_trim_artifacts(self, ref: TTSBeatRef) -> None:
        """Delete every chain intermediate and the final trimmed sibling for *ref*."""
        beat_key = _tts_beat_key(ref)
        stem = beat_key.removesuffix(".mp3") + _TRIM_PREFIX
        directory, _, _ = beat_key.rpartition("/")
        for sibling in self._storage.list_prefix(directory):
            if sibling.startswith(stem) and sibling.endswith(".mp3"):
                self._storage.delete(sibling, missing_ok=True)
        self._storage.delete(
            _trim_step_key(TrimStepRef(beat=ref, step="final")), missing_ok=True,
        )

    def absolute_path_of_tts_beat(self, ref: TTSBeatRef) -> Path:
        """Return a resolved filesystem path for *ref* (used by ffmpeg concat manifests)."""
        with self.open_tts_beat(ref) as path:
            return path.resolve()

    def absolute_path_of_silence_clip(self, ref: SilenceClipRef) -> Path:
        with self.open_silence_clip(ref, "r") as path:
            return path.resolve()

    def absolute_path_of_tts_chunk(self, ref: TTSChunkRef) -> Path:
        with self._storage.local_path(_tts_chunk_key(ref), "r") as path:
            return path.resolve()

    def absolute_path_of_final_trimmed_beat(self, ref: TTSBeatRef) -> Path:
        with self.open_final_trimmed_beat(ref) as path:
            return path.resolve()

    @contextmanager
    def with_concat_manifest(
        self, ref: MixOutputRef, lines: list[str],
    ) -> Iterator[Path]:
        """Write a concat manifest next to the mix output, yield its path, delete on exit."""
        manifest_key = _mix_manifest_key(ref)
        self._storage.write_text(manifest_key, "\n".join(lines) + "\n")
        try:
            with self._storage.local_path(manifest_key, "r") as path:
                yield path
        finally:
            self._storage.delete(manifest_key, missing_ok=True)

    def save_voice_request(
        self, ref: VoiceRequestRef, request: APIRequest,
    ) -> None:
        key = _voice_request_key(ref)
        self._save_api_request(key, request)

    def save_shared_voice_search(self, request: APIRequest) -> None:
        self._save_api_request(_shared_search_key(), request)

    def _save_api_request(self, key: str, request: APIRequest) -> None:
        payload = {
            "method": request.method.upper(),
            "url": request.url,
            "headers": _redact_headers(request.headers),
            "body": request.body,
        }
        self._storage.write_text(
            key, json.dumps(payload, indent=2, ensure_ascii=False),
        )


def _tts_beat_key(ref: TTSBeatRef) -> str:
    return f"{ref.book_id}/audio/tts/{ref.provider}/beat_{ref.index:04d}.mp3"


def _tts_chunk_key(ref: TTSChunkRef) -> str:
    return (
        f"{ref.book_id}/audio/tts/{ref.provider}/{ref.chapter_slug}"
        f"/chunk_{ref.index:04d}.mp3"
    )


def _tts_chunk_dir(book_id: str, provider: str, chapter_slug: str) -> str:
    return f"{book_id}/audio/tts/{provider}/{chapter_slug}"


def _tts_provider_dir(book_id: str, provider: str) -> str:
    return f"{book_id}/audio/tts/{provider}"


def _sfx_beat_key(ref: SFXBeatRef) -> str:
    return f"{ref.book_id}/audio/sfx/{ref.provider}/beat_{ref.index:04d}.{ref.extension}"


def _silence_clip_key(ref: SilenceClipRef) -> str:
    return (
        f"{ref.book_id}/audio/tts/{ref.provider}/silence_{ref.duration_ms}ms.mp3"
    )


def _mix_output_key(ref: MixOutputRef) -> str:
    return f"{ref.book_id}/audio/mix/{ref.provider}/{ref.chapter_slug}.mp3"


def _mix_manifest_key(ref: MixOutputRef) -> str:
    return f"{ref.book_id}/audio/mix/{ref.provider}/{ref.chapter_slug}.concat.txt"


_TRIM_PREFIX = ".trim_step_"


def _trim_step_key(ref: TrimStepRef) -> str:
    beat_key = _tts_beat_key(ref.beat)
    stem = beat_key.removesuffix(".mp3")
    if ref.step == "final":
        return f"{stem}.trimmed.mp3"
    return f"{stem}{_TRIM_PREFIX}{ref.step}.mp3"


def _voice_request_key(ref: VoiceRequestRef) -> str:
    return f"{ref.book_id}/voices/{ref.character_slug}/{ref.name}.request.json"


def _shared_search_key() -> str:
    return "_shared_voices/shared_search.request.json"


def _sibling_request_key(audio_key: str) -> str:
    return audio_key.removesuffix(".mp3") + ".request.json"


def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in headers.items():
        lower = name.lower()
        if lower == "authorization":
            out[name] = _AUTH_REDACTED
        elif lower in _SECRET_HEADER_NAMES:
            out[name] = _KEY_REDACTED
        else:
            out[name] = value
    return out


