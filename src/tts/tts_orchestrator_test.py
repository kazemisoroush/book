"""Tests for TTSOrchestrator — silence insertion and chapter folder output.

These tests verify:
  - Silence clips are inserted between consecutive TTS segments at stitch time,
    with duration varying by boundary type (same speaker vs. speaker change).
  - Output goes to named per-chapter subfolders: ``audio/{chapter_title}/chapter.mp3``.
  - ``debug=True`` retains individual ``seg_NNNN.mp3`` files alongside ``chapter.mp3``.
  - ``debug=False`` (default) cleans up segment files after stitching.
  - ``_sanitize_dirname`` replaces filesystem-unsafe characters.
  - Ambient audio is generated and mixed when ``ambient_enabled=True`` and scenes have
    ``ambient_prompt`` values.
"""
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from src.config.feature_flags import FeatureFlags
from src.domain.models import (
    Book, BookContent, BookMetadata, Chapter, CharacterRegistry,
    Scene, SceneRegistry, Section, Segment, SegmentType,
)
from src.tts.tts_orchestrator import (
    TTSOrchestrator, _sanitize_dirname, build_ambient_filter_complex,
)


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


# ------------------------------------------------------------------
# Helpers for synthesize_chapter tests
# ------------------------------------------------------------------

def _make_book(chapter_title: str = "Chapter 1") -> Book:
    """Create a minimal Book with one chapter containing two narration segments."""
    return Book(
        metadata=BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language="en",
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(
            chapters=[
                Chapter(
                    number=1,
                    title=chapter_title,
                    sections=[
                        Section(
                            text="Hello world. Goodbye world.",
                            segments=[
                                Segment(
                                    text="Hello world.",
                                    segment_type=SegmentType.NARRATION,
                                    character_id="narrator",
                                ),
                                Segment(
                                    text="Goodbye world.",
                                    segment_type=SegmentType.NARRATION,
                                    character_id="narrator",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        character_registry=CharacterRegistry.with_default_narrator(),
    )


def _fake_synthesize(text: str, voice_id: str, path: Path, **kwargs: object) -> None:
    """Stub TTS provider that writes a tiny file instead of calling an API."""
    path.write_bytes(b"\x00" * 64)


def _fake_ffmpeg_stitch(
    self: TTSOrchestrator,
    segment_paths: list[Path],
    output_path: Path,
    segments: list[Segment] | None = None,
) -> None:
    """Replace _stitch_with_ffmpeg to avoid a real ffmpeg dependency in tests."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x00" * 128)
    # Simulate concat_list.txt and silence files that ffmpeg would leave behind
    concat_dir = segment_paths[0].parent if segment_paths else output_path.parent
    (concat_dir / "concat_list.txt").write_text("fake")
    (concat_dir / "silence_150ms.mp3").write_bytes(b"\x00" * 32)


# ------------------------------------------------------------------
# _sanitize_dirname tests
# ------------------------------------------------------------------


class TestSanitizeDirname:
    """_sanitize_dirname replaces filesystem-unsafe characters."""

    def test_safe_name_unchanged(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("Chapter 1") == "Chapter 1"

    def test_colons_replaced(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("Chapter 1: The Beginning") == "Chapter 1- The Beginning"

    def test_slashes_replaced(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname("A/B\\C") == "A-B-C"

    def test_multiple_unsafe_chars(self) -> None:
        # Arrange / Act / Assert
        assert _sanitize_dirname('He said "Hello?" <yes>') == 'He said -Hello-- -yes-'


# ------------------------------------------------------------------
# synthesize_chapter — named subfolder output
# ------------------------------------------------------------------


class TestSynthesizeChapterNamedSubfolder:
    """synthesize_chapter writes to output_dir/{chapter_title}/chapter.mp3."""

    def test_synthesize_chapter_creates_named_subfolder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Output path should be output_dir/{chapter_title}/chapter.mp3."""
        # Arrange
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)
        book = _make_book("Chapter 1")

        # Act
        result = orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert
        assert result == tmp_path / "Chapter 1" / "chapter.mp3"
        assert result.exists()


# ------------------------------------------------------------------
# synthesize_chapter — debug mode keeps segments
# ------------------------------------------------------------------


class TestSynthesizeChapterDebugKeepsSegments:
    """debug=True retains seg_NNNN.mp3 files alongside chapter.mp3."""

    def test_synthesize_chapter_debug_keeps_segments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In debug mode, segment files remain in the chapter folder."""
        # Arrange
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path, debug=True)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — segment files persist
        chapter_dir = tmp_path / "Chapter 1"
        seg_files = sorted(chapter_dir.glob("seg_*.mp3"))
        assert len(seg_files) == 2
        assert seg_files[0].name == "seg_0000.mp3"
        assert seg_files[1].name == "seg_0001.mp3"


# ------------------------------------------------------------------
# synthesize_chapter — normal mode cleans segments
# ------------------------------------------------------------------


class TestSynthesizeChapterNormalCleansSegments:
    """debug=False (default) removes seg_NNNN.mp3 after stitching."""

    def test_synthesize_chapter_normal_cleans_segments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In normal mode, no seg_*.mp3 files remain in the chapter folder."""
        # Arrange
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path, debug=False)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — no segment files in the chapter folder
        chapter_dir = tmp_path / "Chapter 1"
        seg_files = list(chapter_dir.glob("seg_*.mp3"))
        assert seg_files == []
        # But chapter.mp3 still exists
        assert (chapter_dir / "chapter.mp3").exists()


# ------------------------------------------------------------------
# US-019 Fix 1: previous_text / next_text context
# ------------------------------------------------------------------


def _make_book_with_segments(
    segments: list[Segment],
    chapter_title: str = "Ch 1",
    scene: Scene | None = None,
) -> Book:
    """Create a Book with a single chapter containing the given segments.

    When *scene* is provided, it is added to the book's ``scene_registry``
    and each segment gets its ``scene_id`` set (if not already set).
    """
    scene_registry = SceneRegistry()
    if scene is not None:
        scene_registry.upsert(scene)
        for seg in segments:
            if seg.scene_id is None:
                seg.scene_id = scene.scene_id

    return Book(
        metadata=BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language="en",
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(
            chapters=[
                Chapter(
                    number=1,
                    title=chapter_title,
                    sections=[
                        Section(
                            text="placeholder",
                            segments=segments,
                        ),
                    ],
                ),
            ],
        ),
        character_registry=CharacterRegistry.with_default_narrator(),
        scene_registry=scene_registry,
    )


class TestSynthesiseSegmentsPassesSameCharacterContext:
    """_synthesise_segments passes previous_text/next_text from same-character segments."""

    def test_same_character_gets_own_previous_and_next(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Three narrator segments: middle one gets context from the other two."""
        # Arrange
        segments = [
            Segment(text="First.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Second.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Third.", segment_type=SegmentType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert
        calls = provider.synthesize.call_args_list
        assert len(calls) == 3
        assert calls[1].kwargs.get("previous_text") == "First."
        assert calls[1].kwargs.get("next_text") == "Third."

    def test_character_context_skips_other_characters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mrs Bennet's context comes from her own lines, not narrator's."""
        # Arrange
        segments = [
            Segment(text="Narration.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="First line.", segment_type=SegmentType.DIALOGUE, character_id="mrs_bennet"),
            Segment(text="More narration.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Second line.", segment_type=SegmentType.DIALOGUE, character_id="mrs_bennet"),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1", "mrs_bennet": "v2"},
        )

        # Assert — mrs_bennet's second line (call index 3) gets her first line as context
        calls = provider.synthesize.call_args_list
        assert len(calls) == 4
        # mrs_bennet call at index 1: no previous (first time she speaks), next is her own "Second line."
        assert calls[1].kwargs.get("previous_text") is None
        assert calls[1].kwargs.get("next_text") == "Second line."
        # mrs_bennet call at index 3: previous is her own "First line.", no next
        assert calls[3].kwargs.get("previous_text") == "First line."
        assert calls[3].kwargs.get("next_text") is None

    def test_first_segment_for_character_has_no_previous(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A character's first segment in the chapter gets previous_text=None."""
        # Arrange
        segments = [
            Segment(text="Hello.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Reply.", segment_type=SegmentType.DIALOGUE, character_id="alice"),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1", "alice": "v2"},
        )

        # Assert — alice's first (and only) segment has no same-character context
        calls = provider.synthesize.call_args_list
        assert calls[1].kwargs.get("previous_text") is None
        assert calls[1].kwargs.get("next_text") is None

    def test_voice_settings_passed_through_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """voice_stability/style/speed from Segment are forwarded to provider."""
        # Arrange
        segments = [
            Segment(
                text="Come closer.",
                segment_type=SegmentType.DIALOGUE,
                character_id="spy",
                emotion="secretive",
                voice_stability=0.45,
                voice_style=0.30,
                voice_speed=0.90,
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1", "spy": "v2"},
        )

        # Assert
        calls = provider.synthesize.call_args_list
        assert calls[0].kwargs.get("voice_stability") == 0.45
        assert calls[0].kwargs.get("voice_style") == 0.30
        assert calls[0].kwargs.get("voice_speed") == 0.90

    def test_none_voice_settings_passed_through_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Segments without voice settings pass None to provider."""
        # Arrange
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1"},
        )

        # Assert
        calls = provider.synthesize.call_args_list
        assert calls[0].kwargs.get("voice_stability") is None
        assert calls[0].kwargs.get("voice_style") is None
        assert calls[0].kwargs.get("voice_speed") is None

    def test_skipped_segments_excluded_from_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-synthesisable segments (ILLUSTRATION) are not in the speakable list at all."""
        # Arrange
        segments = [
            Segment(text="Before.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="[Illustration]", segment_type=SegmentType.ILLUSTRATION, character_id=None),
            Segment(text="After.", segment_type=SegmentType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — only 2 synthesize calls (ILLUSTRATION skipped)
        calls = provider.synthesize.call_args_list
        assert len(calls) == 2
        # Narrator's context links its own segments, skipping illustration
        assert calls[0].kwargs.get("previous_text") is None
        assert calls[0].kwargs.get("next_text") == "After."
        assert calls[1].kwargs.get("previous_text") == "Before."
        assert calls[1].kwargs.get("next_text") is None


# ------------------------------------------------------------------
# US-019 Fix 2: previous_request_ids chaining
# ------------------------------------------------------------------


def _fake_synthesize_with_request_id(
    text: str, voice_id: str, path: Path, **kwargs: object
) -> str:
    """Stub TTS provider that writes a tiny file and returns a fake request ID."""
    path.write_bytes(b"\x00" * 64)
    return f"req-{voice_id}-{text[:5]}"


def _fake_synthesize_returns_none(
    text: str, voice_id: str, path: Path, **kwargs: object
) -> None:
    """Stub TTS provider that returns None (no request ID)."""
    path.write_bytes(b"\x00" * 64)
    return None


class TestSynthesiseSegmentsRequestIdChaining:
    """_synthesise_segments passes previous_request_ids per voice sliding window."""

    def test_second_same_voice_segment_gets_first_request_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The second narrator segment receives previous_request_ids containing
        the request ID returned by the first narrator call."""
        # Arrange
        segments = [
            Segment(text="First.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Second.", segment_type=SegmentType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_with_request_id
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert
        calls = provider.synthesize.call_args_list
        # First call: no previous request IDs
        assert calls[0].kwargs.get("previous_request_ids") is None
        # Second call: gets the request ID from the first call
        prev_ids = calls[1].kwargs.get("previous_request_ids")
        assert prev_ids is not None
        assert len(prev_ids) == 1

    def test_sliding_window_limited_to_3_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After 4+ same-voice segments, the window contains only the last 3 IDs."""
        # Arrange
        segments = [
            Segment(text=f"Seg {i}.", segment_type=SegmentType.NARRATION, character_id="narrator")
            for i in range(5)
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_with_request_id
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — 5th call (index 4) should have exactly 3 previous IDs
        calls = provider.synthesize.call_args_list
        prev_ids = calls[4].kwargs.get("previous_request_ids")
        assert prev_ids is not None
        assert len(prev_ids) == 3

    def test_different_voices_have_independent_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each voice_id maintains its own request ID window."""
        # Arrange
        segments = [
            Segment(text="Narr 1.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Alice 1.", segment_type=SegmentType.DIALOGUE, character_id="alice"),
            Segment(text="Narr 2.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Alice 2.", segment_type=SegmentType.DIALOGUE, character_id="alice"),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_with_request_id
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1", "alice": "v2"},
        )

        # Assert
        calls = provider.synthesize.call_args_list
        # Call 0 (narrator): no previous IDs
        assert calls[0].kwargs.get("previous_request_ids") is None
        # Call 1 (alice): no previous IDs (first alice)
        assert calls[1].kwargs.get("previous_request_ids") is None
        # Call 2 (narrator): has 1 ID from narrator's first call
        narr_ids = calls[2].kwargs.get("previous_request_ids")
        assert narr_ids is not None
        assert len(narr_ids) == 1
        # Call 3 (alice): has 1 ID from alice's first call
        alice_ids = calls[3].kwargs.get("previous_request_ids")
        assert alice_ids is not None
        assert len(alice_ids) == 1
        # The IDs should be different (different voices)
        assert narr_ids[0] != alice_ids[0]

    def test_none_request_id_not_added_to_window(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When provider returns None, the window stays empty -- no chaining."""
        # Arrange
        segments = [
            Segment(text="First.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Second.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            Segment(text="Third.", segment_type=SegmentType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_returns_none
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — all calls get None for previous_request_ids (nothing to chain)
        calls = provider.synthesize.call_args_list
        for call in calls:
            assert call.kwargs.get("previous_request_ids") is None


# ------------------------------------------------------------------
# US-020: Scene modifiers applied through to provider
# ------------------------------------------------------------------


class TestSynthesiseSegmentsSceneModifiers:
    """TTSOrchestrator applies scene-based voice modifiers to provider calls."""

    def test_cave_scene_adjusts_voice_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cave scene should lower stability and slow speed for segments with voice settings."""
        # Arrange
        segments = [
            Segment(
                text="Listen...",
                segment_type=SegmentType.DIALOGUE,
                character_id="explorer",
                voice_stability=0.50,
                voice_style=0.20,
                voice_speed=1.0,
            ),
        ]
        scene = Scene(
            scene_id="ch1_cave", environment="cave", acoustic_hints=["echo"],
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        )
        book = _make_book_with_segments(segments, scene=scene)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1", "explorer": "v2"},
        )

        # Assert -- cave: stability -0.05 = 0.45, style unchanged, speed 0.90
        calls = provider.synthesize.call_args_list
        assert abs(calls[0].kwargs["voice_stability"] - 0.45) < 0.001
        assert abs(calls[0].kwargs["voice_style"] - 0.20) < 0.001
        assert abs(calls[0].kwargs["voice_speed"] - 0.90) < 0.001

    def test_no_scene_passes_original_voice_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a scene, voice settings are passed through unmodified."""
        # Arrange
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                voice_stability=0.65,
                voice_style=0.05,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_segments(segments, scene=None)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert
        calls = provider.synthesize.call_args_list
        assert calls[0].kwargs["voice_stability"] == 0.65
        assert calls[0].kwargs["voice_style"] == 0.05
        assert calls[0].kwargs["voice_speed"] == 1.0


# ------------------------------------------------------------------
# SceneRegistry: per-segment scene lookup
# ------------------------------------------------------------------


def _make_book_with_scene_registry(
    segments: list[Segment],
    scene_registry: SceneRegistry,
    chapter_title: str = "Ch 1",
) -> Book:
    """Create a Book with a scene_registry and segments with scene_id."""
    return Book(
        metadata=BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language="en",
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(
            chapters=[
                Chapter(
                    number=1,
                    title=chapter_title,
                    sections=[
                        Section(
                            text="placeholder",
                            segments=segments,
                        ),
                    ],
                ),
            ],
        ),
        character_registry=CharacterRegistry.with_default_narrator(),
        scene_registry=scene_registry,
    )


class TestSynthesiseSegmentsSceneRegistryLookup:
    """TTSOrchestrator uses Book.scene_registry for per-segment scene modifiers."""

    def test_segment_with_scene_id_gets_registry_scene_modifiers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A segment with scene_id='scene_cave' gets cave modifiers from scene_registry."""
        # Arrange
        scene_reg = SceneRegistry()
        scene_reg.upsert(Scene(
            scene_id="scene_cave", environment="cave", acoustic_hints=["echo"],
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        ))
        segments = [
            Segment(
                text="Listen...",
                segment_type=SegmentType.DIALOGUE,
                character_id="explorer",
                scene_id="scene_cave",
                voice_stability=0.50,
                voice_style=0.20,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_scene_registry(segments, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1", "explorer": "v2"},
        )

        # Assert -- cave: stability 0.50 + (-0.05) = 0.45, speed 0.90
        calls = provider.synthesize.call_args_list
        assert abs(calls[0].kwargs["voice_stability"] - 0.45) < 0.001
        assert abs(calls[0].kwargs["voice_style"] - 0.20) < 0.001
        assert abs(calls[0].kwargs["voice_speed"] - 0.90) < 0.001

    def test_segment_without_scene_id_unmodified_when_registry_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A segment with scene_id=None gets no modifiers even when registry has scenes."""
        # Arrange
        scene_reg = SceneRegistry()
        scene_reg.upsert(Scene(
            scene_id="scene_cave", environment="cave",
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        ))
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id=None,
                voice_stability=0.65,
                voice_style=0.05,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_scene_registry(segments, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert -- no modifiers applied
        calls = provider.synthesize.call_args_list
        assert calls[0].kwargs["voice_stability"] == 0.65
        assert calls[0].kwargs["voice_style"] == 0.05
        assert calls[0].kwargs["voice_speed"] == 1.0


# ------------------------------------------------------------------
# US-011: Ambient background sound
# ------------------------------------------------------------------


class TestBuildAmbientFilterComplex:
    """build_ambient_filter_complex constructs the correct ffmpeg filter."""

    def test_single_scene_ambient_filter(self) -> None:
        """One ambient track at -18 dB covering the full chapter."""
        # Arrange
        ambient_entries = [
            (Path("/tmp/ambient/cave.mp3"), -18.0, 0.0, 120.0),
        ]

        # Act
        filter_str = build_ambient_filter_complex(ambient_entries, cross_fade_seconds=5.0)

        # Assert — filter should contain volume adjustment and amix
        assert filter_str is not None
        assert "volume=-18.0dB" in filter_str
        assert "amix" in filter_str

    def test_two_scene_crossfade_filter(self) -> None:
        """Two adjacent scenes produce a cross-fade at the boundary."""
        # Arrange
        ambient_entries = [
            (Path("/tmp/ambient/cave.mp3"), -18.0, 0.0, 60.0),
            (Path("/tmp/ambient/forest.mp3"), -16.0, 60.0, 120.0),
        ]

        # Act
        filter_str = build_ambient_filter_complex(ambient_entries, cross_fade_seconds=5.0)

        # Assert — filter has two volume adjustments and acrossfade
        assert filter_str is not None
        assert "volume=-18.0dB" in filter_str
        assert "volume=-16.0dB" in filter_str
        assert "acrossfade" in filter_str

    def test_empty_entries_returns_none(self) -> None:
        """No ambient entries means no filter needed."""
        # Arrange / Act
        result = build_ambient_filter_complex([], cross_fade_seconds=5.0)

        # Assert
        assert result is None


class TestAmbientEnabledFlag:
    """TTSOrchestrator.ambient_enabled controls ambient processing."""

    def test_ambient_disabled_skips_ambient(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ambient_enabled=False, no ambient mixing occurs even with ambient scenes."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            ambient_prompt="dripping water, echoes",
            ambient_volume=-18.0,
        )
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(segments, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path, ambient_enabled=False)

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert — chapter produced, no ambient directory created
        assert result.exists()
        ambient_dir = tmp_path / "Ch 1" / "ambient"
        assert not ambient_dir.exists()


class TestNoAmbientScenesIdenticalToToday:
    """When no scenes have ambient_prompt, behavior is identical to pre-US-011."""

    def test_chapter_without_ambient_scenes_produces_same_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Scenes without ambient_prompt produce chapter identically to before."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            # No ambient_prompt or ambient_volume
        )
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(segments, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert — chapter produced normally
        assert result.exists()


# ------------------------------------------------------------------
# Compute scene time ranges
# ------------------------------------------------------------------


class TestComputeSceneTimeRanges:
    """_compute_scene_time_ranges maps scene_ids to (start, end) second offsets."""

    def test_single_scene_covers_full_duration(self) -> None:
        """All segments in one scene: range is (0.0, total_duration)."""
        # Arrange
        segments = [
            Segment(text="A.", segment_type=SegmentType.NARRATION, character_id="narrator", scene_id="s1"),
            Segment(text="B.", segment_type=SegmentType.NARRATION, character_id="narrator", scene_id="s1"),
        ]
        durations = [10.0, 5.0]

        # Act
        from src.tts.tts_orchestrator import _compute_scene_time_ranges
        ranges = _compute_scene_time_ranges(segments, durations)

        # Assert — single scene from 0.0 to 15.0
        assert len(ranges) == 1
        assert ranges["s1"] == (0.0, 15.0)

    def test_two_scenes_sequential(self) -> None:
        """Two scenes in sequence get non-overlapping time ranges."""
        # Arrange
        segments = [
            Segment(text="A.", segment_type=SegmentType.NARRATION, character_id="narrator", scene_id="s1"),
            Segment(text="B.", segment_type=SegmentType.NARRATION, character_id="narrator", scene_id="s1"),
            Segment(text="C.", segment_type=SegmentType.NARRATION, character_id="narrator", scene_id="s2"),
        ]
        durations = [10.0, 5.0, 8.0]

        # Act
        from src.tts.tts_orchestrator import _compute_scene_time_ranges
        ranges = _compute_scene_time_ranges(segments, durations)

        # Assert
        assert len(ranges) == 2
        assert ranges["s1"] == (0.0, 15.0)
        assert ranges["s2"] == (15.0, 23.0)

    def test_segments_without_scene_id_excluded(self) -> None:
        """Segments with scene_id=None do not create time range entries."""
        # Arrange
        segments = [
            Segment(text="A.", segment_type=SegmentType.NARRATION, character_id="narrator", scene_id=None),
            Segment(text="B.", segment_type=SegmentType.NARRATION, character_id="narrator", scene_id="s1"),
        ]
        durations = [10.0, 5.0]

        # Act
        from src.tts.tts_orchestrator import _compute_scene_time_ranges
        ranges = _compute_scene_time_ranges(segments, durations)

        # Assert — only s1 present
        assert len(ranges) == 1
        assert ranges["s1"] == (10.0, 15.0)


# ------------------------------------------------------------------
# Ambient wiring: get_ambient_audio called for ambient scenes
# ------------------------------------------------------------------


class TestAmbientWiringCallsGetAmbientAudio:
    """synthesize_chapter calls get_ambient_audio for scenes with ambient_prompt."""

    def test_ambient_enabled_calls_get_ambient_audio(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With ambient_enabled=True and a scene with ambient_prompt,
        get_ambient_audio is called with that scene."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            ambient_prompt="dripping water",
            ambient_volume=-18.0,
        )
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(segments, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # Create mock ambient provider to track calls
        from src.tts.ambient_provider import AmbientProvider
        ambient_calls: list[str] = []

        class MockAmbientProvider(AmbientProvider):
            def generate(
                self, prompt: str, output_path: Path, duration_seconds: float = 60.0
            ) -> Optional[Path]:
                # Extract scene_id from output_path name
                scene_id = output_path.stem
                ambient_calls.append(scene_id)
                return None

        # Stub _get_audio_duration to return a fixed value
        monkeypatch.setattr(
            "src.tts.tts_orchestrator._get_audio_duration", lambda p: 5.0
        )

        ambient_provider = MockAmbientProvider()
        orch = TTSOrchestrator(
            provider, output_dir=tmp_path, ambient_enabled=True,
            ambient_provider=ambient_provider,
        )

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert — provider.generate was called for the cave scene
        assert "cave" in ambient_calls


class TestAmbientWiringNoClientSkipsAmbient:
    """When ambient_client is None, ambient processing is skipped."""

    def test_no_ambient_client_skips_ambient(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without an ambient_client, no ambient generation occurs."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            ambient_prompt="dripping water",
            ambient_volume=-18.0,
        )
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(segments, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # No ambient_client passed (default None)
        orch = TTSOrchestrator(provider, output_dir=tmp_path, ambient_enabled=True)

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert — chapter produced, no ambient directory
        assert result.exists()


class TestAmbientWiringGetAmbientReturnsNone:
    """When get_ambient_audio returns None, that scene is skipped gracefully."""

    def test_none_ambient_does_not_trigger_mixing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If get_ambient_audio returns None for all scenes, no mixing occurs."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            ambient_prompt="dripping water",
            ambient_volume=-18.0,
        )
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(segments, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # Create mock ambient provider that returns None (API failure)
        from src.tts.ambient_provider import AmbientProvider

        class FailingAmbientProvider(AmbientProvider):
            def generate(
                self, prompt: str, output_path: Path, duration_seconds: float = 60.0
            ) -> Optional[Path]:
                return None

        monkeypatch.setattr(
            "src.tts.tts_orchestrator._get_audio_duration", lambda p: 5.0
        )

        ambient_provider = FailingAmbientProvider()
        orch = TTSOrchestrator(
            provider, output_dir=tmp_path, ambient_enabled=True,
            ambient_provider=ambient_provider,
        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert — chapter still produced successfully (no mixing needed)
        assert result.exists()


class TestAmbientWiringMixesAudio:
    """When ambient audio is available, _mix_ambient_into_speech is called."""

    def test_ambient_mix_called_with_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With a valid ambient file, _mix_ambient_into_speech is invoked."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            ambient_prompt="dripping water",
            ambient_volume=-18.0,
        )
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(segments, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # Create mock ambient provider that returns a fake file
        from src.tts.ambient_provider import AmbientProvider

        class WorkingAmbientProvider(AmbientProvider):
            def generate(
                self, prompt: str, output_path: Path, duration_seconds: float = 60.0
            ) -> Optional[Path]:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"\xff" * 100)
                return output_path

        monkeypatch.setattr(
            "src.tts.tts_orchestrator._get_audio_duration", lambda p: 5.0
        )

        # Track _mix_ambient_into_speech calls
        mix_calls: list[tuple[Path, list[tuple[Path, float, float, float]]]] = []

        def _fake_mix(
            self: TTSOrchestrator,
            speech_path: Path,
            ambient_entries: list[tuple[Path, float, float, float]],
        ) -> None:
            mix_calls.append((speech_path, ambient_entries))

        monkeypatch.setattr(TTSOrchestrator, "_mix_ambient_into_speech", _fake_mix)

        ambient_provider = WorkingAmbientProvider()
        orch = TTSOrchestrator(
            provider, output_dir=tmp_path, ambient_enabled=True,
            ambient_provider=ambient_provider,
        )

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert — _mix_ambient_into_speech was called with correct entries
        assert len(mix_calls) == 1
        speech_path, entries = mix_calls[0]
        assert speech_path.name == "chapter.mp3"
        assert len(entries) == 1
        assert entries[0][0].name == "cave.mp3"  # ambient path (scene_id.mp3)
        assert entries[0][1] == -18.0  # volume
        assert entries[0][2] == 0.0  # start time
        assert entries[0][3] == 5.0  # end time


# ── Sound Effects Insertion (US-023 Cinematic Sound Effects) ────────────────

class TestSoundEffectsInsertion:
    """Tests for sound effects insertion into silence gaps."""

    def test_segment_with_sound_effect_description_but_no_client_skips_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When sound_effect_description is set but sfx_client is None, skip gracefully."""
        # Arrange
        segments = [
            Segment(
                text="She coughed.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                sound_effect_description="dry cough",
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            cinematic_sfx_enabled=True,
            sfx_client=None,  # No SFX client
        )

        # Act — should complete without error
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"}
        )

        # Assert — chapter still produced (no SFX but no failure)
        assert result.exists()

    def test_segment_without_sound_effect_description_produces_normal_silence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Segments without sound_effect_description produce normal silence gaps."""
        # Arrange
        segments = [
            Segment(
                text="Hello.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                sound_effect_description=None,  # No SFX
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        mock_sfx_client = MagicMock()
        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            cinematic_sfx_enabled=True,
            sfx_client=mock_sfx_client,
        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"}
        )

        # Assert
        assert result.exists()
        # SFX client should not be called (no sound_effect_description)
        mock_sfx_client.assert_not_called()

    def test_feature_flag_disabled_skips_all_sfx(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When cinematic_sfx_enabled=False, no SFX are generated even if described."""
        # Arrange
        segments = [
            Segment(
                text="Thunder crashed.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                sound_effect_description="thunder crash",
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        mock_sfx_client = MagicMock()
        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            cinematic_sfx_enabled=False,  # Feature disabled
            sfx_client=mock_sfx_client,
        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"}
        )

        # Assert
        assert result.exists()
        # SFX client should not be called (feature disabled)
        mock_sfx_client.assert_not_called()

    def test_sfx_client_can_be_passed_to_orchestrator(self, tmp_path: Path) -> None:
        """TTSOrchestrator accepts sfx_client parameter."""
        # Arrange
        provider = MagicMock()
        mock_sfx_client = MagicMock()

        # Act
        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            cinematic_sfx_enabled=True,
            sfx_client=mock_sfx_client,
        )

        # Assert
        assert orch._sfx_client is mock_sfx_client


# ------------------------------------------------------------------
# Feature Flags: emotion_enabled, voice_design_enabled, scene_context_enabled
# ------------------------------------------------------------------


class TestEmotionEnabledFlag:
    """Tests for emotion_enabled flag enforcement in _synthesise_segments."""

    def test_emotion_enabled_false_passes_none_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When emotion_enabled=False, synthesize is called with emotion=None."""
        # Arrange
        segments = [
            Segment(
                text="Hello with emotion.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                emotion="whispers",
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            emotion_enabled=False,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — synthesize should be called with emotion=None
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        assert call_kwargs.get("emotion") is None

    def test_emotion_enabled_true_passes_segment_emotion_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When emotion_enabled=True, synthesize is called with segment.emotion."""
        # Arrange
        segments = [
            Segment(
                text="Hello with emotion.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                emotion="whispers",
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            emotion_enabled=True,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — synthesize should be called with emotion="whispers"
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        assert call_kwargs.get("emotion") == "whispers"

    def test_emotion_enabled_false_overrides_nonzero_emotion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Emotion flag disables even strong emotions like 'angry'."""
        # Arrange
        segments = [
            Segment(
                text="I am angry!",
                segment_type=SegmentType.DIALOGUE,
                character_id="alice",
                emotion="angry",
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            emotion_enabled=False,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1", "alice": "v2"})

        # Assert — emotion should still be None despite segment having "angry"
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        assert call_kwargs.get("emotion") is None


class TestVoiceDesignEnabledFlag:
    """Tests for voice_design_enabled flag enforcement in _synthesise_segments."""

    def test_voice_design_enabled_false_passes_none_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When voice_design_enabled=False, synthesize is called with voice_*=None."""
        # Arrange
        segments = [
            Segment(
                text="Hello with design.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                voice_stability=0.6,
                voice_style=0.7,
                voice_speed=1.05,
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            voice_design_enabled=False,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — all voice_* should be None
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        assert call_kwargs.get("voice_stability") is None
        assert call_kwargs.get("voice_style") is None
        assert call_kwargs.get("voice_speed") is None

    def test_voice_design_enabled_true_passes_voice_settings_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When voice_design_enabled=True, synthesize is called with segment voice settings."""
        # Arrange
        segments = [
            Segment(
                text="Hello with design.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                voice_stability=0.6,
                voice_style=0.7,
                voice_speed=1.05,
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            voice_design_enabled=True,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — voice settings should be passed through
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        assert call_kwargs.get("voice_stability") == 0.6
        assert call_kwargs.get("voice_style") == 0.7
        assert call_kwargs.get("voice_speed") == 1.05

    def test_voice_design_enabled_false_overrides_nonzero_voice_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Voice design flag disables even strong voice settings."""
        # Arrange
        segments = [
            Segment(
                text="Strong voice design.",
                segment_type=SegmentType.DIALOGUE,
                character_id="alice",
                voice_stability=0.95,
                voice_style=0.95,
                voice_speed=1.5,
            ),
        ]
        book = _make_book_with_segments(segments)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            voice_design_enabled=False,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1", "alice": "v2"})

        # Assert — all voice_* should be None despite high values
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        assert call_kwargs.get("voice_stability") is None
        assert call_kwargs.get("voice_style") is None
        assert call_kwargs.get("voice_speed") is None


class TestSceneContextEnabledFlag:
    """Tests for scene_context_enabled flag enforcement in scene modifiers."""

    def test_scene_context_enabled_false_does_not_apply_scene_modifiers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When scene_context_enabled=False, scene modifiers are not applied."""
        # Arrange
        scene = Scene(
            scene_id="forest",
            environment="Forest",
            voice_modifiers={
                "stability_delta": 0.1,
                "style_delta": 0.2,
                "speed": 1.05,
            },
        )
        segments = [
            Segment(
                text="In the forest.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="forest",
                voice_stability=0.5,
                voice_style=0.3,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_segments(segments, scene=scene)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            scene_context_enabled=False,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — voice settings should NOT be modified by scene
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        # Without scene modifiers, values should remain as original
        assert call_kwargs.get("voice_stability") == 0.5
        assert call_kwargs.get("voice_style") == 0.3
        assert call_kwargs.get("voice_speed") == 1.0

    def test_scene_context_enabled_true_applies_scene_modifiers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When scene_context_enabled=True, scene modifiers are applied."""
        # Arrange
        scene = Scene(
            scene_id="forest",
            environment="Forest",
            voice_modifiers={
                "stability_delta": 0.1,
                "style_delta": 0.2,
                "speed": 1.05,
            },
        )
        segments = [
            Segment(
                text="In the forest.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="forest",
                voice_stability=0.5,
                voice_style=0.3,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_segments(segments, scene=scene)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            scene_context_enabled=True,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — voice settings should be modified by scene
        provider.synthesize.assert_called_once()
        call_kwargs = provider.synthesize.call_args.kwargs
        # With scene modifiers: stability = 0.5 + 0.1 = 0.6, style = 0.3 + 0.2 = 0.5, speed = 1.05
        assert call_kwargs.get("voice_stability") == 0.6
        assert call_kwargs.get("voice_style") == 0.5
        assert call_kwargs.get("voice_speed") == 1.05

    def test_scene_context_enabled_false_still_sets_scene_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Disabling scene context doesn't remove scene_id, just modifiers."""
        # Arrange — verify scene_id is still in the book even when not applying modifiers
        scene = Scene(
            scene_id="library",
            environment="Library",
            voice_modifiers={"stability_delta": 0.15},
        )
        segments = [
            Segment(
                text="In the library.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
                scene_id="library",
                voice_stability=0.6,
            ),
        ]
        book = _make_book_with_segments(segments, scene=scene)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(TTSOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = TTSOrchestrator(
            provider,
            output_dir=tmp_path,
            scene_context_enabled=False,
        )

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — the chapter was synthesized without errors; scene_id is not a synthesize param
        # but the absence of an error confirms the scene is still tracked in the book
        provider.synthesize.assert_called_once()
        assert book.scene_registry.get("library") is not None


class TestFeatureFlagsInjection:
    """TTSOrchestrator accepts FeatureFlags instance and uses its values."""

    def test_orchestrator_accepts_feature_flags_parameter(self, tmp_path: Path) -> None:
        """Constructor accepts a FeatureFlags instance without error."""
        # Arrange
        provider = MagicMock()
        flags = FeatureFlags(
            emotion_enabled=False,
            voice_design_enabled=False,
            scene_context_enabled=False,
            ambient_enabled=False,
            cinematic_sfx_enabled=False,
        )

        # Act
        orch = TTSOrchestrator(provider, output_dir=tmp_path, feature_flags=flags)

        # Assert — orchestrator stores the flags instance
        assert orch._feature_flags == flags

    def test_orchestrator_reads_emotion_enabled_from_feature_flags(self, tmp_path: Path) -> None:
        """When emotion_enabled is False in FeatureFlags, orchestrator reads that value."""
        # Arrange
        provider = MagicMock()
        flags = FeatureFlags(emotion_enabled=False)

        # Act
        orch = TTSOrchestrator(provider, output_dir=tmp_path, feature_flags=flags)

        # Assert — orchestrator uses the feature flag value
        assert orch._feature_flags.emotion_enabled is False

    def test_orchestrator_defaults_to_all_flags_enabled(self, tmp_path: Path) -> None:
        """When feature_flags is not provided, all features are enabled by default."""
        # Arrange
        provider = MagicMock()

        # Act
        orch = TTSOrchestrator(provider, output_dir=tmp_path)

        # Assert — all feature flags are True by default
        assert orch._feature_flags.emotion_enabled is True
        assert orch._feature_flags.voice_design_enabled is True
        assert orch._feature_flags.scene_context_enabled is True
        assert orch._feature_flags.ambient_enabled is True
        assert orch._feature_flags.cinematic_sfx_enabled is True
