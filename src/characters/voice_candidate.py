"""A shortlisted voice offered for a character, before anyone has chosen it."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VoiceCandidate:
    """One voice a character could be cast with.

    ``voice_id`` is the vendor's shared-library id, which TTS cannot use until the
    voice has been added to the workspace, so it is never a ``voice_assignments`` value.
    """

    voice_id: str
    public_owner_id: str
    name: str
    preview_url: str
    gender: Optional[str] = None
    age: Optional[str] = None
    accent: Optional[str] = None

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Return a JSON-serialisable dictionary of all fields."""
        return {
            "voice_id": self.voice_id,
            "public_owner_id": self.public_owner_id,
            "name": self.name,
            "preview_url": self.preview_url,
            "gender": self.gender,
            "age": self.age,
            "accent": self.accent,
        }
