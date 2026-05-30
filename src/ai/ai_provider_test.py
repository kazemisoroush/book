"""Tests for AIProvider interface."""
from dataclasses import dataclass
from typing import Optional

from src.ai.ai_provider import AIProvider
from src.prompts.models.ai_prompt import AIPrompt


@dataclass(frozen=True)
class _StubPrompt(AIPrompt):
    static: str
    dynamic: str

    def build_static_portion(self) -> str:
        return self.static

    def build_dynamic_portion(self) -> str:
        return self.dynamic


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
        prompt = _StubPrompt(static="STATIC", dynamic="DYNAMIC")
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
        prompt = _StubPrompt(static="S", dynamic="D")
        provider = MockAIProvider("response")

        # Act
        _ = provider.generate(prompt, max_tokens=1000)

        # Assert
        assert isinstance(provider.last_prompt, AIPrompt)
        assert provider.last_prompt.build_static_portion() == "S"
        assert provider.last_prompt.build_full_prompt() == "SD"

    def test_mock_ai_provider_default_max_tokens(self) -> None:
        """MockAIProvider.generate() defaults max_tokens to 1000."""
        # Arrange
        prompt = _StubPrompt(static="S", dynamic="D")
        provider = MockAIProvider("response")

        # Act
        _ = provider.generate(prompt)

        # Assert
        assert provider.last_max_tokens == 1000
