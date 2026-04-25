"""Audio orchestrator for a single book chapter.

Responsibilities
----------------
1. Iterate all segments in the requested chapter.
2. Skip ILLUSTRATION, COPYRIGHT, and OTHER segments.
3. Synthesise NARRATION, DIALOGUE, BOOK_TITLE, and CHAPTER_ANNOUNCEMENT
   segments via the injected TTSProvider.
5. Write per-segment MP3 files into a per-chapter named folder:
   ``output_dir/{chapter_title}/chapter.mp3``.
6. Interleave silence clips between consecutive segments — shorter for
   same-speaker boundaries, longer for speaker changes.
7. Concatenate the per-segment files (with silence clips) into
   ``chapter.mp3`` using ffmpeg.
8. Return the :class:`~pathlib.Path` to the final stitched MP3.

In **normal mode** (``debug=False``), individual segment MP3 files are
synthesised into a temporary directory that is deleted after stitching.
In **debug mode** (``debug=True``), segments are synthesised directly into
the chapter folder and kept alongside ``chapter.mp3`` for inspection.

Concatenation uses ffmpeg's ``concat`` demuxer (a list file approach) which
is the most reliable method for concatenating MP3 files without re-encoding.
Silence clips are generated via ffmpeg's ``anullsrc`` lavfi source once per
unique duration and reused across the chapter.
"""
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import structlog

from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.tts.beat_context_resolver import BeatContextResolver
from src.audio.tts.tts_provider import TTSProvider
from src.config.feature_flags import FeatureFlags
from src.domain.models import Beat, BeatType, Book, Chapter, SceneRegistry

logger = structlog.get_logger(__name__)

# Segment types that should be synthesised to audio.
_SYNTHESISE_TYPES = {
    BeatType.NARRATION,
    BeatType.DIALOGUE,
    BeatType.SOUND_EFFECT,
    BeatType.VOCAL_EFFECT,
    BeatType.CHAPTER_ANNOUNCEMENT,
    BeatType.BOOK_TITLE,
}

# Same character set as generate_book_id in src/repository/book_id.py.
_UNSAFE_CHARS = re.compile(r'[:/\\<>"|?*]')


def _sanitize_dirname(name: str) -> str:
    """Replace filesystem-unsafe characters in *name* with ``-``."""
    return _UNSAFE_CHARS.sub("-", name)


