"""Tests for AudioOrchestrator — silence insertion and chapter folder output.

These tests verify:
  - Silence clips are inserted between consecutive TTS beats at stitch time,
    with duration varying by boundary type (same speaker vs. speaker change).
  - Output goes to named per-chapter subfolders: ``audio/{chapter_title}/chapter.mp3``.
  - ``debug=True`` retains individual ``beat_NNNN.mp3`` files alongside ``chapter.mp3``.
  - ``debug=False`` (default) cleans up beat files after stitching.
  - ``_sanitize_dirname`` replaces filesystem-unsafe characters.
  - Ambient audio is generated and mixed when ``ambient_enabled=True`` and scenes have
    ``ambient_prompt`` values.
"""
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from src.audio.audio_orchestrator import (
    AudioOrchestrator,
    _sanitize_dirname,
    build_ambient_filter_complex,
)
from src.config.feature_flags import FeatureFlags
from src.domain.models import (
    Beat,
    BeatType,
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    CharacterRegistry,
    Scene,
    SceneRegistry,
    Section,
)


def _make_beat(character_id: str) -> Beat:
    """Create a minimal speakable beat with the given character_id."""
    return Beat(
        text="Some text.",
        beat_type=BeatType.NARRATION,
        character_id=character_id,
    )


class TestBuildConcatEntriesSameSpeaker:
    """Same-speaker boundaries use the short silence duration."""

    def test_same_speaker_boundary_uses_short_silence(self, tmp_path: Path) -> None:
        """Two beats with the same character_id produce a silence gap
        of silence_same_speaker_ms duration."""
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [_make_beat("narrator"), _make_beat("narrator")]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — 2 beat entries + 1 silence entry = 3 total
        assert len(entries) == 3
        # The middle entry should be a silence file path containing '150'
        silence_entry = entries[1]
        assert "silence_150ms" in silence_entry.name


class TestBuildConcatEntriesSpeakerChange:
    """Speaker-change boundaries use the long silence duration."""

    def test_speaker_change_boundary_uses_long_silence(self, tmp_path: Path) -> None:
        """Two beats with different character_id produce a silence gap
        of silence_speaker_change_ms duration."""
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [_make_beat("narrator"), _make_beat("alice")]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — 2 beat entries + 1 silence entry = 3 total
        assert len(entries) == 3
        silence_entry = entries[1]
        assert "silence_400ms" in silence_entry.name


