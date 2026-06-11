"""Audio orchestrator: synthesise and stitch all speakable beats in a chapter."""
import re
import subprocess
from pathlib import Path
from typing import Optional

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.tts.beat_context_resolver import BeatContextResolver
from src.audio.tts.tts_provider import TTSProvider
from src.config.feature_flags import FeatureFlags
from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_ID
from src.domain.models import Book, Chapter

logger = structlog.get_logger(__name__)

_SYNTHESISE_TYPES = {
    BeatType.NARRATION,
    BeatType.DIALOGUE,
    BeatType.SOUND_EFFECT,
    BeatType.VOCAL_EFFECT,
    BeatType.CHAPTER_ANNOUNCEMENT,
    BeatType.BOOK_TITLE,
}

_UNSAFE_CHARS = re.compile(r'[:/\\<>"|?*]')


def _sanitize_dirname(name: str) -> str:
    """Replace filesystem-unsafe characters in *name* with ``-``."""
    return _UNSAFE_CHARS.sub("-", name)


class AudioOrchestrator:
    """Orchestrates audio synthesis for a single chapter of a Book."""

    SILENCE_SAME_SPEAKER_MS = 150
    SILENCE_SPEAKER_CHANGE_MS = 400
    SILENCE_AFTER_INTRODUCTION_MS = 1500
    SILENCE_AFTER_ANNOUNCEMENT_MS = 500

    def __init__(
        self,
        provider: TTSProvider,
        output_dir: Path,
        silence_same_speaker_ms: int = 150,
        silence_speaker_change_ms: int = 400,
        debug: bool = False,
        ffmpeg_concat_demuxer_path: Optional[Path] = None,
        sound_effect_provider: Optional[SoundEffectProvider] = None,
        feature_flags: Optional[FeatureFlags] = None,
    ) -> None:
        self._provider = provider
        self._output_dir = output_dir
        self._ffmpeg_concat_demuxer_path = ffmpeg_concat_demuxer_path
        self._feature_flags = feature_flags or FeatureFlags()
        self._silence_same_speaker_ms = silence_same_speaker_ms
        self._silence_speaker_change_ms = silence_speaker_change_ms
        self._debug = debug
        self._sound_effect_provider = sound_effect_provider

        from src.audio.audio_assembler import AudioAssembler
        from src.audio.tts.beat_synthesizer import BeatSynthesizer

        self._synthesizer = BeatSynthesizer(provider)
        self._assembler = AudioAssembler(
            output_dir,
            feature_flags=self._feature_flags,
            silence_same_speaker_ms=silence_same_speaker_ms,
            silence_speaker_change_ms=silence_speaker_change_ms,
        )

    def synthesize_chapter(
        self,
        book: Book,
        chapter_number: int,
        voice_assignment: dict[int, str],
    ) -> Path:
        """Synthesise all speakable beats in *chapter_number* and stitch them."""
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

        if self._debug:
            beat_paths, synthesised_beats = self._synthesise_beats(
                chapter, voice_assignment, chapter_dir,
            )
            self._stitch_with_ffmpeg(beat_paths, output_mp3, synthesised_beats)
            for artifact in chapter_dir.glob("silence_*ms.mp3"):
                artifact.unlink(missing_ok=True)
            concat_list = chapter_dir / "concat_list.txt"
            concat_list.unlink(missing_ok=True)
        else:
            beats_dir = chapter_dir / "beats" / self._provider.name
            beats_dir.mkdir(parents=True, exist_ok=True)
            beat_paths, synthesised_beats = self._synthesise_beats(
                chapter, voice_assignment, beats_dir,
            )
            self._stitch_with_ffmpeg(beat_paths, output_mp3, synthesised_beats)

        logger.info(
            "tts_chapter_done",
            chapter_number=chapter_number,
            output=str(output_mp3),
        )
        return output_mp3

    def _synthesise_beats(
        self,
        chapter: Chapter,
        voice_assignment: dict[int, str],
        tmp_dir: Path,
    ) -> tuple[list[Path], list[Beat]]:
        """Synthesise all speakable beats; return paths and corresponding beats."""
        speakable: list[Beat] = []
        for beat in chapter.beats:
            if beat.beat_type not in _SYNTHESISE_TYPES:
                logger.debug(
                    "tts_beat_skipped",
                    beat_type=beat.beat_type.value,
                    text_preview=beat.text[:40],
                )
                continue
            speakable.append(beat)

        resolver = BeatContextResolver(speakable)

        beat_paths: list[Path] = []
        for beat_index, beat in enumerate(speakable):
            beat_path = tmp_dir / f"beat_{beat_index:04d}.mp3"

            if beat_path.exists() and beat_path.stat().st_size > 0:
                logger.debug(
                    "tts_beat_cached",
                    beat_index=beat_index,
                    path=str(beat_path),
                )
                beat_paths.append(beat_path)
                continue

            if beat.beat_type in {BeatType.VOCAL_EFFECT, BeatType.SOUND_EFFECT}:
                if self._sound_effect_provider is None:
                    logger.debug(
                        "tts_sound_effect_skipped",
                        beat_index=beat_index,
                        text=beat.text,
                        reason="no provider",
                    )
                    continue

                sound_effect_description = beat.text
                logger.debug(
                    "tts_sound_effect_synthesise",
                    beat_index=beat_index,
                    description=sound_effect_description,
                )

                sound_effect_result = self._sound_effect_provider._generate(  # type: ignore[attr-defined]
                    sound_effect_description,
                    beat_path,
                    duration_seconds=2.0,
                )

                if sound_effect_result is None:
                    logger.warning(
                        "tts_sound_effect_generation_failed",
                        beat_index=beat_index,
                        description=sound_effect_description,
                    )
                    continue

                beat_paths.append(beat_path)
                continue

            character_id = beat.character_id or NARRATOR_ID
            voice_id = voice_assignment.get(
                character_id,
                voice_assignment.get(NARRATOR_ID, ""),
            )

            logger.debug(
                "tts_beat_synthesise",
                beat_index=beat_index,
                beat_type=beat.beat_type.value,
                character_id=character_id,
                voice_id=voice_id,
            )

            ctx = resolver.resolve(beat_index, voice_id=voice_id)

            request_id = self._provider.synthesize(beat, voice_id, beat_path, ctx)

            resolver.record_request_id(voice_id, request_id)
            beat_paths.append(beat_path)

        return beat_paths, speakable

    def _build_concat_entries(
        self,
        beat_paths: list[Path],
        beats: list[Beat],
        work_dir: Path,
    ) -> list[Path]:
        """Build an ordered list with silence clips interleaved between beats."""
        if len(beat_paths) <= 1:
            return list(beat_paths)

        silence_cache: dict[int, Path] = {}

        entries: list[Path] = [beat_paths[0]]
        for i in range(1, len(beat_paths)):
            prev_beat = beats[i - 1]
            prev_char = prev_beat.character_id or NARRATOR_ID
            curr_char = beats[i].character_id or NARRATOR_ID

            if prev_beat.beat_type == BeatType.BOOK_TITLE:
                duration_ms = self.SILENCE_AFTER_INTRODUCTION_MS
            elif prev_beat.beat_type == BeatType.CHAPTER_ANNOUNCEMENT:
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
            entries.append(beat_paths[i])

        return entries

    def _generate_silence_clip(self, duration_ms: int, work_dir: Path) -> Path:
        """Generate a silent MP3 clip of *duration_ms* milliseconds."""
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
        beat_paths: list[Path],
        output_path: Path,
        beats: list[Beat] | None = None,
    ) -> None:
        """Concatenate *beat_paths* into *output_path* using ffmpeg."""
        if not beat_paths:
            logger.warning("tts_stitch_no_beats", output=str(output_path))
            output_path.touch()
            return

        concat_dir = beat_paths[0].parent
        if beats is not None:
            concat_entries = self._build_concat_entries(
                beat_paths, beats, concat_dir,
            )
        else:
            concat_entries = list(beat_paths)

        concat_list_path = concat_dir / "concat_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for entry_path in concat_entries:
                f.write(f"file '{entry_path.resolve().as_posix()}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            str(output_path),
        ]

        logger.info(
            "tts_ffmpeg_stitch",
            beat_count=len(beat_paths),
            output=str(output_path),
        )

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
