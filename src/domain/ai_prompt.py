"""Abstract base for structured LLM prompts.

Concrete prompt classes encapsulate the input shape for a specific LLM
task (section parsing, book-title announcement, chapter announcement).
Each concrete class splits its content into a cacheable static portion
and a per-call dynamic portion so providers can take advantage of
prompt caching (e.g. AWS Bedrock, Anthropic).
"""
from abc import ABC, abstractmethod


class AIPrompt(ABC):
    """Interface for any structured prompt sent to an :class:`AIProvider`.

    Implementations are typically frozen dataclasses. They expose the
    cacheable and per-call portions of the prompt so providers can split
    them when invoking the underlying LLM API.
    """

    @abstractmethod
    def build_static_portion(self) -> str:
        """Return the cacheable portion of the prompt.

        This is the part that does not change across multiple calls for
        the same logical task (instructions, possibly book context).
        """

    @abstractmethod
    def build_dynamic_portion(self) -> str:
        """Return the per-call portion of the prompt.

        This is the part that changes between calls (the specific input
        text, current registries, etc.).
        """

    def build_full_prompt(self) -> str:
        """Return the complete prompt: static portion followed by dynamic."""
        return self.build_static_portion() + self.build_dynamic_portion()
