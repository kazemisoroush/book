"""Workflow interface for book processing pipelines."""
from abc import ABC, abstractmethod
from src.domain.models import Book


class Workflow(ABC):
    """Abstract workflow interface.

    A workflow orchestrates multiple components to process a book
    from input (e.g., URL, file path) to a fully populated ``Book``.

    All concrete workflows return a ``Book``.  Any workflow-specific
    data (e.g. ``CharacterRegistry``) is carried as a field on the
    returned ``Book`` instance.
    """

    @abstractmethod
    def run(self, input: str) -> Book:
        """Run the workflow with the given input.

        Args:
            input: The input string (e.g., URL, file path)

        Returns:
            A fully populated Book instance

        Raises:
            Exception: If the workflow fails
        """
        pass
