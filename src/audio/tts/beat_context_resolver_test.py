"""Tests for BeatContextResolver -- context resolution for TTS beats.

Verifies that the resolver correctly computes per-beat context:
  - Same-character previous/next text for prosody continuity
  - Per-voice request ID sliding windows for acoustic continuity
  - SceneRegistry-based per-beat scene lookup with voice modifiers
"""
import pytest

from src.audio.tts.beat_context_resolver import BeatContextResolver
from src.domain.models import Beat, BeatType, Scene, SceneRegistry


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


class TestSceneRegistryLookup:
    """Resolver looks up scene from SceneRegistry via beat.scene_id."""

    def test_beat_with_scene_id_gets_scene_modifiers(self) -> None:
        """A beat whose scene_id matches a registry entry gets that scene's modifiers."""
        # Arrange
        scene_reg = SceneRegistry()
        cave = Scene(
            scene_id="scene_cave", environment="cave",
            acoustic_hints=["echo"],
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        )
        scene_reg.upsert(cave)

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
        resolver = BeatContextResolver(beats, scene_registry=scene_reg)

        # Act
        ctx = resolver.resolve(0)

        # Assert -- cave modifiers applied: 0.50 + (-0.05) = 0.45, speed = 0.90
        assert ctx.voice_stability == pytest.approx(0.45)
        assert ctx.voice_style == pytest.approx(0.20)
        assert ctx.voice_speed == pytest.approx(0.90)

    def test_beat_with_no_scene_id_gets_no_modifiers(self) -> None:
        """A beat with scene_id=None gets no scene modifiers even when registry has scenes."""
        # Arrange
        scene_reg = SceneRegistry()
        cave = Scene(
            scene_id="scene_cave", environment="cave",
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        )
        scene_reg.upsert(cave)

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
        resolver = BeatContextResolver(beats, scene_registry=scene_reg)

        # Act
        ctx = resolver.resolve(0)

        # Assert -- no modifiers applied
        assert ctx.voice_stability == pytest.approx(0.65)
        assert ctx.voice_style == pytest.approx(0.05)
        assert ctx.voice_speed == pytest.approx(1.0)

    def test_different_beats_can_have_different_scenes(self) -> None:
        """Two beats with different scene_ids get different modifiers."""
        # Arrange
        scene_reg = SceneRegistry()
        cave = Scene(
            scene_id="scene_cave", environment="cave",
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        )
        battle = Scene(
            scene_id="scene_battle", environment="battlefield",
            voice_modifiers={"stability_delta": -0.10, "style_delta": 0.15, "speed": 1.10},
        )
        scene_reg.upsert(cave)
        scene_reg.upsert(battle)

        beats = [
            Beat(
                text="In the cave.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="scene_cave",
                voice_stability=0.50,
                voice_style=0.20,
                voice_speed=1.0,
            ),
            Beat(
                text="On the field!",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="scene_battle",
                voice_stability=0.50,
                voice_style=0.20,
                voice_speed=1.0,
            ),
        ]
        resolver = BeatContextResolver(beats, scene_registry=scene_reg)

        # Act
        ctx_cave = resolver.resolve(0)
        ctx_battle = resolver.resolve(1)

        # Assert -- different modifiers
        assert ctx_cave.voice_stability == pytest.approx(0.45)   # 0.50 - 0.05
        assert ctx_cave.voice_speed == pytest.approx(0.90)
        assert ctx_battle.voice_stability == pytest.approx(0.40)  # 0.50 - 0.10
        assert ctx_battle.voice_speed == pytest.approx(1.10)

    def test_scene_id_not_in_registry_applies_no_modifiers(self) -> None:
        """A beat with a scene_id not found in the registry gets no modifiers."""
        # Arrange
        scene_reg = SceneRegistry()
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="nonexistent",
                voice_stability=0.65,
                voice_style=0.05,
                voice_speed=1.0,
            ),
        ]
        resolver = BeatContextResolver(beats, scene_registry=scene_reg)

        # Act
        ctx = resolver.resolve(0)

        # Assert
        assert ctx.voice_stability == pytest.approx(0.65)
        assert ctx.voice_style == pytest.approx(0.05)
        assert ctx.voice_speed == pytest.approx(1.0)

    def test_empty_voice_modifiers_applies_no_change(self) -> None:
        """Scene with empty voice_modifiers dict passes settings through unchanged."""
        # Arrange
        scene_reg = SceneRegistry()
        spaceship = Scene(
            scene_id="scene_spaceship",
            environment="spaceship",
            acoustic_hints=["humming"],
            voice_modifiers={},
        )
        scene_reg.upsert(spaceship)

        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="scene_spaceship",
                voice_stability=0.65,
                voice_style=0.05,
                voice_speed=1.0,
            ),
        ]
        resolver = BeatContextResolver(beats, scene_registry=scene_reg)

        # Act
        ctx = resolver.resolve(0)

        # Assert -- no change
        assert ctx.voice_stability == pytest.approx(0.65)
        assert ctx.voice_style == pytest.approx(0.05)
        assert ctx.voice_speed == pytest.approx(1.0)

    def test_none_voice_settings_not_modified_by_scene(self) -> None:
        """When beat has no voice settings (all None), scene doesn't add defaults."""
        # Arrange
        scene_reg = SceneRegistry()
        cave = Scene(
            scene_id="scene_cave",
            environment="cave",
            acoustic_hints=["echo"],
            voice_modifiers={"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90},
        )
        scene_reg.upsert(cave)

        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                scene_id="scene_cave",
            ),
        ]
        resolver = BeatContextResolver(beats, scene_registry=scene_reg)

        # Act
        ctx = resolver.resolve(0)

        # Assert
        assert ctx.voice_stability is None
        assert ctx.voice_style is None
        assert ctx.voice_speed is None

    def test_voice_settings_clamped_to_valid_range(self) -> None:
        """Scene modifiers don't push stability/style below 0.0 or above 1.0."""
        # Arrange
        scene_reg = SceneRegistry()
        battle = Scene(
            scene_id="scene_battle",
            environment="battlefield",
            acoustic_hints=["loud"],
            voice_modifiers={"stability_delta": -0.10, "style_delta": 0.15, "speed": 1.10},
        )
        scene_reg.upsert(battle)

        beats = [
            Beat(
                text="Charge!",
                beat_type=BeatType.DIALOGUE,
                character_id="captain",
                scene_id="scene_battle",
                voice_stability=0.05,  # 0.05 + (-0.10) would be -0.05
                voice_style=0.95,  # 0.95 + 0.15 would be 1.10
                voice_speed=1.0,
            ),
        ]
        resolver = BeatContextResolver(beats, scene_registry=scene_reg)

        # Act
        ctx = resolver.resolve(0)

        # Assert -- clamped
        assert ctx.voice_stability == pytest.approx(0.0)
        assert ctx.voice_style == pytest.approx(1.0)

    def test_no_registry_returns_original_voice_settings(self) -> None:
        """When no scene_registry is provided, voice settings pass through unchanged."""
        # Arrange
        beats = [
            Beat(
                text="Hello.",
                beat_type=BeatType.NARRATION,
                character_id="narrator",
                voice_stability=0.50,
                voice_style=0.20,
                voice_speed=1.0,
            ),
        ]
        resolver = BeatContextResolver(beats)

        # Act
        ctx = resolver.resolve(0)

        # Assert
        assert ctx.voice_stability == 0.50
        assert ctx.voice_style == 0.20
        assert ctx.voice_speed == 1.0
