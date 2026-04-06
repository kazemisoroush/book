"""AI provider interface - generic LLM abstraction.

This module defines a simple, generic interface for AI/LLM providers.
The provider knows nothing about books, characters, or any domain logic.
It accepts structured prompts that can be cached by LLM backends.

Supports multiple backends: AWS Bedrock, OpenAI, Anthropic, local models, etc.
"""
from abc import ABC, abstractmethod
from src.domain.models import AIPrompt


class AIProvider(ABC):
    """Abstract base class for AI providers.

    A generic LLM interface with no domain knowledge.
    Domain-specific logic (character registry, dialogue detection) belongs in higher layers.

    All providers accept structured AIPrompt objects for cache-friendly segmentation.
    """

    @abstractmethod
    def generate(self, prompt: AIPrompt, max_tokens: int = 1000) -> str:
        """Generate a response from the AI model.

        Args:
            prompt: The structured prompt to send to the model
            max_tokens: Maximum tokens in the response (default: 1000)

        Returns:
            The model's response text

        Raises:
            Exception: If the API call fails
        """
        pass
