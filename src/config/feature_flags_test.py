"""Tests for FeatureFlags dataclass and methods."""
import json
import tempfile
from pathlib import Path

import pytest

from src.config.feature_flags import FeatureFlags


class TestFeatureFlagsToDictFromDict:
    """Test serialization and deserialization via to_dict/from_dict."""

    def test_to_dict_returns_all_fields(self) -> None:
        # Arrange
        flags = FeatureFlags(
            ambient_enabled=False,
            cinematic_sound_effects_enabled=True,
            emotion_enabled=False,
            voice_design_enabled=True,
            scene_context_enabled=False,
        )

        # Act
        d = flags.to_dict()

        # Assert
        assert d == {
            "ambient_enabled": False,
            "cinematic_sound_effects_enabled": True,
            "emotion_enabled": False,
            "voice_design_enabled": True,
            "scene_context_enabled": False,
        }

    def test_from_dict_with_all_values(self) -> None:
        # Arrange
        d: dict[str, bool] = {
            "ambient_enabled": False,
            "cinematic_sound_effects_enabled": True,
            "emotion_enabled": False,
            "voice_design_enabled": False,
            "scene_context_enabled": True,
        }

        # Act
        flags = FeatureFlags.from_dict(d)

        # Assert
        assert flags.ambient_enabled is False
        assert flags.cinematic_sound_effects_enabled is True
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
        assert flags.cinematic_sound_effects_enabled is True
        assert flags.voice_design_enabled is True
        assert flags.scene_context_enabled is True

    def test_from_dict_with_empty_dict_uses_defaults(self) -> None:
        # Arrange
        d: dict[str, bool] = {}

        # Act
        flags = FeatureFlags.from_dict(d)

        # Assert
        assert flags.ambient_enabled is True
        assert flags.cinematic_sound_effects_enabled is True
        assert flags.emotion_enabled is True
        assert flags.voice_design_enabled is True
        assert flags.scene_context_enabled is True

    def test_to_dict_from_dict_round_trip(self) -> None:
        # Arrange
        original = FeatureFlags(
            ambient_enabled=False,
            cinematic_sound_effects_enabled=True,
            emotion_enabled=False,
            voice_design_enabled=True,
            scene_context_enabled=False,
        )

        # Act
        d = original.to_dict()
        restored = FeatureFlags.from_dict(d)

        # Assert
        assert restored.ambient_enabled == original.ambient_enabled
        assert restored.cinematic_sound_effects_enabled == original.cinematic_sound_effects_enabled
        assert restored.emotion_enabled == original.emotion_enabled
        assert restored.voice_design_enabled == original.voice_design_enabled
        assert restored.scene_context_enabled == original.scene_context_enabled


class TestFeatureFlagsYamlLoading:
    """Test loading from YAML files."""

    def test_from_yaml_with_all_values(self) -> None:
        # Arrange
        yaml_content = """
features:
  ambient_enabled: false
  cinematic_sound_effects_enabled: true
  emotion_enabled: false
  voice_design_enabled: true
  scene_context_enabled: false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Act
            flags = FeatureFlags.from_yaml(yaml_path)

            # Assert
            assert flags.ambient_enabled is False
            assert flags.cinematic_sound_effects_enabled is True
            assert flags.emotion_enabled is False
            assert flags.voice_design_enabled is True
            assert flags.scene_context_enabled is False
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_from_yaml_with_partial_values(self) -> None:
        # Arrange
        yaml_content = """
features:
  ambient_enabled: false
  emotion_enabled: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Act
            flags = FeatureFlags.from_yaml(yaml_path)

            # Assert
            assert flags.ambient_enabled is False
            assert flags.emotion_enabled is True
            assert flags.cinematic_sound_effects_enabled is True
            assert flags.voice_design_enabled is True
            assert flags.scene_context_enabled is True
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_from_yaml_with_empty_features_dict(self) -> None:
        # Arrange
        yaml_content = "features: {}"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Act
            flags = FeatureFlags.from_yaml(yaml_path)

            # Assert
            assert flags.ambient_enabled is True
            assert flags.cinematic_sound_effects_enabled is True
            assert flags.emotion_enabled is True
            assert flags.voice_design_enabled is True
            assert flags.scene_context_enabled is True
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_from_yaml_file_not_found_raises_error(self) -> None:
        # Arrange
        yaml_path = "/nonexistent/path/to/file.yaml"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            FeatureFlags.from_yaml(yaml_path)


