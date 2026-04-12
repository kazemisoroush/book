"""Feature flags for the audiobook generator.

This module provides a centralized feature flag system that allows toggling
all end-to-end features (ambient sound, sound effects, emotion tags, voice
design, scene context) at runtime through constructor parameters.
"""
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class FeatureFlags:
    """Centralized feature flags for the audiobook generator.

    All feature toggles default to True (enabled). Disable specific features
    by passing False values to the constructor or loading from a dict.

    Attributes:
        ambient_enabled: When True, generates ambient background audio per scene.
        sound_effects_enabled: When True, inserts diegetic sound effects into silence gaps.
        emotion_enabled: When True, applies emotion-based voice modifiers to segments.
        voice_design_enabled: When True, calls Voice Design API for characters with descriptions.
        scene_context_enabled: When True, applies scene-based voice modifiers to segments.
    """

    ambient_enabled: bool = True
    sound_effects_enabled: bool = True
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
            data: Dictionary with optional keys: ambient_enabled, sound_effects_enabled,
                  emotion_enabled, voice_design_enabled, scene_context_enabled.

        Returns:
            FeatureFlags instance with values from the dictionary or defaults.
        """
        return cls(
            ambient_enabled=data.get("ambient_enabled", True),
            sound_effects_enabled=data.get("sound_effects_enabled", True),
            emotion_enabled=data.get("emotion_enabled", True),
            voice_design_enabled=data.get("voice_design_enabled", True),
            scene_context_enabled=data.get("scene_context_enabled", True),
        )
