"""Deterministic voice assignment for characters in a book.

Assigns ElevenLabs voices to characters based on their ``sex`` and ``age``
fields.  The narrator always receives the first voice.  Remaining characters
are matched by (sex, age) labels in a stable, deterministic order — no random.

## Assignment algorithm

1. Reserve the first voice in the pool for the narrator.
2. For each non-narrator character (in registry order, i.e. insertion order):
   a. Collect all voices not yet assigned.
   b. From those, prefer voices whose ``labels`` match the character's
      ``sex`` and ``age`` (both must match when both are supplied; a single
      match is preferred over no match).
   c. If no unassigned matching voice exists, fall through to any unassigned
      voice; if all voices are exhausted, cycle through the pool again.
3. Return a ``dict[character_id, voice_id]`` covering every character.

The algorithm is deterministic: given the same voice list and registry the
output is always identical.
"""
from dataclasses import dataclass, field

import structlog

from src.domain.models import CharacterRegistry

logger = structlog.get_logger(__name__)


@dataclass
class VoiceEntry:
    """A single voice available in ElevenLabs.

    ``labels`` mirrors the ``labels`` field on the ElevenLabs ``Voice``
    object (a ``dict[str, str]`` that typically contains ``"gender"`` and
    ``"age"`` keys).
    """

    voice_id: str
    name: str
    labels: dict[str, str] = field(default_factory=dict)


def _sex_to_gender_label(sex: str | None) -> str | None:
    """Map a Character ``sex`` value to an ElevenLabs label gender string.

    Character ``sex`` values are free-form strings from the AI parser (e.g.
    ``"male"``, ``"female"``, ``"M"``, ``"F"``).  ElevenLabs labels use
    ``"male"`` / ``"female"``.
    """
    if sex is None:
        return None
    s = sex.lower()
    if s in ("male", "m"):
        return "male"
    if s in ("female", "f"):
        return "female"
    return None


def _age_to_age_label(age: str | None) -> str | None:
    """Map a Character ``age`` value to an ElevenLabs label age string.

    ElevenLabs voices use labels like ``"young"``, ``"middle_aged"``,
    ``"old"``.  Character ``age`` values come from the AI parser.
    """
    if age is None:
        return None
    a = age.lower().replace(" ", "_").replace("-", "_")
    # Direct matches
    if a in ("young", "middle_aged", "old"):
        return a
    # Synonym mapping
    if a in ("middle", "adult", "middle_age"):
        return "middle_aged"
    if a in ("elderly", "senior"):
        return "old"
    return None


def _match_score(voice: VoiceEntry, gender_label: str | None, age_label: str | None) -> int:
    """Return a match score for a voice against the desired gender/age labels.

    Score 2 = both gender and age match.
    Score 1 = only one of gender/age matches.
    Score 0 = no match.
    """
    score = 0
    if gender_label and voice.labels.get("gender") == gender_label:
        score += 1
    if age_label and voice.labels.get("age") == age_label:
        score += 1
    return score


class VoiceAssigner:
    """Assigns ElevenLabs voices to every character in a :class:`CharacterRegistry`.

    Usage::

        voices = [VoiceEntry(voice_id="v1", name="Alice", labels={"gender": "female", ...}), ...]
        assigner = VoiceAssigner(voices)
        assignment = assigner.assign(registry)   # dict[character_id, voice_id]

    The assignment is deterministic: calling :meth:`assign` twice with the
    same *registry* and voice list always returns identical results.
    """

    def __init__(self, voices: list[VoiceEntry]) -> None:
        """Initialise with a list of available voices.

        Args:
            voices: Ordered list of :class:`VoiceEntry` objects.  The first
                    entry is reserved for the narrator.
        """
        if not voices:
            raise ValueError("voices list must not be empty")
        self._voices = list(voices)

    def assign(self, registry: CharacterRegistry) -> dict[str, str]:
        """Assign a voice to every character in *registry*.

        The narrator always receives the first voice.  Non-narrator characters
        are assigned in registry (insertion) order, preferring unassigned
        voices that best match their ``sex`` / ``age`` labels.

        Args:
            registry: The character registry for the book.

        Returns:
            A ``dict[character_id, voice_id]`` covering every character.
        """
        assignment: dict[str, str] = {}
        # Track which voice indices are still available (not yet assigned)
        available_indices: list[int] = list(range(len(self._voices)))

        # Step 1 — narrator gets the first voice unconditionally
        narrator_voice_id = self._voices[0].voice_id
        narrator = registry.get("narrator")
        if narrator is not None:
            assignment["narrator"] = narrator_voice_id
            if 0 in available_indices:
                available_indices.remove(0)

        # Step 2 — assign remaining characters in registry order
        for char in registry.characters:
            if char.character_id == "narrator":
                continue  # already handled

            gender_label = _sex_to_gender_label(char.sex)
            age_label = _age_to_age_label(char.age)

            chosen_idx: int | None = None

            if available_indices:
                # Score each available voice; pick highest score, ties broken
                # by earliest position in the pool (stable / deterministic).
                best_score = -1
                best_idx = available_indices[0]
                for idx in available_indices:
                    s = _match_score(self._voices[idx], gender_label, age_label)
                    if s > best_score:
                        best_score = s
                        best_idx = idx
                chosen_idx = best_idx
                available_indices.remove(chosen_idx)
            else:
                # All voices exhausted — cycle through the pool by position
                # Use modular index based on how many assignments we've made
                cycle_pos = len(assignment) % len(self._voices)
                chosen_idx = cycle_pos

            assignment[char.character_id] = self._voices[chosen_idx].voice_id

        logger.info(
            "voice_assignment_complete",
            character_count=len(assignment),
            assigned=assignment,
        )
        return assignment
