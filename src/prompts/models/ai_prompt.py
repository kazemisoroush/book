"""Abstract base for structured LLM prompts.

Concrete prompt classes encapsulate the input shape for a specific LLM
task (section parsing, book-title announcement, chapter announcement).
Each concrete class owns its own ``.prompt`` template file under
[src/prompts/templates/](../templates/) and exposes the cacheable static
portion and the per-call dynamic portion separately so providers can take
advantage of prompt caching (for example AWS Bedrock or Anthropic).
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / "templates"


def load_template(filename: str) -> str:
    """Return the contents of a ``.prompt`` template by filename."""
    return (TEMPLATE_DIR / filename).read_text()


class AIPrompt(ABC):
    """Interface for any structured prompt sent to an :class:`AIProvider`.

    Implementations are frozen dataclasses. Each subclass declares the
    template file it owns via :attr:`TEMPLATE_FILENAME` and loads its
    static instructions from that file. Callers never inject the template
    text.
    """

    TEMPLATE_FILENAME: ClassVar[str] = ""

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
