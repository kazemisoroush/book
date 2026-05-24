"""Tests for ClaudeCodeProvider.

Bridges the synchronous AIProvider contract to the async claude_agent_sdk.query()
iterator. All tests mock the SDK so they do not require Claude Code to be
installed or signed in.
"""
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from src.ai.claude_code_provider import ClaudeCodeProvider
from src.prompts.models.ai_prompt import AIPrompt
from src.prompts.models.section_parser_prompt import SectionParserPrompt


def _make_prompt(static: str = "STATIC", dynamic: str = "DYNAMIC") -> AIPrompt:
    return SectionParserPrompt(
        static_instructions=static,
        book_context="",
        character_registry=dynamic,
        surrounding_context="",
        scene_registry="",
        text_to_parse="",
    )


def _make_config() -> MagicMock:
    return MagicMock()


def _fake_text_block(text: str) -> Any:
    block = MagicMock(spec=TextBlock)
    block.text = text
    return block


def _fake_assistant_message(*texts: str) -> Any:
    msg = MagicMock(spec=AssistantMessage)
    msg.content = [_fake_text_block(t) for t in texts]
    msg.usage = None
    return msg


def _fake_result_message(
    is_error: bool = False,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> Any:
    msg = MagicMock(spec=ResultMessage)
    msg.is_error = is_error
    msg.usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    msg.stop_reason = None
    return msg


def _make_query_stub(*messages: Any):
    """Build an async-iterator factory matching claude_agent_sdk.query()'s shape."""
    async def _stub(**_kwargs: Any):
        for m in messages:
            yield m
    return _stub


class TestClaudeCodeProviderGenerate:
    """generate() joins all assistant text blocks into a single string."""

    def test_returns_joined_assistant_text(self) -> None:
        # Two assistant messages, two text blocks total
        with patch(
            "src.ai.claude_code_provider._query",
            _make_query_stub(
                _fake_assistant_message("Hello "),
                _fake_assistant_message("world"),
                _fake_result_message(),
            ),
        ):
            provider = ClaudeCodeProvider(_make_config())
            result = provider.generate(_make_prompt(), max_tokens=50)

        assert result == "Hello world"

    def test_handles_multiple_text_blocks_in_single_message(self) -> None:
        with patch(
            "src.ai.claude_code_provider._query",
            _make_query_stub(
                _fake_assistant_message("foo ", "bar ", "baz"),
                _fake_result_message(),
            ),
        ):
            provider = ClaudeCodeProvider(_make_config())
            result = provider.generate(_make_prompt())

        assert result == "foo bar baz"

    def test_returns_empty_string_when_stream_has_no_text(self) -> None:
        with patch(
            "src.ai.claude_code_provider._query",
            _make_query_stub(_fake_result_message()),
        ):
            provider = ClaudeCodeProvider(_make_config())
            result = provider.generate(_make_prompt())

        assert result == ""

    def test_raises_when_result_marked_error(self) -> None:
        with patch(
            "src.ai.claude_code_provider._query",
            _make_query_stub(_fake_result_message(is_error=True)),
        ):
            provider = ClaudeCodeProvider(_make_config())
            with pytest.raises(RuntimeError, match="claude-code"):
                provider.generate(_make_prompt())

    def test_records_token_usage_from_result_message(self) -> None:
        with patch(
            "src.ai.claude_code_provider._query",
            _make_query_stub(
                _fake_assistant_message("ok"),
                _fake_result_message(input_tokens=42, output_tokens=17),
            ),
        ):
            provider = ClaudeCodeProvider(_make_config())
            provider.generate(_make_prompt())

        assert provider.token_tracker.call_count == 1
        call = provider.token_tracker.calls[0]
        assert call.input_tokens == 42
        assert call.output_tokens == 17

    def test_passes_static_portion_as_system_prompt(self) -> None:
        captured: dict[str, Any] = {}

        async def _capture_stub(**kwargs: Any):
            captured.update(kwargs)
            yield _fake_assistant_message("done")
            yield _fake_result_message()

        with patch("src.ai.claude_code_provider._query", _capture_stub):
            provider = ClaudeCodeProvider(_make_config())
            provider.generate(_make_prompt(static="STATIC_PORTION", dynamic="DYNAMIC_PORTION"))

        # Static portion travels as the agent's system prompt.
        opts = captured["options"]
        assert "STATIC_PORTION" in opts.system_prompt
        # Dynamic portion travels as the user prompt.
        assert "DYNAMIC_PORTION" in captured["prompt"]
