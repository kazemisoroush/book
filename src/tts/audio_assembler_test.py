"""Tests for AudioAssembler — audio post-processing: silence, stitching, ambient, SFX.

These tests verify:
  - AudioAssembler reads audio config from TTSOrchestrator constants
  - AudioAssembler reads feature flags from TTSOrchestrator constants
  - assemble_chapter() orchestrates silence + stitching + ambient + SFX
  - Ambient and SFX are only applied when enabled AND clients provided
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.domain.models import Segment, SegmentType
from src.tts.audio_assembler import AudioAssembler


class TestAudioAssemblerConstruction:
    """Verify constructor stores output_dir and optional clients."""

    def test_constructor_stores_output_dir(self, tmp_path: Path) -> None:
        """Constructor accepts output_dir and stores it."""
        # Arrange & Act
        assembler = AudioAssembler(tmp_path)

        # Assert
        assert assembler._output_dir == tmp_path

    def test_constructor_stores_optional_clients(self, tmp_path: Path) -> None:
        """Constructor accepts optional ambient_client and sfx_client."""
        # Arrange
        ambient_client = MagicMock()
        sfx_client = MagicMock()

        # Act
        assembler = AudioAssembler(
            tmp_path, ambient_client=ambient_client, sfx_client=sfx_client
        )

        # Assert
        assert assembler._ambient_client is ambient_client
        assert assembler._sfx_client is sfx_client

    def test_constructor_defaults_clients_to_none(self, tmp_path: Path) -> None:
        """Constructor defaults clients to None."""
        # Arrange & Act
        assembler = AudioAssembler(tmp_path)

        # Assert
        assert assembler._ambient_client is None
        assert assembler._sfx_client is None


class TestAudioAssemblerAssembleChapterBasic:
    """Verify assemble_chapter() orchestrates assembly steps."""

    def test_assemble_chapter_with_single_segment(self, tmp_path: Path) -> None:
        """assemble_chapter() processes a single segment."""
        # Arrange
        assembler = AudioAssembler(tmp_path)

        # Create a single synthesized segment
        segment_file = tmp_path / "seg_0000.mp3"
        segment_file.write_text("fake mp3 data")

        segment = Segment(
            text="Hello",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        # Act
        with patch.object(assembler, "_build_silence_clips") as mock_silence:
            with patch.object(assembler, "_interleave_segments_and_silence") as mock_interleave:
                with patch.object(assembler, "_stitch_with_ffmpeg") as mock_stitch:
                    mock_silence.return_value = []
                    mock_interleave.return_value = [segment_file]
                    mock_stitch.return_value = tmp_path / "chapter.mp3"

                    chapter_path = assembler.assemble_chapter(
                        [segment_file], [segment], scene_registry=None
                    )

        # Assert
        assert chapter_path == tmp_path / "chapter.mp3"
        mock_silence.assert_called_once()
        mock_interleave.assert_called_once()
        mock_stitch.assert_called_once()

    def test_assemble_chapter_with_multiple_segments(self, tmp_path: Path) -> None:
        """assemble_chapter() processes multiple segments."""
        # Arrange
        assembler = AudioAssembler(tmp_path)

        # Create multiple synthesized segments
        segment_files = [
            tmp_path / "seg_0000.mp3",
            tmp_path / "seg_0001.mp3",
            tmp_path / "seg_0002.mp3",
        ]
        for f in segment_files:
            f.write_text("fake mp3 data")

        segments = [
            Segment(
                text="Narrator 1",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            ),
            Segment(
                text="Character dialogue",
                segment_type=SegmentType.DIALOGUE,
                character_id="char-1",
            ),
            Segment(
                text="Narrator 2",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            ),
        ]

        # Act
        with patch.object(assembler, "_build_silence_clips") as mock_silence:
            with patch.object(assembler, "_interleave_segments_and_silence") as mock_interleave:
                with patch.object(assembler, "_stitch_with_ffmpeg") as mock_stitch:
                    mock_silence.return_value = [tmp_path / "silence_150ms.mp3"]
                    mock_interleave.return_value = segment_files + [tmp_path / "silence_150ms.mp3"]
                    mock_stitch.return_value = tmp_path / "chapter.mp3"

                    chapter_path = assembler.assemble_chapter(
                        segment_files, segments, scene_registry=None
                    )

        # Assert
        assert chapter_path == tmp_path / "chapter.mp3"
        # Verify silence was built with correct segments
        mock_silence.assert_called_once_with(segments)


class TestAudioAssemblerAmbientFeatureFlag:
    """Verify ambient is only applied when enabled AND client provided."""

    def test_ambient_not_applied_when_disabled(self, tmp_path: Path) -> None:
        """When AMBIENT_ENABLED=False, _apply_ambient not called."""
        # Arrange
        ambient_client = MagicMock()
        assembler = AudioAssembler(tmp_path, ambient_client=ambient_client)

        segment_file = tmp_path / "seg_0000.mp3"
        segment_file.write_text("fake mp3")

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch:
            mock_orch.AMBIENT_ENABLED = False
            mock_orch.CINEMATIC_SFX_ENABLED = False
            mock_orch.SILENCE_SAME_SPEAKER_MS = 150
            mock_orch.SILENCE_SPEAKER_CHANGE_MS = 400
            mock_orch.DEBUG = False

            with patch.object(assembler, "_build_silence_clips", return_value=[]):
                with patch.object(assembler, "_interleave_segments_and_silence", return_value=[segment_file]):
                    with patch.object(assembler, "_stitch_with_ffmpeg", return_value=tmp_path / "chapter.mp3"):
                        with patch.object(assembler, "_apply_ambient") as mock_ambient:
                            assembler.assemble_chapter([segment_file], [segment])

        # Assert
        mock_ambient.assert_not_called()

    def test_ambient_not_applied_without_client(self, tmp_path: Path) -> None:
        """When ambient_client is None, _apply_ambient not called."""
        # Arrange
        assembler = AudioAssembler(tmp_path, ambient_client=None)

        segment_file = tmp_path / "seg_0000.mp3"
        segment_file.write_text("fake mp3")

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch:
            mock_orch.AMBIENT_ENABLED = True
            mock_orch.CINEMATIC_SFX_ENABLED = False
            mock_orch.SILENCE_SAME_SPEAKER_MS = 150
            mock_orch.SILENCE_SPEAKER_CHANGE_MS = 400
            mock_orch.DEBUG = False

            with patch.object(assembler, "_build_silence_clips", return_value=[]):
                with patch.object(assembler, "_interleave_segments_and_silence", return_value=[segment_file]):
                    with patch.object(assembler, "_stitch_with_ffmpeg", return_value=tmp_path / "chapter.mp3"):
                        with patch.object(assembler, "_apply_ambient") as mock_ambient:
                            assembler.assemble_chapter([segment_file], [segment])

        # Assert
        mock_ambient.assert_not_called()

    def test_ambient_applied_when_enabled_and_client_present(self, tmp_path: Path) -> None:
        """When AMBIENT_ENABLED=True and client present, _apply_ambient is called."""
        # Arrange
        ambient_client = MagicMock()
        assembler = AudioAssembler(tmp_path, ambient_client=ambient_client)

        segment_file = tmp_path / "seg_0000.mp3"
        segment_file.write_text("fake mp3")

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        chapter_path = tmp_path / "chapter.mp3"

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch:
            mock_orch.AMBIENT_ENABLED = True
            mock_orch.CINEMATIC_SFX_ENABLED = False
            mock_orch.SILENCE_SAME_SPEAKER_MS = 150
            mock_orch.SILENCE_SPEAKER_CHANGE_MS = 400
            mock_orch.DEBUG = False

            with patch.object(assembler, "_build_silence_clips", return_value=[]):
                with patch.object(assembler, "_interleave_segments_and_silence", return_value=[segment_file]):
                    with patch.object(assembler, "_stitch_with_ffmpeg", return_value=chapter_path):
                        with patch.object(assembler, "_apply_ambient") as mock_ambient:
                            assembler.assemble_chapter([segment_file], [segment])

        # Assert
        mock_ambient.assert_called_once_with(
            chapter_path, [segment_file], [segment], None
        )


class TestAudioAssemblerSFXFeatureFlag:
    """Verify SFX is only applied when enabled AND client provided."""

    def test_sfx_not_applied_when_disabled(self, tmp_path: Path) -> None:
        """When CINEMATIC_SFX_ENABLED=False, _insert_sfx not called."""
        # Arrange
        sfx_client = MagicMock()
        assembler = AudioAssembler(tmp_path, sfx_client=sfx_client)

        segment_file = tmp_path / "seg_0000.mp3"
        segment_file.write_text("fake mp3")

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch:
            mock_orch.AMBIENT_ENABLED = False
            mock_orch.CINEMATIC_SFX_ENABLED = False
            mock_orch.SILENCE_SAME_SPEAKER_MS = 150
            mock_orch.SILENCE_SPEAKER_CHANGE_MS = 400
            mock_orch.DEBUG = False

            with patch.object(assembler, "_build_silence_clips", return_value=[]):
                with patch.object(assembler, "_interleave_segments_and_silence", return_value=[segment_file]):
                    with patch.object(assembler, "_stitch_with_ffmpeg", return_value=tmp_path / "chapter.mp3"):
                        with patch.object(assembler, "_insert_sfx") as mock_sfx:
                            assembler.assemble_chapter([segment_file], [segment])

        # Assert
        mock_sfx.assert_not_called()

    def test_sfx_not_applied_without_client(self, tmp_path: Path) -> None:
        """When sfx_client is None, _insert_sfx not called."""
        # Arrange
        assembler = AudioAssembler(tmp_path, sfx_client=None)

        segment_file = tmp_path / "seg_0000.mp3"
        segment_file.write_text("fake mp3")

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch:
            mock_orch.AMBIENT_ENABLED = False
            mock_orch.CINEMATIC_SFX_ENABLED = True
            mock_orch.SILENCE_SAME_SPEAKER_MS = 150
            mock_orch.SILENCE_SPEAKER_CHANGE_MS = 400
            mock_orch.DEBUG = False

            with patch.object(assembler, "_build_silence_clips", return_value=[]):
                with patch.object(assembler, "_interleave_segments_and_silence", return_value=[segment_file]):
                    with patch.object(assembler, "_stitch_with_ffmpeg", return_value=tmp_path / "chapter.mp3"):
                        with patch.object(assembler, "_insert_sfx") as mock_sfx:
                            assembler.assemble_chapter([segment_file], [segment])

        # Assert
        mock_sfx.assert_not_called()

    def test_sfx_applied_when_enabled_and_client_present(self, tmp_path: Path) -> None:
        """When CINEMATIC_SFX_ENABLED=True and client present, _insert_sfx is called."""
        # Arrange
        sfx_client = MagicMock()
        assembler = AudioAssembler(tmp_path, sfx_client=sfx_client)

        segment_file = tmp_path / "seg_0000.mp3"
        segment_file.write_text("fake mp3")

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        chapter_path = tmp_path / "chapter.mp3"

        # Act
        with patch("src.tts.tts_orchestrator.TTSOrchestrator") as mock_orch:
            mock_orch.AMBIENT_ENABLED = False
            mock_orch.CINEMATIC_SFX_ENABLED = True
            mock_orch.SILENCE_SAME_SPEAKER_MS = 150
            mock_orch.SILENCE_SPEAKER_CHANGE_MS = 400
            mock_orch.DEBUG = False

            with patch.object(assembler, "_build_silence_clips", return_value=[]):
                with patch.object(assembler, "_interleave_segments_and_silence", return_value=[segment_file]):
                    with patch.object(assembler, "_stitch_with_ffmpeg", return_value=chapter_path):
                        with patch.object(assembler, "_insert_sfx") as mock_sfx:
                            assembler.assemble_chapter([segment_file], [segment])

        # Assert
        mock_sfx.assert_called_once_with(chapter_path, [segment])
