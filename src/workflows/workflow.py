"""Workflow interface for book processing pipelines."""
from abc import ABC, abstractmethod
from src.domain.models import Book


class Workflow(ABC):
    """Abstract workflow interface.

    A workflow orchestrates multiple components to process a book
    from input (e.g., URL, file path) to a complete Book object.
    """

    @abstractmethod
    def run(self, input: str) -> Book:
        """Run the workflow with the given input.

        Args:
            input: The input string (e.g., URL, file path)

        Returns:
            Parsed Book object

        Raises:
            Exception: If the workflow fails
        """
        pass
