"""Tests for TTSOrchestrator — inter-segment silence insertion (US-016).

These tests verify that silence clips are inserted between consecutive
TTS segments at stitch time, with duration varying by boundary type:
  - same speaker → silence_same_speaker_ms (default 150)
  - speaker change → silence_speaker_change_ms (default 400)
"""
from pathlib import Path
from unittest.mock import MagicMock

from src.domain.models import Segment, SegmentType
from src.tts.tts_orchestrator import TTSOrchestrator


def _make_segment(character_id: str) -> Segment:
    """Create a minimal speakable segment with the given character_id."""
    return Segment(
        text="Some text.",
        segment_type=SegmentType.NARRATION,
        character_id=character_id,
    )


class TestBuildConcatEntriesSameSpeaker:
    """Same-speaker boundaries use the short silence duration."""

    def test_same_speaker_boundary_uses_short_silence(self, tmp_path: Path) -> None:
        """Two segments with the same character_id produce a silence gap
        of silence_same_speaker_ms duration."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [_make_segment("narrator"), _make_segment("narrator")]
        seg_paths = [tmp_path / "seg_0.mp3", tmp_path / "seg_1.mp3"]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — 2 segment entries + 1 silence entry = 3 total
        assert len(entries) == 3
        # The middle entry should be a silence file path containing '150'
        silence_entry = entries[1]
        assert "silence_150ms" in silence_entry.name


class TestBuildConcatEntriesSpeakerChange:
    """Speaker-change boundaries use the long silence duration."""

    def test_speaker_change_boundary_uses_long_silence(self, tmp_path: Path) -> None:
        """Two segments with different character_id produce a silence gap
        of silence_speaker_change_ms duration."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [_make_segment("narrator"), _make_segment("alice")]
        seg_paths = [tmp_path / "seg_0.mp3", tmp_path / "seg_1.mp3"]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — 2 segment entries + 1 silence entry = 3 total
        assert len(entries) == 3
        silence_entry = entries[1]
        assert "silence_400ms" in silence_entry.name


class TestBuildConcatEntriesGapCount:
    """N segments produce exactly N-1 silence gaps."""

    def test_three_segments_produce_two_gaps(self, tmp_path: Path) -> None:
        """Three segments must yield 3 segment entries + 2 silence entries = 5."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [
            _make_segment("narrator"),
            _make_segment("alice"),
            _make_segment("narrator"),
        ]
        seg_paths = [tmp_path / f"seg_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — 3 segments + 2 gaps = 5
        assert len(entries) == 5
        # Positions 1 and 3 are silence entries
        assert "silence_" in entries[1].name
        assert "silence_" in entries[3].name


class TestBuildConcatEntriesSingleSegment:
    """A single segment produces no silence clips."""

    def test_single_segment_has_no_silence(self, tmp_path: Path) -> None:
        """One segment must yield exactly 1 entry with no silence."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [_make_segment("narrator")]
        seg_paths = [tmp_path / "seg_0.mp3"]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert
        assert len(entries) == 1
        assert entries[0] == seg_paths[0]


class TestBuildConcatEntriesCustomDurations:
    """Custom silence durations are respected."""

    def test_custom_silence_durations(self, tmp_path: Path) -> None:
        """Non-default silence durations are reflected in silence file names."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            silence_same_speaker_ms=200,
            silence_speaker_change_ms=500,
        )
        segments = [
            _make_segment("narrator"),
            _make_segment("narrator"),
            _make_segment("alice"),
        ]
        seg_paths = [tmp_path / f"seg_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — first gap is same-speaker (200ms), second is change (500ms)
        assert "silence_200ms" in entries[1].name
        assert "silence_500ms" in entries[3].name


class TestSilenceClipReuse:
    """Silence clips of the same duration are generated once and reused."""

    def test_same_duration_silence_paths_are_identical(self, tmp_path: Path) -> None:
        """Multiple same-speaker gaps should reference the same silence file path."""
        # Arrange
        provider = MagicMock()
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        segments = [
            _make_segment("narrator"),
            _make_segment("narrator"),
            _make_segment("narrator"),
        ]
        seg_paths = [tmp_path / f"seg_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(seg_paths, segments, tmp_path)

        # Assert — both silence entries reference the exact same path
        assert entries[1] == entries[3]
