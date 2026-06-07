"""Anthropic direct API provider using the anthropic Python SDK."""
from typing import cast

import anthropic
from anthropic.types import TextBlock

from ..config import Config
from .ai_provider import AIProvider


class AnthropicProvider(AIProvider):
    """AI provider using the Anthropic API directly via the anthropic Python SDK."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.model_id = config.anthropic.model_id
        self._client = anthropic.Anthropic(api_key=config.anthropic.api_key)

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return cast(TextBlock, response.content[0]).text