class TestBuildConcatEntriesGapCount:
    """N beats produce exactly N-1 silence gaps."""

    def test_three_beats_produce_two_gaps(self, tmp_path: Path) -> None:
        """Three beats must yield 3 beat entries + 2 silence entries = 5."""
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [
            _make_beat("narrator"),
            _make_beat("alice"),
            _make_beat("narrator"),
        ]
        beat_paths = [tmp_path / f"beat_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — 3 beats + 2 gaps = 5
        assert len(entries) == 5
        # Positions 1 and 3 are silence entries
        assert "silence_" in entries[1].name
        assert "silence_" in entries[3].name


class TestBuildConcatEntriesSingleBeat:
    """A single beat produces no silence clips."""

    def test_single_beat_has_no_silence(self, tmp_path: Path) -> None:
        """One beat must yield exactly 1 entry with no silence."""
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [_make_beat("narrator")]
        beat_paths = [tmp_path / "beat_0.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert
        assert len(entries) == 1
        assert entries[0] == beat_paths[0]


class TestBuildConcatEntriesCustomDurations:
    """Custom silence durations are respected."""

    def test_custom_silence_durations(self, tmp_path: Path) -> None:
        """Non-default silence durations are reflected in silence file names."""
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(
            provider,
            output_dir=tmp_path,
            silence_same_speaker_ms=200,
            silence_speaker_change_ms=500,
        )
        beats = [
            _make_beat("narrator"),
            _make_beat("narrator"),
            _make_beat("alice"),
        ]
        beat_paths = [tmp_path / f"beat_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — first gap is same-speaker (200ms), second is change (500ms)
        assert "silence_200ms" in entries[1].name
        assert "silence_500ms" in entries[3].name


class TestSilenceClipReuse:
    """Silence clips of the same duration are generated once and reused."""

    def test_same_duration_silence_paths_are_identical(self, tmp_path: Path) -> None:
        """Multiple same-speaker gaps should reference the same silence file path."""
        # Arrange
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [
            _make_beat("narrator"),
            _make_beat("narrator"),
            _make_beat("narrator"),
        ]
        beat_paths = [tmp_path / f"beat_{i}.mp3" for i in range(3)]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — both silence entries reference the exact same path
        assert entries[1] == entries[3]


# ------------------------------------------------------------------
# Helpers for synthesize_chapter tests
# ------------------------------------------------------------------

def _make_book(chapter_title: str = "Chapter 1") -> Book:
    """Create a minimal Book with one chapter containing two narration beats."""
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
                            beats=[
                                Beat(
                                    text="Hello world.",
                                    beat_type=BeatType.NARRATION,
                                    character_id="narrator",
                                ),
                                Beat(
                                    text="Goodbye world.",
                                    beat_type=BeatType.NARRATION,
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


def _fake_generate_silence(
    self: AudioOrchestrator,
    duration_ms: int,
    work_dir: Path,
) -> Path:
    """Replace _generate_silence_clip to avoid ffmpeg dependency in tests."""
    silence_path = work_dir / f"silence_{duration_ms}ms.mp3"
    silence_path.write_bytes(b"\x00" * 16)
    return silence_path


def _fake_ffmpeg_stitch(
    self: AudioOrchestrator,
    beat_paths: list[Path],
    output_path: Path,
    beats: list[Beat] | None = None,
) -> None:
    """Replace _stitch_with_ffmpeg to avoid a real ffmpeg dependency in tests."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x00" * 128)
    # Simulate concat_list.txt and silence files that ffmpeg would leave behind
    concat_dir = beat_paths[0].parent if beat_paths else output_path.parent
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
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        book = _make_book("Chapter 1")

        # Act
        result = orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert
        assert result == tmp_path / "Chapter 1" / "chapter.mp3"
        assert result.exists()


# ------------------------------------------------------------------
# synthesize_chapter — debug mode keeps beats
# ------------------------------------------------------------------


class TestSynthesizeChapterDebugKeepsBeats:
    """debug=True retains beat_NNNN.mp3 files alongside chapter.mp3."""

    def test_synthesize_chapter_debug_keeps_beats(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In debug mode, beat files remain in the chapter folder."""
        # Arrange
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, debug=True)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — beat files persist
        chapter_dir = tmp_path / "Chapter 1"
        beat_files = sorted(chapter_dir.glob("beat_*.mp3"))
        assert len(beat_files) == 2
        assert beat_files[0].name == "beat_0000.mp3"
        assert beat_files[1].name == "beat_0001.mp3"


# ------------------------------------------------------------------
# synthesize_chapter — normal mode cleans beats
# ------------------------------------------------------------------


class TestSynthesizeChapterNormalPreservesBeats:
    """debug=False preserves beats in a permanent beats/{provider_name}/ dir."""

    def test_synthesize_chapter_normal_preserves_beats(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In normal mode, beat_*.mp3 files persist in beats/{provider.name}/ subdir."""
        # Arrange
        provider = MagicMock()
        provider.name = "mock_tts"
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, debug=False)
        book = _make_book("Chapter 1")

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — beats persist in named subdir
        beats_dir = tmp_path / "Chapter 1" / "beats" / "mock_tts"
        beat_files = sorted(beats_dir.glob("beat_*.mp3"))
        assert len(beat_files) == 2
        # chapter.mp3 still exists
        assert (tmp_path / "Chapter 1" / "chapter.mp3").exists()


class TestSynthesizeChapterSkipsCachedBeats:
    """Cached beats (existing non-empty files) are not re-synthesized."""

    def test_cached_beat_skips_synthesis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a beat file already exists and is non-empty, synthesize is not called for it."""
        # Arrange
        provider = MagicMock()
        provider.name = "mock_tts"
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, debug=False)
        book = _make_book("Chapter 1")

        # Pre-create one cached beat (beat_0000.mp3)
        beats_dir = tmp_path / "Chapter 1" / "beats" / "mock_tts"
        beats_dir.mkdir(parents=True)
        cached = beats_dir / "beat_0000.mp3"
        cached.write_bytes(b"\xff" * 64)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — only the second beat was synthesized
        assert provider.synthesize.call_count == 1


# ------------------------------------------------------------------
# US-019 Fix 1: previous_text / next_text context
# ------------------------------------------------------------------


def _make_book_with_beats(
    beats: list[Beat],
    chapter_title: str = "Ch 1",
    scene: Scene | None = None,
) -> Book:
    """Create a Book with a single chapter containing the given beats.

    When *scene* is provided, it is added to the book's ``scene_registry``
    and each beat gets its ``scene_id`` set (if not already set).
    """
    scene_registry = SceneRegistry()
    if scene is not None:
        scene_registry.upsert(scene)
        for seg in beats:
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
                            beats=beats,
                        ),
                    ],
                ),
            ],
        ),
        character_registry=CharacterRegistry.with_default_narrator(),
        scene_registry=scene_registry,
    )


