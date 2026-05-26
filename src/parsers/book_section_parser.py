"""Abstract base class for section parsers in the parsers layer.

Defines the ``BookSectionParser`` interface that all concrete section parsers
must implement.  Concrete implementations (e.g. ``AISectionParser``) receive a
section, the current ``CharacterRegistry``, and an optional ``context_window``
of neighbouring sections for speaker inference.
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.beat import Beat
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
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
        book_id: str,
        book_title: Optional[str] = None,
        book_author: Optional[str] = None,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> tuple[list[Beat], CharacterRegistry]:
        """Parse *section* into beats and return them with the updated registry."""
        pass
