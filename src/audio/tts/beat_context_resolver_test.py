"""Tests for BeatContextResolver: text continuity and request ID windows."""
from src.audio.tts.beat_context_resolver import BeatContextResolver
from src.domain.beat import Beat, BeatType


class TestSameCharacterTextContext:
    """Resolver provides previous_text/next_text from same-character beats."""

    def test_middle_beat_gets_prev_and_next_from_same_character(self) -> None:
        """Three narrator beats: the middle one gets text from the other two."""
        # Arrange
        beats = [
            Beat(text="First.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Second.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Third.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        resolver = BeatContextResolver(beats)

        # Act
        ctx = resolver.resolve(1)

        # Assert
        assert ctx.previous_text == "First."
        assert ctx.next_text == "Third."

    def test_first_beat_has_no_previous(self) -> None:
        """The first beat for a character has previous_text=None."""
        # Arrange
        beats = [
            Beat(text="Hello.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="World.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        resolver = BeatContextResolver(beats)

        # Act
        ctx = resolver.resolve(0)

        # Assert
        assert ctx.previous_text is None
        assert ctx.next_text == "World."

    def test_context_skips_other_characters(self) -> None:
        """A character's context comes only from its own beats, not others'."""
        # Arrange
        beats = [
            Beat(text="Narration.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Alice line.", beat_type=BeatType.DIALOGUE, character_id="alice"),
            Beat(text="More narration.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Alice again.", beat_type=BeatType.DIALOGUE, character_id="alice"),
        ]
        resolver = BeatContextResolver(beats)

        # Act -- alice's second line (index 3)
        ctx = resolver.resolve(3)

        # Assert
        assert ctx.previous_text == "Alice line."
        assert ctx.next_text is None


class TestRequestIdWindow:
    """Resolver maintains per-voice sliding windows of request IDs."""

    def test_first_beat_has_no_previous_request_ids(self) -> None:
        """Before any synthesis, previous_request_ids is None."""
        # Arrange
        beats = [
            Beat(text="Hello.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        resolver = BeatContextResolver(beats)

        # Act
        ctx = resolver.resolve(0)

        # Assert
        assert ctx.previous_request_ids is None

    def test_recording_request_id_makes_it_available_to_next_same_voice(self) -> None:
        """After recording a request ID for voice v1, the next v1 beat sees it."""
        # Arrange
        beats = [
            Beat(text="First.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Second.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        resolver = BeatContextResolver(beats)

        # Act
        resolver.resolve(0, voice_id="v1")  # no previous IDs
        resolver.record_request_id("v1", "req-001")
        ctx = resolver.resolve(1, voice_id="v1")

        # Assert
        assert ctx.previous_request_ids == ["req-001"]

    def test_window_limited_to_3_ids(self) -> None:
        """After 4+ recordings, only the last 3 are kept."""
        # Arrange
        beats = [
            Beat(text=f"Seg {i}.", beat_type=BeatType.NARRATION, character_id="narrator")
            for i in range(5)
        ]
        resolver = BeatContextResolver(beats)

        # Act -- record 4 IDs then resolve the 5th
        for i in range(4):
            resolver.resolve(i, voice_id="v1")
            resolver.record_request_id("v1", f"req-{i:03d}")
        ctx = resolver.resolve(4, voice_id="v1")

        # Assert
        assert ctx.previous_request_ids is not None
        assert len(ctx.previous_request_ids) == 3

    def test_different_voices_have_independent_windows(self) -> None:
        """Request IDs for voice v1 don't bleed into voice v2."""
        # Arrange
        beats = [
            Beat(text="Narr.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Alice.", beat_type=BeatType.DIALOGUE, character_id="alice"),
            Beat(text="Narr 2.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        resolver = BeatContextResolver(beats)

        # Act
        resolver.resolve(0, voice_id="v1")
        resolver.record_request_id("v1", "req-narr-1")
        resolver.resolve(1, voice_id="v2")
        resolver.record_request_id("v2", "req-alice-1")
        ctx = resolver.resolve(2, voice_id="v1")

        # Assert -- narrator (v1) should only see v1 IDs
        assert ctx.previous_request_ids == ["req-narr-1"]

    def test_none_request_id_not_recorded(self) -> None:
        """Recording None does not add to the window."""
        # Arrange
        beats = [
            Beat(text="First.", beat_type=BeatType.NARRATION, character_id="narrator"),
            Beat(text="Second.", beat_type=BeatType.NARRATION, character_id="narrator"),
        ]
        resolver = BeatContextResolver(beats)

        # Act
        resolver.resolve(0, voice_id="v1")
        resolver.record_request_id("v1", None)
        ctx = resolver.resolve(1, voice_id="v1")

        # Assert
        assert ctx.previous_request_ids is None