class TestFeatureFlagsJsonLoading:
    """Test loading from JSON files."""

    def test_from_json_with_all_values(self) -> None:
        # Arrange
        json_content = json.dumps({
            "features": {
                "ambient_enabled": False,
                "cinematic_sound_effects_enabled": True,
                "emotion_enabled": False,
                "voice_design_enabled": True,
                "scene_context_enabled": False,
            }
        })
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json_content)
            json_path = f.name

        try:
            # Act
            flags = FeatureFlags.from_json(json_path)

            # Assert
            assert flags.ambient_enabled is False
            assert flags.cinematic_sound_effects_enabled is True
            assert flags.emotion_enabled is False
            assert flags.voice_design_enabled is True
            assert flags.scene_context_enabled is False
        finally:
            Path(json_path).unlink(missing_ok=True)

    def test_from_json_with_partial_values(self) -> None:
        # Arrange
        json_content = json.dumps({
            "features": {
                "ambient_enabled": False,
                "emotion_enabled": True,
            }
        })
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json_content)
            json_path = f.name

        try:
            # Act
            flags = FeatureFlags.from_json(json_path)

            # Assert
            assert flags.ambient_enabled is False
            assert flags.emotion_enabled is True
            assert flags.cinematic_sound_effects_enabled is True
            assert flags.voice_design_enabled is True
            assert flags.scene_context_enabled is True
        finally:
            Path(json_path).unlink(missing_ok=True)

    def test_from_json_with_empty_features_dict(self) -> None:
        # Arrange
        json_content = json.dumps({"features": {}})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json_content)
            json_path = f.name

        try:
            # Act
            flags = FeatureFlags.from_json(json_path)

            # Assert
            assert flags.ambient_enabled is True
            assert flags.cinematic_sound_effects_enabled is True
            assert flags.emotion_enabled is True
            assert flags.voice_design_enabled is True
            assert flags.scene_context_enabled is True
        finally:
            Path(json_path).unlink(missing_ok=True)

    def test_from_json_file_not_found_raises_error(self) -> None:
        # Arrange
        json_path = "/nonexistent/path/to/file.json"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            FeatureFlags.from_json(json_path)

    def test_from_json_invalid_json_raises_error(self) -> None:
        # Arrange
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json")
            json_path = f.name

        try:
            # Act & Assert
            with pytest.raises(json.JSONDecodeError):
                FeatureFlags.from_json(json_path)
        finally:
            Path(json_path).unlink(missing_ok=True)


class TestFeatureFlagsYamlJsonEquivalence:
    """Test that YAML and JSON files produce identical FeatureFlags."""

    def test_yaml_and_json_with_same_values_are_equivalent(self) -> None:
        # Arrange
        yaml_content = """
features:
  ambient_enabled: false
  cinematic_sound_effects_enabled: true
  emotion_enabled: false
  voice_design_enabled: true
  scene_context_enabled: false
"""
        json_content = json.dumps({
            "features": {
                "ambient_enabled": False,
                "cinematic_sound_effects_enabled": True,
                "emotion_enabled": False,
                "voice_design_enabled": True,
                "scene_context_enabled": False,
            }
        })

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json_content)
            json_path = f.name

        try:
            # Act
            yaml_flags = FeatureFlags.from_yaml(yaml_path)
            json_flags = FeatureFlags.from_json(json_path)

            # Assert
            assert yaml_flags.ambient_enabled == json_flags.ambient_enabled
            assert yaml_flags.cinematic_sound_effects_enabled == json_flags.cinematic_sound_effects_enabled
            assert yaml_flags.emotion_enabled == json_flags.emotion_enabled
            assert yaml_flags.voice_design_enabled == json_flags.voice_design_enabled
            assert yaml_flags.scene_context_enabled == json_flags.scene_context_enabled
        finally:
            Path(yaml_path).unlink(missing_ok=True)
            Path(json_path).unlink(missing_ok=True)
