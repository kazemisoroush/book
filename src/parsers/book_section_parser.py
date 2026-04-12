"""Abstract base class for section parsers in the parsers layer.

Defines the ``BookSectionParser`` interface that all concrete section parsers
must implement.  Concrete implementations (e.g. ``AISectionParser``) receive a
section, the current ``CharacterRegistry``, and an optional ``context_window``
of neighbouring sections for speaker inference.
"""
from abc import ABC, abstractmethod
from typing import Optional
from src.domain.models import Section, Segment, CharacterRegistry, SceneRegistry


class BookSectionParser(ABC):
    """Abstract base class for section parsers.

    The parser receives the current :class:`CharacterRegistry` (for context)
    and returns both the segmented section and the potentially-updated registry.

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
    ) -> tuple[list[Segment], CharacterRegistry]:
        """Parse a section into segments, returning updated registry.

        Args:
            section: The section to segment.
            registry: The current character registry (read for context; may be
                      mutated with new characters discovered in this section).
            context_window: Optional list of neighbouring sections (typically
                            up to 5 preceding sections) provided as read-only
                            context for speaker inference.  The parser must
                            not re-segment these sections.
            scene_registry: Optional scene registry for tracking acoustic
                            environments across the book.

        Returns:
            A tuple of (segments, updated_registry).
        """
        pass