def _get_audio_duration(path: Path) -> float:
    """Return the duration in seconds of the audio file at *path* via ffprobe.

    Falls back to ``0.0`` if ffprobe is unavailable or the file cannot be read.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        logger.warning("ffprobe_duration_failed", path=str(path), exc_info=True)
    return 0.0


def _compute_scene_time_ranges(
    beats: list[Beat],
    durations: list[float],
) -> dict[str, tuple[float, float]]:
    """Map scene IDs to ``(start_seconds, end_seconds)`` from segment durations.

    Segments without a ``scene_id`` are skipped.  If a scene appears in
    multiple consecutive runs, the range spans from the first segment's
    start to the last segment's end.

    Args:
        beats: Ordered synthesised segments (same order as *durations*).
        durations: Duration in seconds for each segment, same length as *segments*.

    Returns:
        Dict mapping each ``scene_id`` to its ``(start, end)`` time range.
    """
    ranges: dict[str, tuple[float, float]] = {}
    offset = 0.0
    for seg, dur in zip(beats, durations):
        if seg.scene_id is not None:
            existing = ranges.get(seg.scene_id)
            if existing is None:
                ranges[seg.scene_id] = (offset, offset + dur)
            else:
                ranges[seg.scene_id] = (existing[0], offset + dur)
        offset += dur
    return ranges


def build_ambient_filter_complex(
    ambient_entries: list[tuple[Path, float, float, float]],
    cross_fade_seconds: float = 5.0,
) -> Optional[str]:
    """Build an ffmpeg filter_complex string for ambient mixing.

    Each entry is ``(ambient_path, volume_db, start_seconds, end_seconds)``.
    The filter loops each ambient clip to cover its scene duration, applies
    the volume adjustment, and mixes all ambient tracks together using
    ``acrossfade`` at scene boundaries.  The resulting ambient mix is then
    mixed with the speech input (input 0) via ``amix``.

    Args:
        ambient_entries: Per-scene ambient info. Each tuple contains the
            ambient file path, volume in dB, scene start time, and scene
            end time in seconds.
        cross_fade_seconds: Duration of cross-fade at scene boundaries.

    Returns:
        The filter_complex string, or ``None`` if *ambient_entries* is empty.
    """
    if not ambient_entries:
        return None

    filters: list[str] = []
    # For each ambient entry (input indices 1..N, since input 0 is speech),
    # loop, trim, and apply volume.
    for i, (_path, volume_db, start, end) in enumerate(ambient_entries):
        inp_idx = i + 1  # input 0 is speech
        duration = end - start
        filters.append(
            f"[{inp_idx}:a]aloop=loop=-1:size=2e+09,atrim=duration={duration},"
            f"volume={volume_db}dB,adelay={int(start * 1000)}|{int(start * 1000)}"
            f"[amb{i}]"
        )

    if len(ambient_entries) == 1:
        # Single ambient — mix directly with speech
        filters.append("[0:a][amb0]amix=inputs=2:duration=first[out]")
    else:
        # Multiple ambient tracks — cross-fade adjacent pairs, then mix with speech
        # Chain acrossfade between adjacent ambient tracks
        prev_label = "amb0"
        for i in range(1, len(ambient_entries)):
            out_label = f"xfade{i}" if i < len(ambient_entries) - 1 else "ambmix"
            filters.append(
                f"[{prev_label}][amb{i}]acrossfade=d={cross_fade_seconds}:"
                f"c1=tri:c2=tri[{out_label}]"
            )
            prev_label = out_label

        filters.append("[0:a][ambmix]amix=inputs=2:duration=first[out]")

    return ";".join(filters)


class AudioOrchestrator:
    """Orchestrates audio synthesis for a single chapter of a :class:`Book`.

    Usage::

        orchestrator = AudioOrchestrator(provider, output_dir=Path("output"))
        path = orchestrator.synthesize_chapter(book, chapter_number=1, voice_assignment)

    Args:
        provider: A :class:`~src.audio.tts.tts_provider.TTSProvider` implementation.
        output_dir: Directory where per-chapter subfolders are created.
                    Each chapter produces ``output_dir/{title}/chapter.mp3``.
        silence_same_speaker_ms: Duration (ms) of silence inserted between
                                 consecutive segments by the same speaker.
        silence_speaker_change_ms: Duration (ms) of silence inserted at
                                   speaker-change boundaries.
        debug: When ``True``, keep individual ``seg_NNNN.mp3`` files in the
               chapter folder alongside ``chapter.mp3``.  Default ``False``.
        feature_flags: A :class:`~src.config.feature_flags.FeatureFlags` instance
                       controlling all feature toggles (ambient, sound effects, emotion,
                       voice design, scene context).  Defaults to all-enabled.
    """

    # Audio config (class constants)
    SILENCE_SAME_SPEAKER_MS = 150
    SILENCE_SPEAKER_CHANGE_MS = 400
    SILENCE_AFTER_INTRODUCTION_MS = 1500
    SILENCE_AFTER_ANNOUNCEMENT_MS = 500
    DEBUG = False

    def __init__(
        self,
        provider: TTSProvider,
        output_dir: Path,
        silence_same_speaker_ms: int = 150,
        silence_speaker_change_ms: int = 400,
        debug: bool = False,
        scene_registry: Optional[SceneRegistry] = None,
        ffmpeg_concat_demuxer_path: Optional[Path] = None,
        sound_effect_provider: Optional[SoundEffectProvider] = None,
        ambient_provider: Optional[AmbientProvider] = None,
        feature_flags: Optional[FeatureFlags] = None,
    ) -> None:
        self._provider = provider
        self._output_dir = output_dir
        self._scene_registry = scene_registry
        self._ffmpeg_concat_demuxer_path = ffmpeg_concat_demuxer_path

        self._feature_flags = feature_flags or FeatureFlags()

        self._silence_same_speaker_ms = silence_same_speaker_ms
        self._silence_speaker_change_ms = silence_speaker_change_ms
        self._debug = debug

        self._sound_effect_provider = sound_effect_provider
        self._ambient_provider = ambient_provider

        # Create synthesizer and assembler
        from src.audio.audio_assembler import AudioAssembler
        from src.audio.tts.beat_synthesizer import BeatSynthesizer

        self._synthesizer = BeatSynthesizer(provider)
        self._assembler = AudioAssembler(
            output_dir,
            ambient_enabled=self._feature_flags.ambient_enabled,
            sound_effects_enabled=self._feature_flags.sound_effects_enabled,
            silence_same_speaker_ms=silence_same_speaker_ms,
            silence_speaker_change_ms=silence_speaker_change_ms,
        )

    def synthesize_chapter(
        self,
        book: Book,
        chapter_number: int,
        voice_assignment: dict[str, str],
    ) -> Path:
        """Synthesise all speakable segments in *chapter_number* and stitch them.

        Output is written to ``output_dir/{chapter_title}/chapter.mp3``.
        In debug mode, individual ``seg_NNNN.mp3`` files are kept alongside
        ``chapter.mp3``.

        Args:
            book: The :class:`~src.domain.models.Book` to synthesise.
            chapter_number: 1-based chapter index (must exist in the book).
            voice_assignment: Mapping from ``character_id`` to ElevenLabs
                              ``voice_id``, as returned by
                              :class:`~src.audio.tts.voice_assigner.VoiceAssigner`.

        Returns:
            Path to the stitched ``chapter.mp3`` inside the chapter subfolder.

        Raises:
            ValueError: If *chapter_number* is not found in the book.
            RuntimeError: If ffmpeg fails during stitching.
        """
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

        chapter_dir = self._output_dir / _sanitize_dirname(chapter.title)
        chapter_dir.mkdir(parents=True, exist_ok=True)
        output_mp3 = chapter_dir / "chapter.mp3"

        logger.info(
            "tts_chapter_start",
            chapter_number=chapter_number,
            chapter_title=chapter.title,
        )

        # Use the book's scene_registry for per-segment scene lookup.
        scene_reg: Optional[SceneRegistry] = None
        if book.scene_registry.all():
            scene_reg = book.scene_registry

        if self._debug:
            # Debug mode — synthesise directly into the chapter folder
            segment_paths, synthesised_segments = self._synthesise_segments(
                chapter, voice_assignment, chapter_dir, scene_registry=scene_reg
            )
            self._stitch_with_ffmpeg(
                segment_paths, output_mp3, synthesised_segments
            )
            # Clean up non-segment artifacts (silence clips, concat list)
            for artifact in chapter_dir.glob("silence_*ms.mp3"):
                artifact.unlink(missing_ok=True)
            concat_list = chapter_dir / "concat_list.txt"
            concat_list.unlink(missing_ok=True)
        else:
            # Normal mode — synthesise into temp dir, stitch into chapter folder
            with tempfile.TemporaryDirectory(prefix="tts_segments_") as tmp_dir:
                tmp_path = Path(tmp_dir)
                segment_paths, synthesised_segments = self._synthesise_segments(
                    chapter, voice_assignment, tmp_path, scene_registry=scene_reg
                )
                self._stitch_with_ffmpeg(
                    segment_paths, output_mp3, synthesised_segments
                )

        # Ambient audio mixing (post-stitch)
        if (
            self._feature_flags.ambient_enabled
            and self._ambient_provider is not None
            and scene_reg is not None
            and segment_paths
        ):
            self._apply_ambient(
                output_mp3, segment_paths, synthesised_segments, scene_reg
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

    def _synthesise_segments(
        self,
        chapter: Chapter,
        voice_assignment: dict[str, str],
        tmp_dir: Path,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> tuple[list[Path], list[Beat]]:
        """Synthesise all speakable segments; return paths and corresponding segments.

        Returns:
            A tuple of (segment_paths, synthesised_segments) where each list
            is in the same order and length.  Only segments with a synthesisable
            type are included.
        """
        # Collect all synthesisable segments.
        speakable: list[Beat] = []
        for section in chapter.sections:
            if section.beats is None:
                continue
            for beat in section.beats:
                if beat.beat_type not in _SYNTHESISE_TYPES:
                    logger.debug(
                        "tts_segment_skipped",
                        segment_type=beat.beat_type.value,
                        text_preview=beat.text[:40],
                    )
                    continue
                speakable.append(beat)

        # Delegate context resolution (text context, request-ID chaining,
        # scene modifiers) to BeatContextResolver.
        resolver = BeatContextResolver(
            speakable,
            scene_registry=scene_registry,
        )

        segment_paths: list[Path] = []
        for seg_index, beat in enumerate(speakable):
            seg_path = tmp_dir / f"seg_{seg_index:04d}.mp3"

            # Handle VOCAL_EFFECT and SOUND_EFFECT via SoundEffectProvider
            if beat.beat_type in {BeatType.VOCAL_EFFECT, BeatType.SOUND_EFFECT}:
                # Skip if no provider configured
                if self._sound_effect_provider is None:
                    logger.debug(
                        "tts_sound_effect_skipped",
                        segment_index=seg_index,
                        text=beat.text,
                        reason="no provider",
                    )
                    continue

                # Use sound_effect_detail if available, otherwise fall back to text
                sound_effect_description = beat.sound_effect_detail or beat.text
                logger.debug(
                    "tts_sound_effect_synthesise",
                    segment_index=seg_index,
                    description=sound_effect_description,
                )

                # Generate sound effect audio
                sound_effect_result = self._sound_effect_provider._generate(
                    sound_effect_description,
                    seg_path,
                    duration_seconds=2.0,
                )

                if sound_effect_result is None:
                    logger.warning(
                        "tts_sound_effect_generation_failed",
                        segment_index=seg_index,
                        description=sound_effect_description,
                    )
                    continue

                segment_paths.append(seg_path)
                continue

            # Standard TTS synthesis for DIALOGUE and NARRATION
            # Resolve voice_id — fall back to narrator voice if unknown
            character_id = beat.character_id or "narrator"
            voice_id = voice_assignment.get(
                character_id,
                voice_assignment.get("narrator", ""),
            )

            logger.debug(
                "tts_segment_synthesise",
                segment_index=seg_index,
                segment_type=beat.beat_type.value,
                character_id=character_id,
                voice_id=voice_id,
            )

            ctx = resolver.resolve(
                seg_index,
                voice_id=voice_id,
                apply_scene_modifiers=True,
            )

            request_id = self._provider.synthesize(
                beat.text,
                voice_id,
                seg_path,
                emotion=beat.emotion,
                previous_text=ctx.previous_text,
                next_text=ctx.next_text,
                voice_stability=ctx.voice_stability,
                voice_style=ctx.voice_style,
                voice_speed=ctx.voice_speed,
                previous_request_ids=ctx.previous_request_ids,
            )

            resolver.record_request_id(voice_id, request_id)
            segment_paths.append(seg_path)

        return segment_paths, speakable

    def _apply_ambient(
        self,
        speech_path: Path,
        segment_paths: list[Path],
        beats: list[Beat],
        scene_registry: SceneRegistry,
    ) -> None:
        """Generate ambient audio and mix it under the speech file.

        Computes per-segment durations, maps them to scene time ranges,
        generates ambient audio for each scene with ``ambient_prompt``,
        and mixes the result into *speech_path* in-place.

        Silently skips any scene where ambient generation fails or when
        no ambient provider is configured.
        """
        # Skip if no ambient provider configured
        if self._ambient_provider is None:
            return

        # Compute segment durations
        durations = [_get_audio_duration(p) for p in segment_paths]

        # Map scene_ids to time ranges
        time_ranges = _compute_scene_time_ranges(beats, durations)

        # Build ambient entries
        ambient_entries: list[tuple[Path, float, float, float]] = []
        for scene_id, (start, end) in time_ranges.items():
            scene = scene_registry.get(scene_id)
            if scene is None or scene.ambient_prompt is None:
                continue

            # Use provider instead of function
            ambient_dir = self._output_dir / "ambient"
            output_path = ambient_dir / f"{scene.scene_id}.mp3"
            ambient_path = self._ambient_provider._generate(
                scene.ambient_prompt,
                output_path,
                duration_seconds=max(end - start, 10.0),
            )
            if ambient_path is None:
                continue

            volume_db = scene.ambient_volume if scene.ambient_volume is not None else -18.0
            ambient_entries.append((ambient_path, volume_db, start, end))

        if not ambient_entries:
            return

        logger.info(
            "tts_ambient_mix",
            scene_count=len(ambient_entries),
            speech_path=str(speech_path),
        )

        self._mix_ambient_into_speech(speech_path, ambient_entries)

    def _mix_ambient_into_speech(
        self,
        speech_path: Path,
        ambient_entries: list[tuple[Path, float, float, float]],
    ) -> None:
        """Run ffmpeg filter_complex to mix ambient tracks under *speech_path*.

        The speech file is replaced in-place (written to a temp file first,
        then moved over the original).

        Args:
            speech_path: Path to the stitched speech MP3.
            ambient_entries: Per-scene ambient info — each tuple contains
                ``(ambient_path, volume_db, start_seconds, end_seconds)``.
        """
        filter_str = build_ambient_filter_complex(ambient_entries)
        if filter_str is None:
            return

        # Build ffmpeg command: input 0 = speech, inputs 1..N = ambient files
        tmp_output = speech_path.with_suffix(".mixed.mp3")
        cmd: list[str] = ["ffmpeg", "-y", "-i", str(speech_path)]
        for ambient_path, _vol, _start, _end in ambient_entries:
            cmd.extend(["-i", str(ambient_path)])
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[out]",
            str(tmp_output),
        ])

        logger.debug("tts_ambient_ffmpeg", cmd=" ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(
                "tts_ambient_mix_failed",
                returncode=result.returncode,
                stderr=result.stderr[:500],
            )
            # Clean up temp file on failure — speech file remains unmixed
            tmp_output.unlink(missing_ok=True)
            return

        # Replace original with mixed version
        tmp_output.replace(speech_path)

    def _build_concat_entries(
        self,
        segment_paths: list[Path],
        beats: list[Beat],
        work_dir: Path,
    ) -> list[Path]:
        """Build an ordered list of file paths for the ffmpeg concat list.

        Interleaves silence clips between consecutive segment paths.  The
        silence duration depends on whether adjacent segments share the same
        ``character_id`` (same-speaker gap) or differ (speaker-change gap).

        Silence clips are generated once per unique duration and reused.

        Args:
            segment_paths: Ordered MP3 file paths (one per synthesised segment).
            beats: Corresponding :class:`Segment` objects in the same order.
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
            prev_seg = beats[i - 1]
            prev_char = prev_seg.character_id or "narrator"
            curr_char = beats[i].character_id or "narrator"

            if prev_seg.beat_type == BeatType.BOOK_TITLE:
                duration_ms = self.SILENCE_AFTER_INTRODUCTION_MS
            elif prev_seg.beat_type == BeatType.CHAPTER_ANNOUNCEMENT:
                duration_ms = self.SILENCE_AFTER_ANNOUNCEMENT_MS
            elif prev_char == curr_char:
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
        beats: list[Beat] | None = None,
    ) -> None:
        """Concatenate *segment_paths* into *output_path* using ffmpeg.

        Uses the ``concat`` demuxer (list-file approach) which does not
        re-encode the audio — segments are joined as-is.  When *segments*
        is provided, silence clips are interleaved between consecutive
        segment files based on speaker boundary type.

        Args:
            segment_paths: Ordered list of MP3 segment files.
            output_path: Destination MP3 file path.
            beats: Optional list of :class:`Segment` objects corresponding
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
        if beats is not None:
            concat_entries = self._build_concat_entries(
                segment_paths, beats, concat_dir
            )
        else:
            concat_entries = list(segment_paths)

        concat_list_path = concat_dir / "concat_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for entry_path in concat_entries:
                # ffmpeg concat list syntax: one line per file (absolute paths
                # avoid resolution issues with concat demuxer).
                f.write(f"file '{entry_path.resolve().as_posix()}'\n")

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
            beat_count=len(segment_paths),
            output=str(output_path),
        )

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
