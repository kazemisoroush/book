"""TTS synthesis orchestrator for a single book chapter.

Responsibilities
----------------
1. Iterate all segments in the requested chapter.
2. Skip ILLUSTRATION, COPYRIGHT, and OTHER segments.
3. Synthesise NARRATION and DIALOGUE segments via the injected TTSProvider.
4. Write per-segment MP3 files to a temporary sub-directory.
5. Interleave silence clips between consecutive segments — shorter for
   same-speaker boundaries, longer for speaker changes.
6. Concatenate the per-segment files (with silence clips) into
   ``chapter_01.mp3`` using ffmpeg.
7. Save the full :class:`~src.domain.models.Book` as ``book.json`` in the
   output directory (a byproduct — useful for inspection and replay).
8. Return the :class:`~pathlib.Path` to the final stitched MP3.

Concatenation uses ffmpeg's ``concat`` demuxer (a list file approach) which
is the most reliable method for concatenating MP3 files without re-encoding.
Silence clips are generated via ffmpeg's ``anullsrc`` lavfi source once per
unique duration and reused across the chapter.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import structlog

from src.domain.models import Book, Chapter, Segment, SegmentType
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
        silence_same_speaker_ms: Duration (ms) of silence inserted between
                                 consecutive segments by the same speaker.
        silence_speaker_change_ms: Duration (ms) of silence inserted at
                                   speaker-change boundaries.
    """

    def __init__(
        self,
        provider: TTSProvider,
        output_dir: Path,
        silence_same_speaker_ms: int = 150,
        silence_speaker_change_ms: int = 400,
    ) -> None:
        self._provider = provider
        self._output_dir = output_dir
        self._silence_same_speaker_ms = silence_same_speaker_ms
        self._silence_speaker_change_ms = silence_speaker_change_ms

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
            segment_paths, synthesised_segments = self._synthesise_segments(
                chapter, voice_assignment, tmp_path
            )

            # Stitch segments into final chapter MP3
            chapter_filename = f"chapter_{chapter_number:02d}.mp3"
            output_mp3 = self._output_dir / chapter_filename
            self._stitch_with_ffmpeg(
                segment_paths, output_mp3, synthesised_segments
            )

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
        chapter: Chapter,
        voice_assignment: dict[str, str],
        tmp_dir: Path,
    ) -> tuple[list[Path], list[Segment]]:
        """Synthesise all speakable segments; return paths and corresponding segments.

        Returns:
            A tuple of (segment_paths, synthesised_segments) where each list
            is in the same order and length.  Only segments with a synthesisable
            type are included.
        """
        segment_paths: list[Path] = []
        synthesised_segments: list[Segment] = []
        seg_index = 0

        for section in chapter.sections:
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

                # Pass emotion as a string or None
                emotion_value = segment.emotion
                self._provider.synthesize(
                    segment.text, voice_id, seg_path, emotion=emotion_value
                )
                segment_paths.append(seg_path)
                synthesised_segments.append(segment)
                seg_index += 1

        return segment_paths, synthesised_segments

    def _build_concat_entries(
        self,
        segment_paths: list[Path],
        segments: list[Segment],
        work_dir: Path,
    ) -> list[Path]:
        """Build an ordered list of file paths for the ffmpeg concat list.

        Interleaves silence clips between consecutive segment paths.  The
        silence duration depends on whether adjacent segments share the same
        ``character_id`` (same-speaker gap) or differ (speaker-change gap).

        Silence clips are generated once per unique duration and reused.

        Args:
            segment_paths: Ordered MP3 file paths (one per synthesised segment).
            segments: Corresponding :class:`Segment` objects in the same order.
            work_dir: Directory where silence clips are written.

        Returns:
            Ordered list of paths — segment files with silence clips inserted
            between each consecutive pair.
        """
        if len(segment_paths) <= 1:
            return list(segment_paths)

        # Cache: duration_ms -> generated silence file path
        silence_cache: dict[int, Path] = {}

        entries: list[Path] = [segment_paths[0]]
        for i in range(1, len(segment_paths)):
            prev_char = segments[i - 1].character_id or "narrator"
            curr_char = segments[i].character_id or "narrator"

            if prev_char == curr_char:
                duration_ms = self._silence_same_speaker_ms
            else:
                duration_ms = self._silence_speaker_change_ms

            silence_path = silence_cache.get(duration_ms)
            if silence_path is None:
                silence_path = self._generate_silence_clip(duration_ms, work_dir)
                silence_cache[duration_ms] = silence_path

            entries.append(silence_path)
            entries.append(segment_paths[i])

        return entries

    def _generate_silence_clip(self, duration_ms: int, work_dir: Path) -> Path:
        """Generate a silent MP3 clip of *duration_ms* milliseconds.

        Uses ffmpeg's ``anullsrc`` lavfi source to create a silent audio
        stream.  The file is written to *work_dir* and named
        ``silence_<duration_ms>ms.mp3``.

        Args:
            duration_ms: Duration of silence in milliseconds.
            work_dir: Directory where the file is created.

        Returns:
            Path to the generated silence clip.

        Raises:
            RuntimeError: If ffmpeg exits with a non-zero return code.
        """
        silence_path = work_dir / f"silence_{duration_ms}ms.mp3"
        if silence_path.exists():
            return silence_path

        duration_seconds = duration_ms / 1000.0
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(duration_seconds),
            "-q:a", "9",
            "-acodec", "libmp3lame",
            str(silence_path),
        ]

        logger.debug(
            "tts_generate_silence",
            duration_ms=duration_ms,
            path=str(silence_path),
        )

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg silence generation failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        return silence_path

    def _stitch_with_ffmpeg(
        self,
        segment_paths: list[Path],
        output_path: Path,
        segments: list[Segment] | None = None,
    ) -> None:
        """Concatenate *segment_paths* into *output_path* using ffmpeg.

        Uses the ``concat`` demuxer (list-file approach) which does not
        re-encode the audio — segments are joined as-is.  When *segments*
        is provided, silence clips are interleaved between consecutive
        segment files based on speaker boundary type.

        Args:
            segment_paths: Ordered list of MP3 segment files.
            output_path: Destination MP3 file path.
            segments: Optional list of :class:`Segment` objects corresponding
                      to *segment_paths*.  When provided, silence clips are
                      inserted between consecutive segments.

        Raises:
            RuntimeError: If ffmpeg exits with a non-zero return code or if
                          there are no segments to stitch.
        """
        if not segment_paths:
            logger.warning("tts_stitch_no_segments", output=str(output_path))
            # Create an empty file so the return value is still valid
            output_path.touch()
            return

        # Build the concat list — with silence gaps if segments are provided
        concat_dir = segment_paths[0].parent
        if segments is not None:
            concat_entries = self._build_concat_entries(
                segment_paths, segments, concat_dir
            )
        else:
            concat_entries = list(segment_paths)

        concat_list_path = concat_dir / "concat_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for entry_path in concat_entries:
                # ffmpeg concat list syntax: one line per file
                f.write(f"file '{entry_path.as_posix()}'\n")

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
