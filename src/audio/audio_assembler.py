"""AudioAssembler: audio post-processing for silence, stitching, sound effects."""
from pathlib import Path
from typing import Any, Optional

from src.config.feature_flags import FeatureFlags
from src.domain.beat import Beat


class AudioAssembler:
    """Owns audio post-processing: silence, stitching, sound effects."""

    def __init__(
        self,
        output_dir: Path,
        feature_flags: FeatureFlags,
        sound_effect_client: Optional[Any] = None,
        silence_same_speaker_ms: int = 150,
        silence_speaker_change_ms: int = 400,
    ) -> None:
        self._output_dir = output_dir
        self._feature_flags = feature_flags
        self._sound_effect_client = sound_effect_client
        self._silence_same_speaker_ms = silence_same_speaker_ms
        self._silence_speaker_change_ms = silence_speaker_change_ms

    def assemble_chapter(
        self,
        beat_paths: list[Path],
        beats: list[Beat],
    ) -> Path:
        """Post-process audio: add silence, stitch to chapter, insert sound effects."""
        silence_paths = self._build_silence_clips(beats)
        interleaved = self._interleave_beats_and_silence(beat_paths, silence_paths)
        speech_path = self._stitch_with_ffmpeg(interleaved)

        if self._feature_flags.sound_effects_enabled and self._sound_effect_client:
            self._insert_sound_effects(speech_path, beats)

        return speech_path

    def _build_silence_clips(self, beats: list[Beat]) -> list[Path]:
        """Build silence clips between beats."""
        raise NotImplementedError(
            "_build_silence_clips to be extracted from AudioOrchestrator"
        )

    def _interleave_beats_and_silence(
        self, beat_paths: list[Path], silence_paths: list[Path],
    ) -> list[Path]:
        """Interleave beat audio with silence clips."""
        raise NotImplementedError(
            "_interleave_beats_and_silence to be extracted from AudioOrchestrator"
        )

    def _stitch_with_ffmpeg(self, interleaved_paths: list[Path]) -> Path:
        """Stitch audio files into a single chapter MP3 using ffmpeg."""
        raise NotImplementedError(
            "_stitch_with_ffmpeg to be extracted from AudioOrchestrator"
        )

    def _insert_sound_effects(self, speech_path: Path, beats: list[Beat]) -> None:
        """Insert sound effects into silence gaps."""
        raise NotImplementedError(
            "_insert_sound_effects to be extracted from existing sound effects code"
        )
