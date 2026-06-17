"""Per-book audio key layout and IO, composed on top of Storage."""
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Iterator

from src.storage.storage import LocalPathMode, Storage


class AudioStore:
    """Owns the per-book key layout for TTS, SFX, dialogue chunks, silence clips, and mixes."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @property
    def storage(self) -> Storage:
        return self._storage

    def tts_beat_key(self, book_id: str, provider: str, beat_index: int) -> str:
        """Key for one per-beat TTS mp3."""
        return f"{book_id}/audio/tts/{provider}/beat_{beat_index:04d}.mp3"

    def tts_chunk_key(
        self, book_id: str, provider: str, chapter_slug: str, chunk_index: int,
    ) -> str:
        """Key for one dialogue-API chunk mp3."""
        return f"{book_id}/audio/tts/{provider}/{chapter_slug}/chunk_{chunk_index:04d}.mp3"

    def tts_chunk_prefix(
        self, book_id: str, provider: str, chapter_slug: str,
    ) -> str:
        """Prefix listing dialogue-API chunk mp3s for a chapter."""
        return f"{book_id}/audio/tts/{provider}/{chapter_slug}"

    def tts_provider_prefix(self, book_id: str, provider: str) -> str:
        """Prefix for all per-beat TTS outputs of one provider."""
        return f"{book_id}/audio/tts/{provider}"

    def sfx_beat_key(
        self, book_id: str, provider: str, beat_index: int, extension: str = "mp3",
    ) -> str:
        """Key for one per-beat SFX clip."""
        return f"{book_id}/audio/sfx/{provider}/beat_{beat_index:04d}.{extension}"

    def silence_clip_key(self, book_id: str, provider: str, duration_ms: int) -> str:
        """Key for a cached silence clip the mix workflow stitches between beats."""
        return f"{book_id}/audio/tts/{provider}/silence_{duration_ms}ms.mp3"

    def mix_output_key(
        self, book_id: str, provider: str, chapter_slug: str,
    ) -> str:
        """Key for one final per-chapter mix output."""
        return f"{book_id}/audio/mix/{provider}/{chapter_slug}.mp3"

    def mix_concat_manifest_key(
        self, book_id: str, provider: str, chapter_slug: str,
    ) -> str:
        """Key for the ffmpeg concat manifest used to stitch one chapter."""
        return f"{book_id}/audio/mix/{provider}/{chapter_slug}.concat.txt"

    def voice_artifact_key(
        self, book_id: str, character_slug: str, filename: str,
    ) -> str:
        """Key for a per-character voice request artifact."""
        return f"{book_id}/voices/{character_slug}/{filename}"

    def shared_voice_artifact_key(self, filename: str) -> str:
        """Key for a shared-voice search artifact, not scoped to a book."""
        return f"_shared_voices/{filename}"

    def write_bytes(self, key: str, data: bytes) -> None:
        self._storage.write_bytes(key, data)

    def read_bytes(self, key: str) -> bytes:
        return self._storage.read_bytes(key)

    def write_text(self, key: str, text: str) -> None:
        self._storage.write_text(key, text)

    def exists(self, key: str) -> bool:
        return self._storage.exists(key)

    def size(self, key: str) -> int:
        return self._storage.size(key)

    def delete(self, key: str, missing_ok: bool = True) -> None:
        self._storage.delete(key, missing_ok=missing_ok)

    def list_prefix(self, prefix: str) -> list[str]:
        return self._storage.list_prefix(prefix)

    def local_path(self, key: str, mode: LocalPathMode) -> AbstractContextManager[Path]:
        return self._storage.local_path(key, mode)

    def iter_chunk_keys(
        self, book_id: str, provider: str, chapter_slug: str,
    ) -> Iterator[str]:
        """Yield every dialogue-API chunk key for a chapter in sorted order."""
        prefix = self.tts_chunk_prefix(book_id, provider, chapter_slug)
        for key in self.list_prefix(prefix):
            if key.endswith(".mp3") and "/chunk_" in key:
                yield key
