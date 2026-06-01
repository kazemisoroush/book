"""AI provider interface — generic LLM abstraction.

Concrete providers (AWS Bedrock, Anthropic, Claude Code) take a rendered
prompt string and return the model's response. Prompt assembly is the
caller's responsibility — see :mod:`src.prompts.prompt_builder`.
"""
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        """Send *prompt* to the underlying model and return its response.

        Args:
            prompt: The fully rendered prompt string.
            max_tokens: Maximum tokens in the response.

        Returns:
            The model's response text.

        Raises:
            Exception: If the API call fails.
        """
