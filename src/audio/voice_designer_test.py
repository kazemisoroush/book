"""Tests for voice_designer — ElevenLabs Voice Design API (US-014 AC4)."""
from unittest.mock import MagicMock

from src.audio.voice_designer import design_voice


class TestDesignVoice:
    """design_voice() calls create-previews then create-voice and returns voice_id."""

    def test_calls_create_previews_then_create_voice_and_returns_voice_id(self) -> None:
        """design_voice() must POST create_previews, take the first preview's
        generated_voice_id, POST create to make it permanent, and return the
        permanent voice_id."""
        # Arrange — one mock: the ElevenLabs client
        client = MagicMock()

        # Stub create_previews to return a response with one preview
        preview = MagicMock()
        preview.generated_voice_id = "gen_voice_abc123"
        preview_response = MagicMock()
        preview_response.previews = [preview]
        client.text_to_voice.create_previews.return_value = preview_response

        # Stub create to return a Voice with a permanent voice_id
        created_voice = MagicMock()
        created_voice.voice_id = "permanent_voice_xyz789"
        client.text_to_voice.create.return_value = created_voice

        # Act
        result = design_voice(
            description="adult male, booming bass voice, thick West Country accent.",
            character_name="Hagrid",
            client=client,
        )

        # Assert — correct API calls in order
        client.text_to_voice.create_previews.assert_called_once()
        call_kwargs = client.text_to_voice.create_previews.call_args
        assert call_kwargs.kwargs["voice_description"] == (
            "adult male, booming bass voice, thick West Country accent."
        )

        client.text_to_voice.create.assert_called_once()
        create_kwargs = client.text_to_voice.create.call_args
        assert create_kwargs.kwargs["voice_name"] == "Hagrid"
        assert create_kwargs.kwargs["generated_voice_id"] == "gen_voice_abc123"
        assert create_kwargs.kwargs["voice_description"] == (
            "adult male, booming bass voice, thick West Country accent."
        )

        assert result == "permanent_voice_xyz789"

    def test_uses_fixed_preview_text(self) -> None:
        """design_voice() must send a fixed preview_text to create_previews."""
        # Arrange
        client = MagicMock()
        preview = MagicMock()
        preview.generated_voice_id = "gen_id"
        preview_response = MagicMock()
        preview_response.previews = [preview]
        client.text_to_voice.create_previews.return_value = preview_response

        created_voice = MagicMock()
        created_voice.voice_id = "perm_id"
        client.text_to_voice.create.return_value = created_voice

        # Act
        design_voice(
            description="young female, bright clear soprano.",
            character_name="Luna",
            client=client,
        )

        # Assert — the text kwarg must be a non-empty fixed string
        call_kwargs = client.text_to_voice.create_previews.call_args
        text_sent = call_kwargs.kwargs.get("text")
        assert text_sent is not None
        assert len(text_sent) > 10  # meaningful sentence, not empty


