"""Stitch per-beat or per-chunk TTS mp3s into one file per chapter via ffmpeg."""
import subprocess
from pathlib import Path
from typing import Optional

import structlog

from src.audio.tts.audio_trimmer.audio_trimmer_pipeline import AudioTrimmerPipeline
from src.domain.beat import Beat, BeatType
from src.domain.models import Book, Chapter
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.storage.audio_store import AudioStore
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)

_FALLBACK_GAP_SECONDS = 1.0

_DEFAULT_GAP_SECONDS_BY_BEAT_TYPE: dict[BeatType, float] = {
    BeatType.BOOK_TITLE: 3.5,
    BeatType.CHAPTER_ANNOUNCEMENT: 2.0,
    BeatType.NARRATION: 1.0,
    BeatType.DIALOGUE: 0.8,
}

_DIALOGUE_PROVIDER_NAME = "elevenlabs_dialogue"
_DIALOGUE_CHUNK_GAP_SECONDS = 1.0


class MixWorkflow(Workflow):
    """Concatenate the TTS beat mp3s into one `chapter_NN.mp3` per chapter."""

    def __init__(
        self,
        repositories: list[BookRepository],
        provider_name: str,
        audio_store: AudioStore,
        gap_seconds_by_beat_type: Optional[dict[BeatType, float]] = None,
        trimmer_pipeline: Optional[AudioTrimmerPipeline] = None,
    ) -> None:
        self._repositories = repositories
        self._provider_name = provider_name
        self._audio_store = audio_store
        self._gap_seconds_by_beat_type: dict[BeatType, float] = {
            **_DEFAULT_GAP_SECONDS_BY_BEAT_TYPE,
            **(gap_seconds_by_beat_type or {}),
        }
        self._trimmer_pipeline = trimmer_pipeline or AudioTrimmerPipeline()

    def run(self, request: WorkflowRequest) -> Book:
        book_id = get_book_id_from_url(request.url)
        logger.info("mix_workflow_started", book_id=book_id)

        book = self._repositories[0].load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run all prior workflows first."
            )

        provider_prefix = self._audio_store.tts_provider_prefix(
            book_id, self._provider_name,
        )
        if not self._audio_store.list_prefix(provider_prefix):
            logger.warning(
                "mix_workflow_no_tts_output",
                book_id=book_id,
                provider_prefix=provider_prefix,
            )
            return book

        if self._provider_name == _DIALOGUE_PROVIDER_NAME:
            self._mix_dialogue_chapters(book, book_id, request)
        else:
            self._mix_beat_chapters(book, book_id, request)

        for repository in self._repositories:
            repository.save(book)
        logger.info("mix_workflow_complete", book_id=book_id)
        return book

    def _mix_beat_chapters(
        self,
        book: Book,
        book_id: str,
        request: WorkflowRequest,
    ) -> None:
        silence_keys = self._ensure_silence_clips(book_id)
        file_index = 0
        voices = book.voice_assignments
        for chapter in _chapters_in_range(book, request):
            beat_pairs: list[tuple[Beat, str]] = []
            for beat in chapter.beats:
                if not _was_synthesised(beat, voices):
                    continue
                file_index += 1
                beat_pairs.append((
                    beat,
                    self._audio_store.tts_beat_key(
                        book_id, self._provider_name, file_index,
                    ),
                ))

            if not beat_pairs:
                logger.warning(
                    "mix_workflow_chapter_skipped_no_beats",
                    chapter=chapter.number,
                )
                continue

            missing = [k for _, k in beat_pairs if not self._audio_store.exists(k)]
            if missing:
                logger.warning(
                    "mix_workflow_chapter_skipped_files_missing",
                    chapter=chapter.number,
                    missing_count=len(missing),
                    first_missing=missing[0],
                )
                continue

            self._stitch_chapter(chapter, book_id, beat_pairs, silence_keys)

    def _mix_dialogue_chapters(
        self,
        book: Book,
        book_id: str,
        request: WorkflowRequest,
    ) -> None:
        silence_key = self._ensure_silence_clip(
            book_id, _DIALOGUE_CHUNK_GAP_SECONDS,
        )
        for chapter in _chapters_in_range(book, request):
            chunk_keys = sorted(self._audio_store.iter_chunk_keys(
                book_id, self._provider_name, chapter.dir_slug,
            ))
            if not chunk_keys:
                logger.warning(
                    "mix_workflow_chapter_skipped_no_chunks",
                    chapter=chapter.number,
                    chapter_slug=chapter.dir_slug,
                )
                continue
            self._concat_chunks(chapter, book_id, chunk_keys, silence_key)

    def _ensure_silence_clips(self, book_id: str) -> dict[float, str]:
        unique_durations = set(self._gap_seconds_by_beat_type.values())
        unique_durations.add(_FALLBACK_GAP_SECONDS)
        return {d: self._ensure_silence_clip(book_id, d) for d in unique_durations}

    def _ensure_silence_clip(self, book_id: str, gap_seconds: float) -> str:
        duration_ms = int(round(gap_seconds * 1000))
        key = self._audio_store.silence_clip_key(
            book_id, self._provider_name, duration_ms,
        )
        if self._audio_store.exists(key):
            return key
        with self._audio_store.local_path(key, "w") as silence_path:
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(gap_seconds),
                "-q:a", "9",
                "-acodec", "libmp3lame",
                str(silence_path),
            ])
        return key

    def _gap_for(self, beat: Beat) -> float:
        return self._gap_seconds_by_beat_type.get(beat.beat_type, _FALLBACK_GAP_SECONDS)

    def _concat_chunks(
        self,
        chapter: Chapter,
        book_id: str,
        chunk_keys: list[str],
        silence_key: str,
    ) -> None:
        output_key = self._audio_store.mix_output_key(
            book_id, self._provider_name, chapter.dir_slug,
        )
        manifest_key = self._audio_store.mix_concat_manifest_key(
            book_id, self._provider_name, chapter.dir_slug,
        )
        manifest_text = _build_manifest(chunk_keys, silence_key, self._audio_store)
        self._audio_store.write_text(manifest_key, manifest_text)

        try:
            with self._audio_store.local_path(manifest_key, "r") as manifest_path:
                with self._audio_store.local_path(output_key, "w") as output_path:
                    _run_ffmpeg([
                        "ffmpeg", "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", str(manifest_path),
                        "-c", "copy",
                        str(output_path),
                    ])
            logger.info(
                "mix_workflow_chapter_concatenated",
                chapter=chapter.number,
                chunk_count=len(chunk_keys),
                output_key=output_key,
            )
        finally:
            self._audio_store.delete(manifest_key, missing_ok=True)

    def _stitch_chapter(
        self,
        chapter: Chapter,
        book_id: str,
        beat_pairs: list[tuple[Beat, str]],
        silence_keys: dict[float, str],
    ) -> None:
        output_key = self._audio_store.mix_output_key(
            book_id, self._provider_name, chapter.dir_slug,
        )
        manifest_key = self._audio_store.mix_concat_manifest_key(
            book_id, self._provider_name, chapter.dir_slug,
        )

        effective_pairs = self._trimmer_pipeline.apply(beat_pairs, self._audio_store)
        manifest_text = _build_stitch_manifest(
            effective_pairs, silence_keys, self._gap_for, self._audio_store,
        )
        self._audio_store.write_text(manifest_key, manifest_text)

        try:
            with self._audio_store.local_path(manifest_key, "r") as manifest_path:
                with self._audio_store.local_path(output_key, "w") as output_path:
                    _run_ffmpeg([
                        "ffmpeg", "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", str(manifest_path),
                        "-c", "copy",
                        str(output_path),
                    ])
            logger.info(
                "mix_workflow_chapter_stitched",
                chapter=chapter.number,
                beat_count=len(beat_pairs),
                output_key=output_key,
            )
            self._trimmer_pipeline.cleanup(effective_pairs, beat_pairs, self._audio_store)
        finally:
            self._audio_store.delete(manifest_key, missing_ok=True)


