"""Claude Code AI provider — runs against the user's claude.ai Pro/Max subscription.

Uses ``claude_agent_sdk.query()`` which spawns the Claude Code CLI as a
subprocess and reuses its OAuth session. Calls bill against the signed-in
plan (Pro/Max) rather than against an API key.

Tradeoffs vs ``AnthropicProvider``:

* No Anthropic-style prompt caching at the wire level (the agent SDK does
  not expose ``cache_control``).
* Quota-billed: Pro caps around 45 messages per 5h; Max scales that.
* Requires Claude Code installed and authenticated on the host.

The agent SDK is async; ``generate()`` bridges it to the synchronous
:class:`AIProvider` contract via :func:`asyncio.run`.
"""
import asyncio
from typing import Any, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
)
from claude_agent_sdk import query as _query

from ..config import Config
from .ai_provider import AIProvider
from .token_tracker import TokenTracker


class ClaudeCodeProvider(AIProvider):
    """AI provider that runs through Claude Code's OAuth session."""

    def __init__(
        self,
        config: Config,
        *,
        token_tracker: Optional[TokenTracker] = None,
    ) -> None:
        self.config = config
        self.model_id = "claude-code"
        self.token_tracker: TokenTracker = (
            token_tracker if token_tracker is not None else TokenTracker()
        )

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:  # noqa: ARG002
        return asyncio.run(self._generate_async(prompt))

    async def _generate_async(self, prompt: str) -> str:
        options = ClaudeAgentOptions(allowed_tools=[], max_turns=1, effort="low")

        chunks: list[str] = []
        async for message in _query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                if getattr(message, "is_error", False):
                    raise RuntimeError(
                        f"claude-code query failed: stop_reason="
                        f"{getattr(message, 'stop_reason', None)!r}"
                    )
                usage: Any = getattr(message, "usage", None) or {}
                self.token_tracker.record(
                    model_id=self.model_id,
                    input_tokens=int(usage.get("input_tokens", 0)) if isinstance(usage, dict) else 0,
                    output_tokens=int(usage.get("output_tokens", 0)) if isinstance(usage, dict) else 0,
                )

        return "".join(chunks)
