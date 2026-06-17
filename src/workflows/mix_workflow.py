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


class MixWorkflow(Workflow):
    """Concatenate the TTS beat mp3s into one `chapter_NN.mp3` per chapter."""

    def __init__(
        self,
        repositories: list[BookRepository],
        provider_name: str,
        books_dir: Path = Path("books"),
        gap_seconds_by_beat_type: Optional[dict[BeatType, float]] = None,
        trimmer_pipeline: Optional[AudioTrimmerPipeline] = None,
    ) -> None:
        self._repositories = repositories
        self._provider_name = provider_name
        self._books_dir = books_dir
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

        provider_dir = (
            self._books_dir / book_id / "audio" / "tts" / self._provider_name
        )
        if not provider_dir.is_dir():
            logger.warning(
                "mix_workflow_no_tts_output",
                book_id=book_id,
                provider_dir=str(provider_dir),
            )
            return book

        mix_dir = (
            self._books_dir / book_id / "audio" / "mix" / self._provider_name
        )
        mix_dir.mkdir(parents=True, exist_ok=True)

        if self._provider_name == _DIALOGUE_PROVIDER_NAME:
            self._mix_dialogue_chapters(book, provider_dir, mix_dir, request)
        else:
            self._mix_beat_chapters(book, provider_dir, mix_dir, request)

        for repository in self._repositories:
            repository.save(book)
        logger.info("mix_workflow_complete", book_id=book_id)
        return book

    def _mix_beat_chapters(
        self,
        book: Book,
        provider_dir: Path,
        mix_dir: Path,
        request: WorkflowRequest,
    ) -> None:
        silence_paths = self._ensure_silence_clips(provider_dir)
        file_index = 0
        voices = book.voice_assignments
        for chapter in _chapters_in_range(book, request):
            beat_pairs: list[tuple[Beat, Path]] = []
            for beat in chapter.beats:
                if not _was_synthesised(beat, voices):
                    continue
                file_index += 1
                beat_pairs.append((beat, provider_dir / f"beat_{file_index:04d}.mp3"))

            if not beat_pairs:
                logger.warning(
                    "mix_workflow_chapter_skipped_no_beats",
                    chapter=chapter.number,
                )
                continue

            missing = [p for _, p in beat_pairs if not p.exists()]
            if missing:
                logger.warning(
                    "mix_workflow_chapter_skipped_files_missing",
                    chapter=chapter.number,
                    missing_count=len(missing),
                    first_missing=str(missing[0]),
                )
                continue

            self._stitch_chapter(chapter, beat_pairs, silence_paths, mix_dir)

    def _mix_dialogue_chapters(
        self,
        book: Book,
        provider_dir: Path,
        mix_dir: Path,
        request: WorkflowRequest,
    ) -> None:
        for chapter in _chapters_in_range(book, request):
            chunk_dir = provider_dir / chapter.dir_slug
            if not chunk_dir.is_dir():
                logger.warning(
                    "mix_workflow_chapter_skipped_no_chunks",
                    chapter=chapter.number,
                    chunk_dir=str(chunk_dir),
                )
                continue
            chunks = sorted(chunk_dir.glob("chunk_*.mp3"))
            if not chunks:
                logger.warning(
                    "mix_workflow_chapter_skipped_no_chunks",
                    chapter=chapter.number,
                    chunk_dir=str(chunk_dir),
                )
                continue
            self._concat_chunks(chapter, chunks, mix_dir)

    def _ensure_silence_clips(self, provider_dir: Path) -> dict[float, Path]:
        unique_durations = set(self._gap_seconds_by_beat_type.values())
        unique_durations.add(_FALLBACK_GAP_SECONDS)
        return {d: self._ensure_silence_clip(provider_dir, d) for d in unique_durations}

    def _ensure_silence_clip(self, provider_dir: Path, gap_seconds: float) -> Path:
        duration_ms = int(round(gap_seconds * 1000))
        silence_path = provider_dir / f"silence_{duration_ms}ms.mp3"
        if silence_path.exists():
            return silence_path
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(gap_seconds),
            "-q:a", "9",
            "-acodec", "libmp3lame",
            str(silence_path),
        ])
        return silence_path

    def _gap_for(self, beat: Beat) -> float:
        return self._gap_seconds_by_beat_type.get(beat.beat_type, _FALLBACK_GAP_SECONDS)

    def _concat_chunks(
        self,
        chapter: Chapter,
        chunks: list[Path],
        mix_dir: Path,
    ) -> None:
        output_path = mix_dir / f"{chapter.dir_slug}.mp3"
        concat_list = mix_dir / f"{chapter.dir_slug}.concat.txt"

        with concat_list.open("w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(f"file '{chunk.resolve().as_posix()}'\n")

        try:
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ])
            logger.info(
                "mix_workflow_chapter_concatenated",
                chapter=chapter.number,
                chunk_count=len(chunks),
                output_path=str(output_path),
            )
        finally:
            concat_list.unlink(missing_ok=True)

    def _stitch_chapter(
        self,
        chapter: Chapter,
        beat_pairs: list[tuple[Beat, Path]],
        silence_paths: dict[float, Path],
        mix_dir: Path,
    ) -> None:
        output_path = mix_dir / f"{chapter.dir_slug}.mp3"
        concat_list = mix_dir / f"{chapter.dir_slug}.concat.txt"

        effective_pairs = self._trimmer_pipeline.apply(beat_pairs)

        with concat_list.open("w", encoding="utf-8") as f:
            for i, (beat, beat_file) in enumerate(effective_pairs):
                if i > 0:
                    prev_beat = effective_pairs[i - 1][0]
                    silence = silence_paths[self._gap_for(prev_beat)]
                    f.write(f"file '{silence.resolve().as_posix()}'\n")
                f.write(f"file '{beat_file.resolve().as_posix()}'\n")

        try:
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ])
            logger.info(
                "mix_workflow_chapter_stitched",
                chapter=chapter.number,
                beat_count=len(beat_pairs),
                output_path=str(output_path),
            )
            self._trimmer_pipeline.cleanup(effective_pairs, beat_pairs)
        finally:
            concat_list.unlink(missing_ok=True)


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
