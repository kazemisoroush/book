"""Stitch per-beat or per-chunk TTS mp3s into one file per chapter via ffmpeg."""
import subprocess
from typing import Optional

import structlog

from src.audio.tts.audio_trimmer.audio_trimmer_pipeline import AudioTrimmerPipeline
from src.domain.beat import Beat, BeatType
from src.domain.models import Book, Chapter
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.storage.audio_store import AudioStore
from src.storage.objects import (
    MixOutputRef,
    SilenceClipRef,
    TTSBeatRef,
    TTSChunkRef,
)
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

        if not self._audio_store.has_tts_provider_outputs(book_id, self._provider_name):
            logger.warning(
                "mix_workflow_no_tts_output",
                book_id=book_id, provider=self._provider_name,
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
        silence_refs = self._ensure_silence_clips(book_id)
        file_index = 0
        voices = book.voice_assignments
        for chapter in _chapters_in_range(book, request):
            beat_pairs: list[tuple[Beat, TTSBeatRef]] = []
            for beat in chapter.beats:
                if not _was_synthesised(beat, voices):
                    continue
                file_index += 1
                beat_pairs.append((
                    beat,
                    TTSBeatRef(
                        book_id=book_id,
                        provider=self._provider_name,
                        index=file_index,
                    ),
                ))

            if not beat_pairs:
                logger.warning(
                    "mix_workflow_chapter_skipped_no_beats",
                    chapter=chapter.number,
                )
                continue

            missing = [r for _, r in beat_pairs if not self._audio_store.has_tts_beat(r)]
            if missing:
                logger.warning(
                    "mix_workflow_chapter_skipped_files_missing",
                    chapter=chapter.number,
                    missing_count=len(missing),
                    first_missing=missing[0],
                )
                continue

            self._stitch_chapter(chapter, book_id, beat_pairs, silence_refs)

    def _mix_dialogue_chapters(
        self,
        book: Book,
        book_id: str,
        request: WorkflowRequest,
    ) -> None:
        silence_ref = self._ensure_silence_clip(book_id, _DIALOGUE_CHUNK_GAP_SECONDS)
        for chapter in _chapters_in_range(book, request):
            chunk_refs = self._audio_store.list_tts_chunks(
                book_id, self._provider_name, chapter.dir_slug,
            )
            if not chunk_refs:
                logger.warning(
                    "mix_workflow_chapter_skipped_no_chunks",
                    chapter=chapter.number,
                    chapter_slug=chapter.dir_slug,
                )
                continue
            self._concat_chunks(chapter, book_id, chunk_refs, silence_ref)

    def _ensure_silence_clips(self, book_id: str) -> dict[float, SilenceClipRef]:
        unique_durations = set(self._gap_seconds_by_beat_type.values())
        unique_durations.add(_FALLBACK_GAP_SECONDS)
        return {d: self._ensure_silence_clip(book_id, d) for d in unique_durations}

    def _ensure_silence_clip(self, book_id: str, gap_seconds: float) -> SilenceClipRef:
        duration_ms = int(round(gap_seconds * 1000))
        ref = SilenceClipRef(
            book_id=book_id, provider=self._provider_name, duration_ms=duration_ms,
        )
        if self._audio_store.has_silence_clip(ref):
            return ref
        with self._audio_store.open_silence_clip(ref, "w") as silence_path:
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(gap_seconds),
                "-q:a", "9",
                "-acodec", "libmp3lame",
                str(silence_path),
            ])
        return ref

    def _gap_for(self, beat: Beat) -> float:
        return self._gap_seconds_by_beat_type.get(beat.beat_type, _FALLBACK_GAP_SECONDS)

    def _concat_chunks(
        self,
        chapter: Chapter,
        book_id: str,
        chunk_refs: list[TTSChunkRef],
        silence_ref: SilenceClipRef,
    ) -> None:
        output_ref = MixOutputRef(
            book_id=book_id, provider=self._provider_name, chapter_slug=chapter.dir_slug,
        )
        silence_line = _file_line(self._audio_store.absolute_path_of_silence_clip(silence_ref))
        lines: list[str] = []
        for i, chunk_ref in enumerate(chunk_refs):
            if i > 0:
                lines.append(silence_line)
            lines.append(_file_line(self._audio_store.absolute_path_of_tts_chunk(chunk_ref)))

        with self._audio_store.with_concat_manifest(output_ref, lines) as manifest_path:
            with self._audio_store.open_mix_output(output_ref) as output_path:
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
            chunk_count=len(chunk_refs),
        )

    def _stitch_chapter(
        self,
        chapter: Chapter,
        book_id: str,
        beat_pairs: list[tuple[Beat, TTSBeatRef]],
        silence_refs: dict[float, SilenceClipRef],
    ) -> None:
        output_ref = MixOutputRef(
            book_id=book_id, provider=self._provider_name, chapter_slug=chapter.dir_slug,
        )

        effective_pairs = self._trimmer_pipeline.apply(beat_pairs, self._audio_store)
        beat_path_lookup = (
            self._audio_store.absolute_path_of_final_trimmed_beat
            if self._trimmer_pipeline.has_trimmers()
            else self._audio_store.absolute_path_of_tts_beat
        )
        lines: list[str] = []
        for i, (beat, beat_ref) in enumerate(effective_pairs):
            if i > 0:
                prev_beat = effective_pairs[i - 1][0]
                silence_ref = silence_refs[self._gap_for(prev_beat)]
                lines.append(_file_line(
                    self._audio_store.absolute_path_of_silence_clip(silence_ref),
                ))
            lines.append(_file_line(beat_path_lookup(beat_ref)))

        with self._audio_store.with_concat_manifest(output_ref, lines) as manifest_path:
            with self._audio_store.open_mix_output(output_ref) as output_path:
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
        )
        self._trimmer_pipeline.cleanup(effective_pairs, beat_pairs, self._audio_store)


def _file_line(path) -> str:
    return f"file '{path.as_posix()}'"


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
