"""AudioAssembler — audio post-processing: silence, stitching, ambient, sound effects.

Responsibilities
----------------
1. Build silence clips between beats (duration varies by speaker boundary).
2. Interleave beat audio with silence clips.
3. Stitch the interleaved audio into a single chapter MP3 using ffmpeg.
4. Generate and mix ambient audio (if enabled and client provided).
5. Insert sound effects into silence gaps (if enabled and client provided).

Configuration is injected via constructor parameters, not read from class constants.
"""
from pathlib import Path
from typing import Any, Optional

from src.domain.models import Beat, SceneRegistry


class AudioAssembler:
    """Owns audio post-processing: silence, stitching, ambient, sound effects."""

    def __init__(
        self,
        output_dir: Path,
        ambient_client: Optional[Any] = None,
        sound_effect_client: Optional[Any] = None,
        ambient_enabled: bool = True,
        sound_effects_enabled: bool = True,
        silence_same_speaker_ms: int = 150,
        silence_speaker_change_ms: int = 400,
    ) -> None:
        """Initialize with output directory, clients, and feature flags.

        Args:
            output_dir: Directory where chapter.mp3 and artifacts will be written.
            ambient_client: Optional client for generating ambient audio.
            sound_effect_client: Optional client for generating sound effects.
            ambient_enabled: When True, ambient audio is generated and mixed.
            sound_effects_enabled: When True, sound effects are inserted into silence gaps.
            silence_same_speaker_ms: Duration (ms) of silence between same-speaker beats.
            silence_speaker_change_ms: Duration (ms) of silence at speaker-change boundaries.
        """
        self._output_dir = output_dir
        self._ambient_client = ambient_client
        self._sound_effect_client = sound_effect_client
        self._ambient_enabled = ambient_enabled
        self._sound_effects_enabled = sound_effects_enabled
        self._silence_same_speaker_ms = silence_same_speaker_ms
        self._silence_speaker_change_ms = silence_speaker_change_ms

    def assemble_chapter(
        self,
        beat_paths: list[Path],
        beats: list[Beat],
        scene_registry: Optional[SceneRegistry] = None,
    ) -> Path:
        """Post-process audio: add silence, ambient, sound effects, stitch to chapter.

        Uses feature flags and audio config from constructor parameters.

        Args:
            beat_paths: Paths to synthesized beat MP3 files.
            beats: Corresponding Beat objects for each path.
            scene_registry: Optional SceneRegistry for ambient/sound effects per-beat lookup.

        Returns:
            Path to final chapter.mp3 file.
        """
        # Build silence clips between beats
        silence_paths = self._build_silence_clips(beats)

        # Interleave beat audio with silence
        interleaved = self._interleave_beats_and_silence(beat_paths, silence_paths)

        # Stitch to single speech file
        speech_path = self._stitch_with_ffmpeg(interleaved)

        # Apply ambient (if enabled and client provided)
        if self._ambient_enabled and self._ambient_client:
            self._apply_ambient(
                speech_path, beat_paths, beats, scene_registry
            )

        # Insert sound effects (if enabled and client provided)
        if self._sound_effects_enabled and self._sound_effect_client:
            self._insert_sound_effects(speech_path, beats)

        return speech_path

    # Private helpers (to be implemented)

    def _build_silence_clips(self, beats: list[Beat]) -> list[Path]:
        """Build silence clips between beats.

        Uses silence_same_speaker_ms and silence_speaker_change_ms from constructor.

        Args:
            beats: List of beats to compute silence durations for.

        Returns:
            List of Path objects to silence MP3 files.
        """
        # Implementation will be extracted from AudioOrchestrator._build_concat_entries
        # and _generate_silence_clip
        raise NotImplementedError("_build_silence_clips to be extracted from AudioOrchestrator")

    def _interleave_beats_and_silence(
        self, beat_paths: list[Path], silence_paths: list[Path]
    ) -> list[Path]:
        """Interleave beat audio with silence clips.

        Args:
            beat_paths: Paths to beat MP3 files.
            silence_paths: Paths to silence MP3 files.

        Returns:
            List of interleaved Path objects (beats and silence mixed).
        """
        # Implementation will be extracted from AudioOrchestrator._build_concat_entries
        raise NotImplementedError("_interleave_beats_and_silence to be extracted from AudioOrchestrator")

    def _stitch_with_ffmpeg(self, interleaved_paths: list[Path]) -> Path:
        """Stitch audio files into a single chapter MP3 using ffmpeg.

        Args:
            interleaved_paths: Paths to audio files to stitch (in order).

        Returns:
            Path to final chapter.mp3.

        Raises:
            RuntimeError: If ffmpeg fails.
        """
        # Implementation will be extracted from AudioOrchestrator._stitch_with_ffmpeg
        raise NotImplementedError("_stitch_with_ffmpeg to be extracted from AudioOrchestrator")

    def _apply_ambient(
        self,
        speech_path: Path,
        beat_paths: list[Path],
        beats: list[Beat],
        scene_registry: Optional[SceneRegistry],
    ) -> None:
        """Generate ambient audio and mix it under the speech file.

        Args:
            speech_path: Path to stitched speech MP3.
            beat_paths: Paths to original beat files (for duration lookup).
            beats: Corresponding beats (for scene_id lookup).
            scene_registry: SceneRegistry for ambient prompt lookup.
        """
        # Implementation will be extracted from AudioOrchestrator._apply_ambient
        raise NotImplementedError("_apply_ambient to be extracted from AudioOrchestrator")

    def _insert_sound_effects(self, speech_path: Path, beats: list[Beat]) -> None:
        """Insert sound effects into silence gaps.

        Args:
            speech_path: Path to stitched speech MP3.
            beats: Beats (for sound effects scene lookup).
        """
        # Implementation will be extracted from existing sound effects insertion code
        raise NotImplementedError("_insert_sound_effects to be extracted from existing sound effects code")
