from abc import ABC, abstractmethod
from src.domain.models import Section, Segment, CharacterRegistry


class BookSectionParser(ABC):
    """Abstract base class for section parsers.

    The parser receives the current :class:`CharacterRegistry` (for context)
    and returns both the segmented section and the potentially-updated registry.
    """

    @abstractmethod
    def parse(
        self,
        section: Section,
        registry: CharacterRegistry,
    ) -> tuple[list[Segment], CharacterRegistry]:
        """Parse a section into segments, returning updated registry.

        Args:
            section: The section to segment.
            registry: The current character registry (read for context; may be
                      mutated with new characters discovered in this section).

        Returns:
            A tuple of (segments, updated_registry).
        """
        pass
