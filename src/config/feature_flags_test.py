"""Tests for FeatureFlags dataclass and methods."""
from src.config.feature_flags import FeatureFlags


class TestFeatureFlagsToDictFromDict:
    """Test serialization and deserialization via to_dict/from_dict."""

    def test_to_dict_returns_all_fields(self) -> None:
        # Arrange
        flags = FeatureFlags(
            ambient_enabled=False,
            sound_effects_enabled=True,
            emotion_enabled=False,
            voice_design_enabled=True,
            scene_context_enabled=False,
            chapter_announcer_enabled=False,
        )

        # Act
        d = flags.to_dict()

        # Assert
        assert d == {
            "ambient_enabled": False,
            "sound_effects_enabled": True,
            "emotion_enabled": False,
            "voice_design_enabled": True,
            "scene_context_enabled": False,
            "chapter_announcer_enabled": False,
        }

    def test_from_dict_with_all_values(self) -> None:
        # Arrange
        d: dict[str, bool] = {
            "ambient_enabled": False,
            "sound_effects_enabled": True,
            "emotion_enabled": False,
            "voice_design_enabled": False,
            "scene_context_enabled": True,
        }

        # Act
        flags = FeatureFlags.from_dict(d)

        # Assert
        assert flags.ambient_enabled is False
        assert flags.sound_effects_enabled is True
        assert flags.emotion_enabled is False
        assert flags.voice_design_enabled is False
        assert flags.scene_context_enabled is True

    def test_from_dict_with_partial_values_defaults_rest(self) -> None:
        # Arrange
        d: dict[str, bool] = {"ambient_enabled": False, "emotion_enabled": False}

        # Act
        flags = FeatureFlags.from_dict(d)

        # Assert
        assert flags.ambient_enabled is False
        assert flags.emotion_enabled is False
        assert flags.sound_effects_enabled is True
        assert flags.voice_design_enabled is True
        assert flags.scene_context_enabled is True

    def test_from_dict_with_empty_dict_uses_defaults(self) -> None:
        # Arrange
        d: dict[str, bool] = {}

        # Act
        flags = FeatureFlags.from_dict(d)

        # Assert
        assert flags.ambient_enabled is True
        assert flags.sound_effects_enabled is True
        assert flags.emotion_enabled is True
        assert flags.voice_design_enabled is True
        assert flags.scene_context_enabled is True

    def test_to_dict_from_dict_round_trip(self) -> None:
        # Arrange
        original = FeatureFlags(
            ambient_enabled=False,
            sound_effects_enabled=True,
            emotion_enabled=False,
            voice_design_enabled=True,
            scene_context_enabled=False,
        )

        # Act
        d = original.to_dict()
        restored = FeatureFlags.from_dict(d)

        # Assert
        assert restored.ambient_enabled == original.ambient_enabled
        assert restored.sound_effects_enabled == original.sound_effects_enabled
        assert restored.emotion_enabled == original.emotion_enabled
        assert restored.voice_design_enabled == original.voice_design_enabled
        assert restored.scene_context_enabled == original.scene_context_enabled


class TestNewFeatureFlags:
    """Tests for chapter_announcer_enabled flag."""

    def test_chapter_announcer_enabled_defaults_to_true(self) -> None:
        """chapter_announcer_enabled defaults to True — the feature is on by default."""
        # Arrange / Act
        flags = FeatureFlags()

        # Assert
        assert flags.chapter_announcer_enabled is True

    def test_chapter_announcer_enabled_can_be_disabled(self) -> None:
        """chapter_announcer_enabled can be explicitly disabled."""
        # Arrange / Act
        flags = FeatureFlags(chapter_announcer_enabled=False)

        # Assert
        assert flags.chapter_announcer_enabled is False

    def test_from_dict_reads_chapter_announcer_enabled(self) -> None:
        """from_dict correctly reads chapter_announcer_enabled from dict."""
        # Arrange
        d = {"chapter_announcer_enabled": False}

        # Act
        flags = FeatureFlags.from_dict(d)

        # Assert
        assert flags.chapter_announcer_enabled is False

    def test_to_dict_includes_chapter_announcer_enabled(self) -> None:
        """to_dict includes chapter_announcer_enabled in the serialized output."""
        # Arrange
        flags = FeatureFlags(chapter_announcer_enabled=False)

        # Act
        d = flags.to_dict()

        # Assert
        assert "chapter_announcer_enabled" in d
        assert d["chapter_announcer_enabled"] is False
