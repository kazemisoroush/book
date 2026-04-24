"""Tests for AIProvider interface."""
from typing import Optional

from src.ai.ai_provider import AIProvider
from src.domain.models import AIPrompt


class MockAIProvider(AIProvider):
    """Mock AI provider for testing the new AIPrompt signature."""

    def __init__(self, response: str):
        self.response = response
        self.last_prompt: Optional[AIPrompt] = None
        self.last_max_tokens: Optional[int] = None

    def generate(self, prompt: AIPrompt, max_tokens: int = 1000) -> str:  # type: ignore[override]
        """Mock generate accepting AIPrompt."""
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return self.response


class TestAIProviderAcceptsAIPrompt:
    """Tests that AIProvider interface accepts AIPrompt."""

    def test_mock_ai_provider_accepts_ai_prompt(self) -> None:
        """MockAIProvider.generate() accepts AIPrompt and returns response."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="STATIC",
            book_context="BOOK",
            character_registry="CHAR",
            surrounding_context="CTX",
            scene_registry="SCENE",
            text_to_segment="TEXT",
        )
        provider = MockAIProvider("test response")

        # Act
        response = provider.generate(prompt, max_tokens=2000)

        # Assert
        assert response == "test response"
        assert provider.last_prompt is prompt
        assert provider.last_max_tokens == 2000

    def test_mock_ai_provider_stores_prompt_for_inspection(self) -> None:
        """MockAIProvider stores the prompt object for test inspection."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="S",
            book_context="B",
            character_registry="C",
            surrounding_context="X",
            scene_registry="E",
            text_to_segment="T",
        )
        provider = MockAIProvider("response")

        # Act
        _ = provider.generate(prompt, max_tokens=1000)

        # Assert
        assert provider.last_prompt is not None
        assert provider.last_prompt.static_instructions == "S"
        assert provider.last_prompt.build_full_prompt() == "SBCXET"

    def test_mock_ai_provider_default_max_tokens(self) -> None:
        """MockAIProvider.generate() defaults max_tokens to 1000."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="S",
            book_context="B",
            character_registry="C",
            surrounding_context="X",
            scene_registry="E",
            text_to_segment="T",
        )
        provider = MockAIProvider("response")

        # Act
        _ = provider.generate(prompt)

        # Assert
        assert provider.last_max_tokens == 1000