class TestSynthesiseBeatsPassesSameCharacterContext:
    """_synthesise_beats passes previous_text/next_text from same-character beats."""

    def test_same_character_gets_own_previous_and_next(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Three narrator beats: middle one gets context from the other two."""
        # Arrange
        beats = [
            Beat(text="First.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Second.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Third.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
        beats = [
            Beat(text="Narration.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="First line.", beat_type=BeatType.DIALOGUE, character_id="mrs_bennet"),
            Beat(text="More narration.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Second line.", beat_type=BeatType.DIALOGUE, character_id="mrs_bennet"),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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

    def test_first_beat_for_character_has_no_previous(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A character's first beat in the chapter gets previous_text=None."""
        # Arrange
        beats = [
            Beat(text="Hello.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Reply.", beat_type=BeatType.DIALOGUE, character_id="alice"),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1,
            voice_assignment={"narrator": "v1", "alice": "v2"},
        )

        # Assert — alice's first (and only) beat has no same-character context
        calls = provider.synthesize.call_args_list
        assert calls[1].kwargs.get("previous_text") is None
        assert calls[1].kwargs.get("next_text") is None

    def test_voice_settings_passed_through_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """voice_stability/style/speed from Beat are forwarded to provider."""
        # Arrange
        beats = [
            Beat(
                text="Come closer.",
                beat_type=BeatType.DIALOGUE,
                character_id="spy",
                emotion="secretive",
                voice_stability=0.45,
                voice_style=0.30,
                voice_speed=0.90,
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
        """Beats without voice settings pass None to provider."""
        # Arrange
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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

    def test_skipped_beats_excluded_from_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-synthesisable beats (ILLUSTRATION) are not in the speakable list at all."""
        # Arrange
        beats = [
            Beat(text="Before.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="[Illustration]", beat_type=BeatType.ILLUSTRATION, character_id=None),
            Beat(text="After.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — only 2 synthesize calls (ILLUSTRATION skipped)
        calls = provider.synthesize.call_args_list
        assert len(calls) == 2
        # Narrator's context links its own beats, skipping illustration
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


class TestSynthesiseBeatsRequestIdChaining:
    """_synthesise_beats passes previous_request_ids per voice sliding window."""

    def test_second_same_voice_beat_gets_first_request_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The second narrator beat receives previous_request_ids containing
        the request ID returned by the first narrator call."""
        # Arrange
        beats = [
            Beat(text="First.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Second.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_with_request_id
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
        """After 4+ same-voice beats, the window contains only the last 3 IDs."""
        # Arrange
        beats = [
            Beat(text=f"Seg {i}.", beat_type=BeatType.NARRATION, character_id="narrator")
            for i in range(5)
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_with_request_id
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
        beats = [
            Beat(text="Narr 1.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Alice 1.", beat_type=BeatType.DIALOGUE, character_id="alice"),
            Beat(text="Narr 2.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Alice 2.", beat_type=BeatType.DIALOGUE, character_id="alice"),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_with_request_id
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
        beats = [
            Beat(text="First.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Second.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Third.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize_returns_none
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert — all calls get None for previous_request_ids (nothing to chain)
        calls = provider.synthesize.call_args_list
        for call in calls:
            assert call.kwargs.get("previous_request_ids") is None


# ------------------------------------------------------------------
# US-020: Scene modifiers applied through to provider
# ------------------------------------------------------------------


class TestSynthesiseBeatsSceneModifiers:
    """AudioOrchestrator applies scene-based voice modifiers to provider calls."""

    def test_cave_scene_adjusts_voice_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cave scene should lower stability and slow speed for beats with voice settings."""
        # Arrange
        beats = [
            Beat(
                text="Listen...",
                beat_type=BeatType.DIALOGUE,
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
        book = _make_book_with_beats(beats, scene=scene)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                voice_stability=0.65,
                voice_style=0.05,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_beats(beats, scene=None)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(book, chapter_number=1, voice_assignment={"narrator": "v1"})

        # Assert
        calls = provider.synthesize.call_args_list
        assert calls[0].kwargs["voice_stability"] == 0.65
        assert calls[0].kwargs["voice_style"] == 0.05
        assert calls[0].kwargs["voice_speed"] == 1.0


# ------------------------------------------------------------------
# SceneRegistry: per-beat scene lookup
# ------------------------------------------------------------------


def _make_book_with_scene_registry(
    beats: list[Beat],
    scene_registry: SceneRegistry,
    chapter_title: str = "Ch 1",
) -> Book:
    """Create a Book with a scene_registry and beats with scene_id."""
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
                            beats=beats,
                        ),
                    ],
                ),
            ],
        ),
        character_registry=CharacterRegistry.with_default_narrator(),
        scene_registry=scene_registry,
    )


class TestSynthesiseBeatsSceneRegistryLookup:
    """AudioOrchestrator uses Book.scene_registry for per-beat scene modifiers."""

    def test_beat_with_scene_id_gets_registry_scene_modifiers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A beat with scene_id='scene_cave' gets cave modifiers from scene_registry."""
        # Arrange
        scene_reg = SceneRegistry()
        scene_reg.upsert(Scene(
            scene_id="scene_cave", environment="cave", acoustic_hints=["echo"],
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        ))
        beats = [
            Beat(
                text="Listen...",
                beat_type=BeatType.DIALOGUE,
                character_id="explorer",
                scene_id="scene_cave",
                voice_stability=0.50,
                voice_style=0.20,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_scene_registry(beats, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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

    def test_beat_without_scene_id_unmodified_when_registry_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A beat with scene_id=None gets no modifiers even when registry has scenes."""
        # Arrange
        scene_reg = SceneRegistry()
        scene_reg.upsert(Scene(
            scene_id="scene_cave", environment="cave",
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        ))
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id=None,
                voice_stability=0.65,
                voice_style=0.05,
                voice_speed=1.0,
            ),
        ]
        book = _make_book_with_scene_registry(beats, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
    """AudioOrchestrator.ambient_enabled controls ambient processing."""

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
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(beats, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, feature_flags=FeatureFlags(ambient_enabled=False))

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
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(beats, scene_reg)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

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
        """All beats in one scene: range is (0.0, total_duration)."""
        # Arrange
        beats = [
            Beat(text="A.", beat_type=BeatType.NARRATION, character_id="narrator", scene_id="s1"),
            Beat(text="B.", beat_type=BeatType.NARRATION, character_id="narrator", scene_id="s1"),
        ]
        durations = [10.0, 5.0]

        # Act
        from src.audio.audio_orchestrator import _compute_scene_time_ranges
        ranges = _compute_scene_time_ranges(beats, durations)

        # Assert — single scene from 0.0 to 15.0
        assert len(ranges) == 1
        assert ranges["s1"] == (0.0, 15.0)

    def test_two_scenes_sequential(self) -> None:
        """Two scenes in sequence get non-overlapping time ranges."""
        # Arrange
        beats = [
            Beat(text="A.", beat_type=BeatType.NARRATION, character_id="narrator", scene_id="s1"),
            Beat(text="B.", beat_type=BeatType.NARRATION, character_id="narrator", scene_id="s1"),
            Beat(text="C.", beat_type=BeatType.NARRATION, character_id="narrator", scene_id="s2"),
        ]
        durations = [10.0, 5.0, 8.0]

        # Act
        from src.audio.audio_orchestrator import _compute_scene_time_ranges
        ranges = _compute_scene_time_ranges(beats, durations)

        # Assert
        assert len(ranges) == 2
        assert ranges["s1"] == (0.0, 15.0)
        assert ranges["s2"] == (15.0, 23.0)

    def test_beats_without_scene_id_excluded(self) -> None:
        """Beats with scene_id=None do not create time range entries."""
        # Arrange
        beats = [
            Beat(text="A.", beat_type=BeatType.NARRATION, character_id="narrator", scene_id=None),
            Beat(text="B.", beat_type=BeatType.NARRATION, character_id="narrator", scene_id="s1"),
        ]
        durations = [10.0, 5.0]

        # Act
        from src.audio.audio_orchestrator import _compute_scene_time_ranges
        ranges = _compute_scene_time_ranges(beats, durations)

        # Assert — only s1 present
        assert len(ranges) == 1
        assert ranges["s1"] == (10.0, 15.0)


# ------------------------------------------------------------------
# Ambient wiring: AmbientProvider invoked for ambient scenes
# ------------------------------------------------------------------


class TestAmbientWiringCallsAmbientProvider:
    """synthesize_chapter invokes the AmbientProvider for scenes with ambient_prompt."""

    def test_ambient_enabled_calls_ambient_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With ambient_enabled=True and a scene with ambient_prompt,
        the AmbientProvider is invoked for that scene."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            ambient_prompt="dripping water",
            ambient_volume=-18.0,
        )
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(beats, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # Create mock ambient provider to track calls
        from src.audio.ambient.ambient_provider import AmbientProvider
        ambient_calls: list[str] = []

        class MockAmbientProvider(AmbientProvider):
            @property
            def name(self) -> str:
                return "mock"

            def provide(self, scene: Any, book_id: str) -> float:
                return 0.0

            def _generate(
                self, prompt: str, output_path: Path, duration_seconds: float = 60.0
            ) -> Optional[Path]:
                # Extract scene_id from output_path name
                scene_id = output_path.stem
                ambient_calls.append(scene_id)
                return None

        # Stub _get_audio_duration to return a fixed value
        monkeypatch.setattr(
            "src.audio.audio_orchestrator._get_audio_duration", lambda p: 5.0
        )

        ambient_provider = MockAmbientProvider()
        orch = AudioOrchestrator(
            provider, output_dir=tmp_path,
            feature_flags=FeatureFlags(ambient_enabled=True),
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
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(beats, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # No ambient_client passed (default None)
        orch = AudioOrchestrator(provider, output_dir=tmp_path, feature_flags=FeatureFlags(ambient_enabled=True))

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"},
        )

        # Assert — chapter produced, no ambient directory
        assert result.exists()


class TestAmbientWiringProviderReturnsNone:
    """When the AmbientProvider returns None, that scene is skipped gracefully."""

    def test_none_ambient_does_not_trigger_mixing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the AmbientProvider returns None for all scenes, no mixing occurs."""
        # Arrange
        scene = Scene(
            scene_id="cave",
            environment="cave",
            ambient_prompt="dripping water",
            ambient_volume=-18.0,
        )
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(beats, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # Create mock ambient provider that returns None (API failure)
        from src.audio.ambient.ambient_provider import AmbientProvider

        class FailingAmbientProvider(AmbientProvider):
            @property
            def name(self) -> str:
                return "mock"

            def provide(self, scene: Any, book_id: str) -> float:
                return 0.0

            def _generate(
                self, prompt: str, output_path: Path, duration_seconds: float = 60.0
            ) -> Optional[Path]:
                return None

        monkeypatch.setattr(
            "src.audio.audio_orchestrator._get_audio_duration", lambda p: 5.0
        )

        ambient_provider = FailingAmbientProvider()
        orch = AudioOrchestrator(
            provider, output_dir=tmp_path,
            feature_flags=FeatureFlags(ambient_enabled=True),
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
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="cave",
            ),
        ]
        scene_reg = SceneRegistry()
        scene_reg.upsert(scene)
        book = _make_book_with_scene_registry(beats, scene_reg)

        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        # Create mock ambient provider that returns a fake file
        from src.audio.ambient.ambient_provider import AmbientProvider

        class WorkingAmbientProvider(AmbientProvider):
            @property
            def name(self) -> str:
                return "mock"

            def provide(self, scene: Any, book_id: str) -> float:
                return 0.0

            def _generate(
                self, prompt: str, output_path: Path, duration_seconds: float = 60.0
            ) -> Optional[Path]:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"\xff" * 100)
                return output_path

        monkeypatch.setattr(
            "src.audio.audio_orchestrator._get_audio_duration", lambda p: 5.0
        )

        # Track _mix_ambient_into_speech calls
        mix_calls: list[tuple[Path, list[tuple[Path, float, float, float]]]] = []

        def _fake_mix(
            self: AudioOrchestrator,
            speech_path: Path,
            ambient_entries: list[tuple[Path, float, float, float]],
        ) -> None:
            mix_calls.append((speech_path, ambient_entries))

        monkeypatch.setattr(AudioOrchestrator, "_mix_ambient_into_speech", _fake_mix)

        ambient_provider = WorkingAmbientProvider()
        orch = AudioOrchestrator(
            provider, output_dir=tmp_path,
            feature_flags=FeatureFlags(ambient_enabled=True),
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




class TestFeatureFlagsInjection:
    """AudioOrchestrator accepts FeatureFlags instance and uses its values."""

    def test_orchestrator_accepts_feature_flags_parameter(self, tmp_path: Path) -> None:
        """Constructor accepts a FeatureFlags instance without error."""
        # Arrange
        provider = MagicMock()
        flags = FeatureFlags(
            ambient_enabled=False,
            sound_effects_enabled=False,
        )

        # Act
        orch = AudioOrchestrator(provider, output_dir=tmp_path, feature_flags=flags)

        # Assert — orchestrator stores the flags instance
        assert orch._feature_flags == flags

    def test_orchestrator_defaults_to_all_flags_enabled(self, tmp_path: Path) -> None:
        """When feature_flags is not provided, all features are enabled by default."""
        # Arrange
        provider = MagicMock()

        # Act
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

        # Assert — all feature flags are True by default
        assert orch._feature_flags.ambient_enabled is True
        assert orch._feature_flags.sound_effects_enabled is True


# ── Sound Effects Synthesis (US-023 SOUND_EFFECT beats) ───────────────────

class TestSoundEffectBeatSynthesis:
    """Tests for SOUND_EFFECT beat synthesis (US-023 refactor)."""

    def test_sound_effect_beat_synthesized_when_provider_available(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SOUND_EFFECT beats are synthesized via sound_effect_provider when available."""
        # Arrange
        beats = [
            Beat(
                text="She coughed.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
            ),
            Beat(
                text="dry cough",
                beat_type=BeatType.SOUND_EFFECT,
                sound_effect_detail="harsh, dry cough from a middle-aged woman",
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize

        sound_effect_provider = MagicMock()
        sound_effect_provider._generate.return_value = tmp_path / "sfx_dry_cough.mp3"
        # Create the file so ffmpeg doesn't fail
        sound_effect_provider._generate.return_value.touch()

        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = AudioOrchestrator(
            provider,
            output_dir=tmp_path,
            sound_effect_provider=sound_effect_provider,

        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"}
        )

        # Assert
        assert result.exists()
        # Sound effect provider should have been called
        sound_effect_provider._generate.assert_called_once()
        args = sound_effect_provider._generate.call_args[0]
        assert args[0] == "harsh, dry cough from a middle-aged woman"

    def test_sound_effect_beat_fallback_to_text_when_no_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SOUND_EFFECT beats use text field when sound_effect_detail is None."""
        # Arrange
        beats = [
            Beat(
                text="door knock",
                beat_type=BeatType.SOUND_EFFECT,
                sound_effect_detail=None,
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize

        sound_effect_provider = MagicMock()
        sound_effect_provider._generate.return_value = tmp_path / "sfx_door_knock.mp3"
        sound_effect_provider._generate.return_value.touch()

        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = AudioOrchestrator(
            provider,
            output_dir=tmp_path,
            sound_effect_provider=sound_effect_provider,

        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"}
        )

        # Assert
        assert result.exists()
        # Sound effect provider should have been called with text field
        sound_effect_provider._generate.assert_called_once()
        args = sound_effect_provider._generate.call_args[0]
        assert args[0] == "door knock"


# ── VOCAL_EFFECT beat handling (US-017) ───────────────────────────────────

class TestVocalEffectBeats:
    """VOCAL_EFFECT beats use SoundEffectProvider (same as SOUND_EFFECT)."""

    def test_vocal_effect_beat_does_not_call_tts_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A VOCAL_EFFECT beat must not trigger a TTS synthesize call."""
        # Arrange
        beats = [
            Beat(
                text="soft breath intake",
                beat_type=BeatType.VOCAL_EFFECT,
                character_id="alice",
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize

        sound_effect_provider = MagicMock()
        sound_effect_provider._generate.return_value = None

        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = AudioOrchestrator(
            provider,
            output_dir=tmp_path,
            sound_effect_provider=sound_effect_provider,

        )

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"alice": "v_alice"}
        )

        # Assert — TTS provider must NOT have been called for the vocal effect
        provider.synthesize.assert_not_called()

    def test_vocal_effect_beat_calls_sound_effect_provider_with_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A VOCAL_EFFECT beat is synthesised via SoundEffectProvider using beat.text."""
        # Arrange
        beats = [
            Beat(
                text="quiet nervous laughter",
                beat_type=BeatType.VOCAL_EFFECT,
                character_id="bob",
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize

        sfx_path = tmp_path / "vocal_effect.mp3"
        sfx_path.write_bytes(b"\x00" * 64)
        sound_effect_provider = MagicMock()
        sound_effect_provider._generate.return_value = sfx_path

        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = AudioOrchestrator(
            provider,
            output_dir=tmp_path,
            sound_effect_provider=sound_effect_provider,

        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"bob": "v_bob"}
        )

        # Assert — the chapter file is produced (no crash)
        assert result.exists()
        # TTS provider was not called
        provider.synthesize.assert_not_called()
        # Sound effect provider was called with beat.text as description
        sound_effect_provider._generate.assert_called_once()
        args = sound_effect_provider._generate.call_args[0]
        assert args[0] == "quiet nervous laughter"

    def test_vocal_effect_skipped_when_no_sound_effect_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VOCAL_EFFECT beats are skipped when no SoundEffectProvider is configured."""
        # Arrange
        beats = [
            Beat(
                text="soft breath intake",
                beat_type=BeatType.VOCAL_EFFECT,
                character_id="narrator",
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()

        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)

        orch = AudioOrchestrator(
            provider,
            output_dir=tmp_path,
            sound_effect_provider=None,  # no provider

        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"}
        )

        # Assert — beat skipped, no TTS call
        assert result.exists()
        provider.synthesize.assert_not_called()

    def test_vocal_effect_skipped_when_provider_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When SoundEffectProvider.generate returns None, the beat is skipped."""
        # Arrange
        beats = [
            Beat(
                text="gasping exhale",
                beat_type=BeatType.VOCAL_EFFECT,
                character_id="narrator",
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()

        sound_effect_provider = MagicMock()
        sound_effect_provider._generate.return_value = None  # provider fails

        captured_paths: list[Path] = []

        def _capture_stitch(
            self: AudioOrchestrator,
            beat_paths: list[Path],
            output_path: Path,
            segs: list[Beat] | None = None,
        ) -> None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"\x00" * 128)
            captured_paths.extend(beat_paths)

        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _capture_stitch)

        orch = AudioOrchestrator(
            provider,
            output_dir=tmp_path,
            sound_effect_provider=sound_effect_provider,

        )

        # Act
        result = orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v1"}
        )

        # Assert — no paths (beat skipped when provider returns None)
        assert result.exists()
        assert len(captured_paths) == 0


# ------------------------------------------------------------------
# BOOK_TITLE beat handling
# ------------------------------------------------------------------


class TestBookTitleBeatInSynthesiseTypes:
    """BOOK_TITLE beats must be synthesized by TTS."""

    def test_book_title_is_in_synthesise_types(self) -> None:
        """BeatType.BOOK_TITLE must be present in _SYNTHESISE_TYPES."""
        # Arrange
        from src.audio.audio_orchestrator import _SYNTHESISE_TYPES

        # Act / Assert
        assert BeatType.BOOK_TITLE in _SYNTHESISE_TYPES


class TestBookTitleBeatFlowsThroughTTS:
    """BOOK_TITLE beats flow through normal TTS synthesis (narrator voice)."""

    def test_book_title_beat_calls_tts_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A BOOK_TITLE beat is synthesized via the TTS provider using narrator voice."""
        # Arrange
        beats = [
            Beat(
                text="Pride and Prejudice, by Jane Austen.",
                beat_type=BeatType.BOOK_TITLE,
                character_id="narrator",
            ),
        ]
        book = _make_book_with_beats(beats)
        provider = MagicMock()
        provider.synthesize.side_effect = _fake_synthesize
        monkeypatch.setattr(AudioOrchestrator, "_stitch_with_ffmpeg", _fake_ffmpeg_stitch)
        orch = AudioOrchestrator(provider, output_dir=tmp_path)

        # Act
        orch.synthesize_chapter(
            book, chapter_number=1, voice_assignment={"narrator": "v_narrator"}
        )

        # Assert — TTS provider was called for the book title
        provider.synthesize.assert_called_once()
        call_args = provider.synthesize.call_args
        assert call_args[0][0] == "Pride and Prejudice, by Jane Austen."
        assert call_args[0][1] == "v_narrator"


class TestBookTitleSilenceAfterInConcat:
    """After a BOOK_TITLE beat, SILENCE_AFTER_INTRODUCTION_MS (1500ms) is inserted."""

    def test_book_title_followed_by_narration_uses_1500ms_pause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A BOOK_TITLE → NARRATION boundary must use 1500ms silence."""
        # Arrange
        monkeypatch.setattr(AudioOrchestrator, "_generate_silence_clip", _fake_generate_silence)
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [
            Beat(
                text="Pride and Prejudice, by Jane Austen.",
                beat_type=BeatType.BOOK_TITLE,
                character_id="narrator",
            ),
            Beat(
                text="It is a truth universally acknowledged.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
            ),
        ]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — silence between the two beats is 1500ms (intro pause)
        assert len(entries) == 3
        assert "silence_1500ms" in entries[1].name


# ------------------------------------------------------------------
# CHAPTER_ANNOUNCEMENT — stitching pause constant
# ------------------------------------------------------------------


class TestBuildConcatEntriesChapterAnnouncement:
    """After a CHAPTER_ANNOUNCEMENT beat, 500ms silence is inserted."""

    def test_chapter_announcement_followed_by_narration_uses_500ms_pause(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A CHAPTER_ANNOUNCEMENT → NARRATION boundary must use 500ms silence."""
        # Arrange
        monkeypatch.setattr(AudioOrchestrator, "_generate_silence_clip", _fake_generate_silence)
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [
            Beat(
                text="Chapter One.",
                beat_type=BeatType.CHAPTER_ANNOUNCEMENT,
                character_id="narrator",
            ),
            Beat(
                text="It was a dark and stormy night.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
            ),
        ]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — silence between the two beats is 500ms (announcement pause)
        assert len(entries) == 3
        assert "silence_500ms" in entries[1].name

    def test_narration_after_narration_is_not_affected_by_announcement_constant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Normal narration-to-narration boundary still uses 150ms silence."""
        # Arrange
        monkeypatch.setattr(AudioOrchestrator, "_generate_silence_clip", _fake_generate_silence)
        provider = MagicMock()
        orch = AudioOrchestrator(provider, output_dir=tmp_path)
        beats = [
            Beat(
                text="First narration.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
            ),
            Beat(
                text="Second narration.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
            ),
        ]
        beat_paths = [tmp_path / "beat_0.mp3", tmp_path / "beat_1.mp3"]

        # Act
        entries = orch._build_concat_entries(beat_paths, beats, tmp_path)

        # Assert — normal same-speaker silence applies
        assert "silence_150ms" in entries[1].name


# ------------------------------------------------------------------
# CHAPTER_ANNOUNCEMENT — synthesized by TTS
# ------------------------------------------------------------------


class TestChapterAnnouncementInSynthesiseTypes:
    """CHAPTER_ANNOUNCEMENT beats must be synthesized by TTS."""

    def test_chapter_announcement_is_in_synthesise_types(self) -> None:
        """BeatType.CHAPTER_ANNOUNCEMENT must be present in _SYNTHESISE_TYPES."""
        # Arrange
        from src.audio.audio_orchestrator import _SYNTHESISE_TYPES

        # Act / Assert
        assert BeatType.CHAPTER_ANNOUNCEMENT in _SYNTHESISE_TYPES
