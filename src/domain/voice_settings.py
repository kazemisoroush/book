"""VoiceSettings domain value object for per-beat TTS synthesis dials."""
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceSettings:
    """Per-beat TTS synthesis dials, currently mapping 1-to-1 onto ElevenLabs voice_settings."""

    stability: float
    style: float
    similarity_boost: float
    use_speaker_boost: bool