def _build_manifest(
    chunk_keys: list[str], silence_key: str, audio_store: AudioStore,
) -> str:
    lines: list[str] = []
    silence_path = _resolve_local_path(silence_key, audio_store)
    for i, chunk_key in enumerate(chunk_keys):
        if i > 0:
            lines.append(f"file '{silence_path}'")
        chunk_path = _resolve_local_path(chunk_key, audio_store)
        lines.append(f"file '{chunk_path}'")
    return "\n".join(lines) + "\n"


def _build_stitch_manifest(
    effective_pairs: list[tuple[Beat, str]],
    silence_keys: dict[float, str],
    gap_for: object,
    audio_store: AudioStore,
) -> str:
    lines: list[str] = []
    for i, (beat, beat_key) in enumerate(effective_pairs):
        if i > 0:
            prev_beat = effective_pairs[i - 1][0]
            silence_key = silence_keys[gap_for(prev_beat)]  # type: ignore[operator]
            lines.append(f"file '{_resolve_local_path(silence_key, audio_store)}'")
        lines.append(f"file '{_resolve_local_path(beat_key, audio_store)}'")
    return "\n".join(lines) + "\n"


def _resolve_local_path(key: str, audio_store: AudioStore) -> str:
    """Return the absolute filesystem path for *key* using the storage's local_path."""
    with audio_store.local_path(key, "r") as path:
        return Path(path).resolve().as_posix()


def _was_synthesised(beat: Beat, voice_assignments: dict[int, str]) -> bool:
    return (
        beat.is_narratable
        and beat.character_id is not None
        and beat.character_id in voice_assignments
    )


def _chapters_in_range(
    book: Book, request: WorkflowRequest,
) -> list[Chapter]:
    end_chapter = request.end_chapter
    return [
        chapter for chapter in book.content.chapters
        if chapter.number >= request.start_chapter
        and (end_chapter is None or chapter.number <= end_chapter)
    ]


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}): "
            f"cmd={' '.join(cmd)} stderr={result.stderr}",
        )
