"""Beat domain model and its type enum."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BeatType(Enum):
    """Type of text beat."""
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    ILLUSTRATION = "illustration"
    COPYRIGHT = "copyright"
    OTHER = "other"  # Non-narratable content (page numbers, metadata markers, etc.)
    SOUND_EFFECT = "sound_effect"
    VOCAL_EFFECT = "vocal_effect"  # Non-speech character sounds (breath, cough, sigh, etc.)
    BOOK_TITLE = "book_title_announcement"  # Synthetic book title/author introduction beat
    CHAPTER_ANNOUNCEMENT = "chapter_announcement"  # Spoken chapter header ("Chapter 1. Title.")

    @classmethod
    def from_string(cls, value: str, default: "BeatType | None" = None) -> "BeatType":
        """Convert a string to a BeatType, returning *default* on unknown values.

        If *default* is None, falls back to NARRATION.
        """
        try:
            return cls(value)
        except ValueError:
            return default if default is not None else cls.NARRATION


# Opacity levels for mixing audio layers in the final output.
# Narration and dialogue are full volume (1.0), sound effects are prominent (0.8),
# while ambient/music (when added as separate beat types) will be quieter (0.3/0.5).
OPACITY_BY_BEAT_TYPE: dict[BeatType, float] = {
    BeatType.NARRATION: 1.0,
    BeatType.DIALOGUE: 1.0,
    BeatType.SOUND_EFFECT: 0.8,
    BeatType.VOCAL_EFFECT: 1.0,
    BeatType.BOOK_TITLE: 1.0,
    BeatType.CHAPTER_ANNOUNCEMENT: 1.0,
    BeatType.ILLUSTRATION: 1.0,
    BeatType.COPYRIGHT: 1.0,
    BeatType.OTHER: 1.0,
}


@dataclass
class Beat:
    """A single piece of text (narration or dialogue)."""

    text: str
    beat_type: BeatType
    character_id: Optional[int] = None  # Foreign key into CharacterRegistry
    emotion: Optional[str] = None

    def is_dialogue(self) -> bool:
        """Return True if beat is dialogue."""
        return self.beat_type == BeatType.DIALOGUE

    def is_narration(self) -> bool:
        """Return True if beat is narration."""
        return self.beat_type == BeatType.NARRATION

    def is_illustration(self) -> bool:
        """Return True if beat is an illustration caption."""
        return self.beat_type == BeatType.ILLUSTRATION

    def is_copyright(self) -> bool:
        """Return True if beat is copyright text."""
        return self.beat_type == BeatType.COPYRIGHT

    def is_other(self) -> bool:
        """Return True if beat is OTHER (non-narratable junk)."""
        return self.beat_type == BeatType.OTHER

    def is_chapter_announcement(self) -> bool:
        """Return True if beat is a chapter announcement."""
        return self.beat_type == BeatType.CHAPTER_ANNOUNCEMENT

    @property
    def is_narratable(self) -> bool:
        """True when the beat should be read aloud (dialogue, narration, or chapter announcement)."""
        return self.beat_type in {
            BeatType.DIALOGUE,
            BeatType.NARRATION,
            BeatType.CHAPTER_ANNOUNCEMENT,
            BeatType.BOOK_TITLE,
        }
