"""Stitch per-beat TTS mp3s into one file per chapter via ffmpeg."""
import subprocess
from pathlib import Path
from typing import Optional

import structlog

from src.domain.beat import Beat
from src.domain.models import Book, Chapter
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)

_DEFAULT_GAP_SECONDS = 0.4


class MixWorkflow(Workflow):
    """Concatenate the TTS beat mp3s into one `chapter_NN.mp3` per chapter."""

    def __init__(
        self,
        repository: BookRepository,
        books_dir: Path = Path("books"),
        gap_seconds: float = _DEFAULT_GAP_SECONDS,
    ) -> None:
        self._repository = repository
        self._books_dir = books_dir
        self._gap_seconds = gap_seconds

    def run(self, request: WorkflowRequest) -> Book:
        book_id = get_book_id_from_url(request.url)
        logger.info("mix_workflow_started", book_id=book_id)

        book = self._repository.load(book_id)
        if book is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run all prior workflows first."
            )

        provider_dir = self._detect_provider_dir(book_id)
        if provider_dir is None:
            logger.warning("mix_workflow_no_tts_output", book_id=book_id)
            return book

        mix_dir = self._books_dir / book_id / "audio" / "mix"
        mix_dir.mkdir(parents=True, exist_ok=True)
        silence_path = self._ensure_silence_clip(provider_dir)

        file_index = 0
        voices = book.voice_assignments
        for chapter in book.content.chapters:
            beat_files: list[Path] = []
            for beat in chapter.beats:
                if not _was_synthesised(beat, voices):
                    continue
                file_index += 1
                beat_files.append(provider_dir / f"beat_{file_index:04d}.mp3")

            if not beat_files:
                logger.warning(
                    "mix_workflow_chapter_skipped_no_beats",
                    chapter=chapter.number,
                )
                continue

            missing = [p for p in beat_files if not p.exists()]
            if missing:
                logger.warning(
                    "mix_workflow_chapter_skipped_files_missing",
                    chapter=chapter.number,
                    missing_count=len(missing),
                    first_missing=str(missing[0]),
                )
                continue

            self._stitch_chapter(chapter, beat_files, silence_path, mix_dir)

        self._repository.save(book)
        logger.info("mix_workflow_complete", book_id=book_id)
        return book

    def _detect_provider_dir(self, book_id: str) -> Optional[Path]:
        tts_dir = self._books_dir / book_id / "audio" / "tts"
        if not tts_dir.is_dir():
            return None
        subdirs = [d for d in tts_dir.iterdir() if d.is_dir()]
        if not subdirs:
            return None
        if len(subdirs) > 1:
            names = sorted(d.name for d in subdirs)
            raise ValueError(
                f"Multiple TTS provider directories present in {tts_dir}: {names}. "
                "Remove the ones you don't want to mix.",
            )
        return subdirs[0]

    def _ensure_silence_clip(self, provider_dir: Path) -> Path:
        duration_ms = int(round(self._gap_seconds * 1000))
        silence_path = provider_dir / f"silence_{duration_ms}ms.mp3"
        if silence_path.exists():
            return silence_path
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(self._gap_seconds),
            "-q:a", "9",
            "-acodec", "libmp3lame",
            str(silence_path),
        ])
        return silence_path

    def _stitch_chapter(
        self,
        chapter: Chapter,
        beat_files: list[Path],
        silence_path: Path,
        mix_dir: Path,
    ) -> None:
        output_path = mix_dir / f"chapter_{chapter.number:02d}.mp3"
        concat_list = mix_dir / f"chapter_{chapter.number:02d}.concat.txt"

        with concat_list.open("w", encoding="utf-8") as f:
            for i, beat_file in enumerate(beat_files):
                if i > 0:
                    f.write(f"file '{silence_path.resolve().as_posix()}'\n")
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
                beat_count=len(beat_files),
                output_path=str(output_path),
            )
        finally:
            concat_list.unlink(missing_ok=True)


def _was_synthesised(beat: Beat, voice_assignments: dict[int, str]) -> bool:
    return (
        beat.is_narratable
        and beat.character_id is not None
        and beat.character_id in voice_assignments
    )


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}): "
            f"cmd={' '.join(cmd)} stderr={result.stderr}",
        )
