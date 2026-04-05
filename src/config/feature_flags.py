"""Feature flags for the audiobook generator.

This module provides a centralized feature flag system that allows toggling
all end-to-end features (ambient sound, cinematic SFX, emotion tags, voice
design, scene context) at runtime through constructor parameters or config files.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FeatureFlags:
    """Centralized feature flags for the audiobook generator.

    All feature toggles default to True (enabled). Disable specific features
    by passing False values to the constructor or loading from a config file.

    Attributes:
        ambient_enabled: When True, generates ambient background audio per scene.
        cinematic_sfx_enabled: When True, inserts diegetic sound effects into silence gaps.
        emotion_enabled: When True, applies emotion-based voice modifiers to segments.
        voice_design_enabled: When True, calls Voice Design API for characters with descriptions.
        scene_context_enabled: When True, applies scene-based voice modifiers to segments.
    """

    ambient_enabled: bool = True
    cinematic_sfx_enabled: bool = True
    emotion_enabled: bool = True
    voice_design_enabled: bool = True
    scene_context_enabled: bool = True

    def to_dict(self) -> dict[str, bool]:
        """Serialize feature flags to a dictionary.

        Returns:
            Dictionary mapping feature names to boolean values.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureFlags":
        """Deserialize feature flags from a dictionary.

        Missing keys default to True (enabled). Unknown keys are ignored.

        Args:
            data: Dictionary with optional keys: ambient_enabled, cinematic_sfx_enabled,
                  emotion_enabled, voice_design_enabled, scene_context_enabled.

        Returns:
            FeatureFlags instance with values from the dictionary or defaults.
        """
        return cls(
            ambient_enabled=data.get("ambient_enabled", True),
            cinematic_sfx_enabled=data.get("cinematic_sfx_enabled", True),
            emotion_enabled=data.get("emotion_enabled", True),
            voice_design_enabled=data.get("voice_design_enabled", True),
            scene_context_enabled=data.get("scene_context_enabled", True),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "FeatureFlags":
        """Load feature flags from a YAML file.

        The YAML file should have a "features" key containing a dict of feature flags:

        Example:
            features:
              ambient_enabled: false
              emotion_enabled: true

        Args:
            path: Path to the YAML file (relative or absolute).

        Returns:
            FeatureFlags instance with values from the YAML file or defaults.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Feature flags YAML file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Handle empty or None files
        if data is None:
            data = {}

        # Extract "features" key if present, otherwise use entire data as features dict
        features_dict = data.get("features", {})
        if features_dict is None:
            features_dict = {}

        return cls.from_dict(features_dict)

    @classmethod
    def from_json(cls, path: str) -> "FeatureFlags":
        """Load feature flags from a JSON file.

        The JSON file should have a "features" key containing an object of feature flags:

        Example:
            {
              "features": {
                "ambient_enabled": false,
                "emotion_enabled": true
              }
            }

        Args:
            path: Path to the JSON file (relative or absolute).

        Returns:
            FeatureFlags instance with values from the JSON file or defaults.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Feature flags JSON file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract "features" key if present, otherwise use entire data as features dict
        features_dict = data.get("features", {})
        if features_dict is None:
            features_dict = {}

        return cls.from_dict(features_dict)
