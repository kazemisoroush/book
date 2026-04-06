"""AudioAssembler — audio post-processing: silence, stitching, ambient, SFX.

Responsibilities
----------------
1. Build silence clips between segments (duration varies by speaker boundary).
2. Interleave segment audio with silence clips.
3. Stitch the interleaved audio into a single chapter MP3 using ffmpeg.
4. Generate and mix ambient audio (if enabled and client provided).
5. Insert SFX into silence gaps (if enabled and client provided).

This class reads configuration from TTSOrchestrator class constants, not constructor params.
"""
from pathlib import Path
from typing import Any, Optional

from src.domain.models import SceneRegistry, Segment


class AudioAssembler:
    """Owns audio post-processing: silence, stitching, ambient, SFX."""

    def __init__(
        self,
        output_dir: Path,
        ambient_client: Optional[Any] = None,
        sfx_client: Optional[Any] = None,
    ) -> None:
        """Initialize with output directory and optional clients.

        Args:
            output_dir: Directory where chapter.mp3 and artifacts will be written.
            ambient_client: Optional client for generating ambient audio.
            sfx_client: Optional client for generating SFX.
        """
        self._output_dir = output_dir
        self._ambient_client = ambient_client
        self._sfx_client = sfx_client

    def assemble_chapter(
        self,
        segment_paths: list[Path],
        segments: list[Segment],
        scene_registry: Optional[SceneRegistry] = None,
    ) -> Path:
        """Post-process audio: add silence, ambient, SFX, stitch to chapter.

        Reads feature flags and audio config from TTSOrchestrator constants.

        Args:
            segment_paths: Paths to synthesized segment MP3 files.
            segments: Corresponding Segment objects for each path.
            scene_registry: Optional SceneRegistry for ambient/SFX per-segment lookup.

        Returns:
            Path to final chapter.mp3 file.
        """
        # Import here to avoid circular dependency and to allow tests to patch
        from src.tts.tts_orchestrator import TTSOrchestrator

        # Build silence clips between segments
        silence_paths = self._build_silence_clips(segments)

        # Interleave segment audio with silence
        interleaved = self._interleave_segments_and_silence(segment_paths, silence_paths)

        # Stitch to single speech file
        speech_path = self._stitch_with_ffmpeg(interleaved)

        # Apply ambient (if enabled and client provided)
        if TTSOrchestrator.AMBIENT_ENABLED and self._ambient_client:
            self._apply_ambient(
                speech_path, segment_paths, segments, scene_registry
            )

        # Insert SFX (if enabled and client provided)
        if TTSOrchestrator.CINEMATIC_SFX_ENABLED and self._sfx_client:
            self._insert_sfx(speech_path, segments)

        return speech_path

    # Private helpers (to be implemented)

    def _build_silence_clips(self, segments: list[Segment]) -> list[Path]:
        """Build silence clips between segments.

        Reads SILENCE_SAME_SPEAKER_MS and SILENCE_SPEAKER_CHANGE_MS from
        TTSOrchestrator constants.

        Args:
            segments: List of segments to compute silence durations for.

        Returns:
            List of Path objects to silence MP3 files.
        """
        # Implementation will be extracted from TTSOrchestrator._build_concat_entries
        # and _generate_silence_clip
        raise NotImplementedError("_build_silence_clips to be extracted from TTSOrchestrator")

    def _interleave_segments_and_silence(
        self, segment_paths: list[Path], silence_paths: list[Path]
    ) -> list[Path]:
        """Interleave segment audio with silence clips.

        Args:
            segment_paths: Paths to segment MP3 files.
            silence_paths: Paths to silence MP3 files.

        Returns:
            List of interleaved Path objects (segments and silence mixed).
        """
        # Implementation will be extracted from TTSOrchestrator._build_concat_entries
        raise NotImplementedError("_interleave_segments_and_silence to be extracted from TTSOrchestrator")

    def _stitch_with_ffmpeg(self, interleaved_paths: list[Path]) -> Path:
        """Stitch audio files into a single chapter MP3 using ffmpeg.

        Args:
            interleaved_paths: Paths to audio files to stitch (in order).

        Returns:
            Path to final chapter.mp3.

        Raises:
            RuntimeError: If ffmpeg fails.
        """
        # Implementation will be extracted from TTSOrchestrator._stitch_with_ffmpeg
        raise NotImplementedError("_stitch_with_ffmpeg to be extracted from TTSOrchestrator")

    def _apply_ambient(
        self,
        speech_path: Path,
        segment_paths: list[Path],
        segments: list[Segment],
        scene_registry: Optional[SceneRegistry],
    ) -> None:
        """Generate ambient audio and mix it under the speech file.

        Args:
            speech_path: Path to stitched speech MP3.
            segment_paths: Paths to original segment files (for duration lookup).
            segments: Corresponding segments (for scene_id lookup).
            scene_registry: SceneRegistry for ambient prompt lookup.
        """
        # Implementation will be extracted from TTSOrchestrator._apply_ambient
        raise NotImplementedError("_apply_ambient to be extracted from TTSOrchestrator")

    def _insert_sfx(self, speech_path: Path, segments: list[Segment]) -> None:
        """Insert SFX into silence gaps.

        Args:
            speech_path: Path to stitched speech MP3.
            segments: Segments (for SFX scene lookup).
        """
        # Implementation will be extracted from existing SFX insertion code
        raise NotImplementedError("_insert_sfx to be extracted from existing SFX code")
