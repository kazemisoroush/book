"""Abstract base class for section parsers in the parsers layer.

Defines the ``BookSectionParser`` interface that all concrete section parsers
must implement.  Concrete implementations (e.g. ``AISectionParser``) receive a
section, the current ``CharacterRegistry``, and an optional ``context_window``
of neighbouring sections for speaker inference.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.models import (
    Beat,
    CharacterRegistry,
    MoodRegistry,
    SceneRegistry,
    Section,
)


class BookSectionParser(ABC):
    """Abstract base class for section parsers.

    The parser receives the current :class:`CharacterRegistry` (for context)
    and returns both the beated section and the potentially-updated registry.

    An optional ``context_window`` may be supplied by the caller to provide
    neighbouring sections as read-only context for speaker inference.
    """

    @abstractmethod
    def parse(
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        scene_registry: Optional[SceneRegistry] = None,
        mood_registry: Optional[MoodRegistry] = None,
        current_open_mood_id: Optional[str] = None,
    ) -> tuple[list[Beat], CharacterRegistry]:
        """Parse a section into beats, returning updated registry.

        Args:
            section: The section to parse into beats.
            registry: The current character registry (read for context; may be
                      mutated with new characters discovered in this section).
            context_window: Optional list of neighbouring sections (typically
                            up to 5 preceding sections) provided as read-only
                            context for speaker inference.  The parser must
                            not re-parse these sections.
            scene_registry: Optional scene registry for tracking acoustic
                            environments across the book.
            mood_registry: Optional mood registry for story-mood detection
                           (US-034). Passed to the prompt so the LLM can
                           reuse ``mood_id``s when continuing an arc.
            current_open_mood_id: The mood_id of the currently-open arc, if
                                  any. Surfaced to the LLM so it knows which
                                  mood is eligible for ``continue``.

        Returns:
            A tuple of (beats, updated_registry).
        """
        pass
