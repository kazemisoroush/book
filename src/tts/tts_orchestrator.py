"""TTS synthesis orchestrator for a single book chapter.

Responsibilities
----------------
1. Iterate all segments in the requested chapter.
2. Skip ILLUSTRATION, COPYRIGHT, and OTHER segments.
3. Synthesise NARRATION and DIALOGUE segments via the injected TTSProvider.
4. Write per-segment MP3 files to a temporary sub-directory.
5. Concatenate the per-segment files into ``chapter_01.mp3`` using ffmpeg.
6. Save the full :class:`~src.domain.models.Book` as ``book.json`` in the
   output directory (a byproduct — useful for inspection and replay).
7. Return the :class:`~pathlib.Path` to the final stitched MP3.

Concatentation uses ffmpeg's ``concat`` demuxer (a list file approach) which
is the most reliable method for concatenating MP3 files without re-encoding.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import structlog

from src.domain.models import Book, SegmentType
from src.tts.tts_provider import TTSProvider

logger = structlog.get_logger(__name__)

# Segment types that should be synthesised to audio.
_SYNTHESISE_TYPES = {SegmentType.NARRATION, SegmentType.DIALOGUE}


class TTSOrchestrator:
    """Orchestrates TTS synthesis for a single chapter of a :class:`Book`.

    Usage::

        orchestrator = TTSOrchestrator(provider, output_dir=Path("output"))
        path = orchestrator.synthesize_chapter(book, chapter_number=1, voice_assignment)

    Args:
        provider: A :class:`~src.tts.tts_provider.TTSProvider` implementation.
        output_dir: Directory where ``book.json`` and ``chapter_01.mp3`` are
                    written.  Created if it does not exist.
    """

    def __init__(self, provider: TTSProvider, output_dir: Path) -> None:
        self._provider = provider
        self._output_dir = output_dir

    def synthesize_chapter(
        self,
        book: Book,
        chapter_number: int,
        voice_assignment: dict[str, str],
    ) -> Path:
        """Synthesise all speakable segments in *chapter_number* and stitch them.

        Args:
            book: The :class:`~src.domain.models.Book` to synthesise.
            chapter_number: 1-based chapter index (must exist in the book).
            voice_assignment: Mapping from ``character_id`` to ElevenLabs
                              ``voice_id``, as returned by
                              :class:`~src.tts.voice_assigner.VoiceAssigner`.

        Returns:
            Path to the stitched ``chapter_01.mp3`` (or ``chapter_NN.mp3`` for
            chapters beyond 1).

        Raises:
            ValueError: If *chapter_number* is not found in the book.
            RuntimeError: If ffmpeg fails during stitching.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Locate the chapter
        chapter = next(
            (ch for ch in book.content.chapters if ch.number == chapter_number),
            None,
        )
        if chapter is None:
            raise ValueError(
                f"Chapter {chapter_number} not found in book "
                f"(available: {[ch.number for ch in book.content.chapters]})"
            )

        logger.info(
            "tts_chapter_start",
            chapter_number=chapter_number,
            chapter_title=chapter.title,
        )

        # Save book.json
        self._save_book_json(book)

        # Synthesise each speakable segment into a temp directory
        with tempfile.TemporaryDirectory(prefix="tts_segments_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            segment_paths = self._synthesise_segments(
                chapter, voice_assignment, tmp_path
            )

            # Stitch segments into final chapter MP3
            chapter_filename = f"chapter_{chapter_number:02d}.mp3"
            output_mp3 = self._output_dir / chapter_filename
            self._stitch_with_ffmpeg(segment_paths, output_mp3)

        logger.info(
            "tts_chapter_done",
            chapter_number=chapter_number,
            output=str(output_mp3),
        )
        return output_mp3

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save_book_json(self, book: Book) -> None:
        """Write ``book.json`` to the output directory."""
        book_json_path = self._output_dir / "book.json"
        book_dict = book.to_dict()
        with open(book_json_path, "w", encoding="utf-8") as f:
            json.dump(book_dict, f, indent=2, ensure_ascii=False)
        logger.info("book_json_saved", path=str(book_json_path))

    def _synthesise_segments(
        self,
        chapter: object,
        voice_assignment: dict[str, str],
        tmp_dir: Path,
    ) -> list[Path]:
        """Synthesise all speakable segments; return list of created paths."""
        from src.domain.models import Chapter as ChapterModel  # local import for type

        chapter_typed: ChapterModel = chapter  # type: ignore[assignment]

        segment_paths: list[Path] = []
        seg_index = 0

        for section in chapter_typed.sections:
            if section.segments is None:
                continue

            for segment in section.segments:
                if segment.segment_type not in _SYNTHESISE_TYPES:
                    logger.debug(
                        "tts_segment_skipped",
                        segment_type=segment.segment_type.value,
                        text_preview=segment.text[:40],
                    )
                    continue

                # Resolve voice_id — fall back to narrator voice if unknown
                character_id = segment.character_id or "narrator"
                voice_id = voice_assignment.get(
                    character_id,
                    voice_assignment.get("narrator", ""),
                )

                seg_path = tmp_dir / f"seg_{seg_index:04d}.mp3"
                logger.debug(
                    "tts_segment_synthesise",
                    segment_index=seg_index,
                    segment_type=segment.segment_type.value,
                    character_id=character_id,
                    voice_id=voice_id,
                )

                self._provider.synthesize(segment.text, voice_id, seg_path)
                segment_paths.append(seg_path)
                seg_index += 1

        return segment_paths

    def _stitch_with_ffmpeg(
        self,
        segment_paths: list[Path],
        output_path: Path,
    ) -> None:
        """Concatenate *segment_paths* into *output_path* using ffmpeg.

        Uses the ``concat`` demuxer (list-file approach) which does not
        re-encode the audio — segments are joined as-is.

        Args:
            segment_paths: Ordered list of MP3 segment files.
            output_path: Destination MP3 file path.

        Raises:
            RuntimeError: If ffmpeg exits with a non-zero return code or if
                          there are no segments to stitch.
        """
        if not segment_paths:
            logger.warning("tts_stitch_no_segments", output=str(output_path))
            # Create an empty file so the return value is still valid
            output_path.touch()
            return

        # Build the concat list file in the same temp dir as segments
        concat_dir = segment_paths[0].parent
        concat_list_path = concat_dir / "concat_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for seg_path in segment_paths:
                # ffmpeg concat list syntax: one line per file
                f.write(f"file '{seg_path.as_posix()}'\n")

        cmd = [
            "ffmpeg",
            "-y",                     # overwrite output without asking
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            str(output_path),
        ]

        logger.info(
            "tts_ffmpeg_stitch",
            segment_count=len(segment_paths),
            output=str(output_path),
        )

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
