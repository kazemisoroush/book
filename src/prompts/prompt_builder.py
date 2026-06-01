"""Abstract base for fluent prompt builders.

Each concrete subclass corresponds to a single prompt template. Inputs are
set via ``.with_*()`` methods that return a new builder for immutable
chaining; ``.build()`` returns the fully rendered prompt string.
"""
from abc import ABC, abstractmethod


class PromptBuilder(ABC):
    """Fluent builder for an LLM prompt."""

    @abstractmethod
    def build(self) -> str:
        """Render and return the final prompt string.

        Raises:
            ValueError: if any required input was not provided.
        """
