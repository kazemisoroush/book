"""Tests for AnthropicProvider."""
from unittest.mock import MagicMock, patch

from src.ai.anthropic_provider import AnthropicProvider
from src.ai.token_tracker import TokenTracker
from src.domain.models import AIPrompt

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_prompt(static: str = "STATIC", dynamic: str = "DYNAMIC") -> AIPrompt:
    """Build a minimal AIPrompt for testing."""
    return AIPrompt(
        static_instructions=static,
        book_context="",
        character_registry=dynamic,
        surrounding_context="",
        scene_registry="",
        text_to_parse="",
    )


def _make_sdk_response(text: str, input_tokens: int, output_tokens: int) -> MagicMock:
    """Build a mock Anthropic SDK response object."""
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


def _make_config(api_key: str = "test-key", model_id: str = "claude-opus-4-5-20251101") -> MagicMock:
    """Build a minimal mock Config with anthropic sub-config."""
    config = MagicMock()
    config.anthropic.api_key = api_key
    config.anthropic.model_id = model_id
    return config


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAnthropicProviderGenerate:
    """Tests for AnthropicProvider.generate()."""

    def test_returns_text_content_from_sdk_response(self) -> None:
        """generate() returns the text from the first content block."""
        config = _make_config()
        fake_response = _make_sdk_response("Hello world", input_tokens=10, output_tokens=5)

        with patch("src.ai.anthropic_provider.anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.return_value = fake_response

            provider = AnthropicProvider(config)
            result = provider.generate(_make_prompt(), max_tokens=100)

        assert result == "Hello world"

    def test_token_tracker_receives_correct_values(self) -> None:
        """generate() calls token_tracker.record() with model_id, input_tokens, output_tokens."""
        config = _make_config(model_id="claude-opus-4-5-20251101")
        fake_response = _make_sdk_response("response text", input_tokens=42, output_tokens=17)
        tracker = TokenTracker()

        with patch("src.ai.anthropic_provider.anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.return_value = fake_response

            provider = AnthropicProvider(config, token_tracker=tracker)
            provider.generate(_make_prompt(), max_tokens=200)

        assert tracker.call_count == 1
        call = tracker.calls[0]
        assert call.model_id == "claude-opus-4-5-20251101"
        assert call.input_tokens == 42
        assert call.output_tokens == 17

    def test_system_block_contains_cache_control(self) -> None:
        """generate() sends system block with cache_control ephemeral on static portion."""
        config = _make_config()
        fake_response = _make_sdk_response("ok", input_tokens=5, output_tokens=2)

        with patch("src.ai.anthropic_provider.anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.return_value = fake_response

            provider = AnthropicProvider(config)
            prompt = _make_prompt(static="MY_STATIC_INSTRUCTIONS")
            provider.generate(prompt, max_tokens=50)

        call_kwargs = mock_client.messages.create.call_args
        system_arg = call_kwargs.kwargs["system"]

        # Should be a list of blocks
        assert isinstance(system_arg, list)
        assert len(system_arg) >= 1

        static_block = system_arg[0]
        assert static_block["type"] == "text"
        assert "MY_STATIC_INSTRUCTIONS" in static_block["text"]
        assert static_block["cache_control"] == {"type": "ephemeral"}


class TestAnthropicProviderDefaultTracker:
    """AnthropicProvider creates its own TokenTracker when none is provided."""

    def test_default_token_tracker_created(self) -> None:
        """When no token_tracker is passed, provider has a working TokenTracker."""
        config = _make_config()
        fake_response = _make_sdk_response("text", input_tokens=3, output_tokens=1)

        with patch("src.ai.anthropic_provider.anthropic.Anthropic") as mock_anthropic_cls:
            mock_client = MagicMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create.return_value = fake_response

            provider = AnthropicProvider(config)
            provider.generate(_make_prompt())

        assert provider.token_tracker.call_count == 1
