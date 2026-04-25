"""Anthropic direct API provider using the anthropic Python SDK."""
from typing import Optional, cast

import anthropic
from anthropic.types import TextBlock

from ..config import Config
from ..domain.models import AIPrompt
from .ai_provider import AIProvider
from .token_tracker import TokenTracker


class AnthropicProvider(AIProvider):
    """AI provider using the Anthropic API directly via the anthropic Python SDK.

    This is a generic LLM provider with no domain knowledge.
    It simply takes prompts and returns responses.

    Token usage is tracked automatically on every :meth:`generate` call via an
    injectable :class:`TokenTracker`.  If no tracker is supplied, a private one
    is created and accessible via :attr:`token_tracker`.

    Prompt caching is transparently applied: the static portion of the prompt
    (returned by ``prompt.build_static_portion()``) is sent as a ``system``
    block with ``"cache_control": {"type": "ephemeral"}``, matching the
    structure used by :class:`AWSBedrockProvider`.

    Unlike :class:`AWSBedrockProvider`, no retry logic is applied — Anthropic
    API keys do not expire mid-session, so failures are raised immediately.
    """

    def __init__(
        self,
        config: Config,
        *,
        token_tracker: Optional[TokenTracker] = None,
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            config: Configuration object with Anthropic API key and model ID.
            token_tracker: Optional shared tracker for recording token usage.
                           If *None*, a new private tracker is created.
        """
        self.config = config
        self.model_id = config.anthropic.model_id
        self.token_tracker: TokenTracker = (
            token_tracker if token_tracker is not None else TokenTracker()
        )
        self._client = anthropic.Anthropic(api_key=config.anthropic.api_key)

    def generate(self, prompt: AIPrompt, max_tokens: int = 1000) -> str:
        """Generate a response from Claude via the Anthropic API.

        Token usage reported in the response is recorded in :attr:`token_tracker`.

        Prompt caching is applied: the static portion of the prompt is marked
        with ``cache_control`` so that subsequent calls with identical static
        sections pay reduced token costs (Anthropic's prompt caching feature).

        Args:
            prompt: The structured AIPrompt to send to the model.
            max_tokens: Maximum tokens in response (default: 1000).

        Returns:
            The model's response text.

        Raises:
            Exception: If the API call fails.
        """
        static_portion = prompt.build_static_portion()
        dynamic_portion = prompt.build_dynamic_portion()

        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": static_portion,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": dynamic_portion,
                }
            ],
        )

        input_tokens: int = response.usage.input_tokens
        output_tokens: int = response.usage.output_tokens
        self.token_tracker.record(
            model_id=self.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return cast(TextBlock, response.content[0]).text
