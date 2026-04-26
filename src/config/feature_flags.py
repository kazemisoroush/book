"""Feature flags for the audiobook generator.

Feature flags are **hardcoded** in this file — they are not configurable from
CLI, environment variables, or config files. To try the pipeline without a
feature, edit the defaults below.

Each flag gates **deterministic** code behaviour (audio post-processing,
synthetic section injection). Flags must not influence prompt text sent to the
LLM — prompt composition belongs to ``src/parsers/prompts/`` and is a single
static source of truth shared with promptfoo evals.

If a flag ever needs to become user-configurable, graduate it into
``src/config/config.py`` as a proper config value.
"""
from dataclasses import dataclass


@dataclass
class FeatureFlags:
    """Hardcoded feature toggles for deterministic pipeline behaviour.

    Attributes:
        ambient_enabled: When True, ambient background audio is generated
            per scene and mixed under speech by :class:`AudioAssembler`.
        sound_effects_enabled: When True, SOUND_EFFECT and VOCAL_EFFECT
            beats are rendered into the chapter audio.
        chapter_announcer_enabled: When True, synthetic
            ``CHAPTER_ANNOUNCEMENT`` (and first-chapter ``BOOK_TITLE``)
            sections are injected into each chapter by the AI workflow.
    """

    ambient_enabled: bool = True
    sound_effects_enabled: bool = True
    chapter_announcer_enabled: bool = True
