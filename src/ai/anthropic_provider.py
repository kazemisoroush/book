"""Anthropic direct API provider using the anthropic Python SDK."""
from typing import Optional, cast

import anthropic
from anthropic.types import TextBlock

from ..config import Config
from .ai_provider import AIProvider
from .token_tracker import TokenTracker


class AnthropicProvider(AIProvider):
    """AI provider using the Anthropic API directly via the anthropic Python SDK.

    Token usage is tracked on every :meth:`generate` call via an injectable
    :class:`TokenTracker`. If no tracker is supplied, a private one is created
    and accessible via :attr:`token_tracker`.
    """

    def __init__(
        self,
        config: Config,
        *,
        token_tracker: Optional[TokenTracker] = None,
    ) -> None:
        self.config = config
        self.model_id = config.anthropic.model_id
        self.token_tracker: TokenTracker = (
            token_tracker if token_tracker is not None else TokenTracker()
        )
        self._client = anthropic.Anthropic(api_key=config.anthropic.api_key)

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        self.token_tracker.record(
            model_id=self.model_id,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return cast(TextBlock, response.content[0]).text
