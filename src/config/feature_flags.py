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
    by passing False values to the constructor.

    Attributes:
        ambient_enabled: When True, generates ambient background audio per scene.
            Post-processing flag checked in the TTS layer.
        sound_effects_enabled: When True, LLM emits SOUND_EFFECT/VOCAL_EFFECT segments.
            Prompt-level flag checked in PromptBuilder.
        emotion_enabled: When True, LLM emits emotion tags and voice modifiers.
            Prompt-level flag checked in PromptBuilder.
        voice_design_enabled: When True, LLM emits voice_stability/style/speed settings.
            Prompt-level flag checked in PromptBuilder.
        scene_context_enabled: When True, LLM emits scene detection and voice modifiers.
            Prompt-level flag checked in PromptBuilder.
        chapter_announcer_enabled: When True, LLM emits CHAPTER_ANNOUNCEMENT segments.
            Prompt-level flag checked in PromptBuilder.
    """

    ambient_enabled: bool = True
    sound_effects_enabled: bool = True
    emotion_enabled: bool = True
    voice_design_enabled: bool = True
    scene_context_enabled: bool = True
    chapter_announcer_enabled: bool = True

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
            chapter_announcer_enabled=data.get("chapter_announcer_enabled", True),
        )

