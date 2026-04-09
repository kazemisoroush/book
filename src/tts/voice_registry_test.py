"""Tests for ElevenLabsVoiceRegistry — lookup-before-create voice management.

AC9: Unit tests cover cache hit, cache miss, API error fallback, key derivation.
"""
from unittest.mock import MagicMock, patch

from src.tts.voice_registry import ElevenLabsVoiceRegistry


class TestVoiceRegistryKeyDerivation:
    """The registry must derive deterministic keys from book metadata and character ID."""

    def test_key_format_is_title_author_character_id(self) -> None:
        """get_or_create_voice() must derive a key in the format title::author::character_id."""
        # Arrange — 1 mock: ElevenLabs client with no matching voices
        client = MagicMock()
        response = MagicMock()
        response.voices = []
        client.voices.get_all.return_value = response

        registry = ElevenLabsVoiceRegistry(client)

        with patch("src.tts.voice_registry.design_voice") as mock_design:
            mock_design.return_value = "new_voice_id"

            # Act
            registry.get_or_create_voice(
                book_title="Pride and Prejudice",
                book_author="Jane Austen",
                character_id="mr_bennet",
                voice_description="middle-aged male",
                character_name="Mr. Bennet",
            )

            # Assert — design_voice called with the key as voice_name
            mock_design.assert_called_once()
            call_kwargs = mock_design.call_args.kwargs
            assert call_kwargs["character_name"] == "Pride and Prejudice::Jane Austen::mr_bennet"


class TestVoiceRegistryCacheHit:
    """When a voice with the exact key exists, return its voice_id without creating a new voice."""

    def test_existing_voice_with_exact_name_match_returns_voice_id(self) -> None:
        """get_or_create_voice() must return the voice_id of an existing voice with matching name."""
        # Arrange — 1 mock: ElevenLabs client with a matching voice
        client = MagicMock()
        existing_voice = MagicMock()
        existing_voice.name = "Pride and Prejudice::Jane Austen::mr_bennet"
        existing_voice.voice_id = "existing_voice_abc"
        response = MagicMock()
        response.voices = [existing_voice]
        client.voices.get_all.return_value = response

        registry = ElevenLabsVoiceRegistry(client)

        # Act
        result = registry.get_or_create_voice(
            book_title="Pride and Prejudice",
            book_author="Jane Austen",
            character_id="mr_bennet",
            voice_description="middle-aged male",
            character_name="Mr. Bennet",
        )

        # Assert
        assert result == "existing_voice_abc"

    def test_cache_hit_does_not_call_design_voice(self) -> None:
        """When a voice exists, design_voice() must not be called."""
        # Arrange — 1 mock: ElevenLabs client with a matching voice
        client = MagicMock()
        existing_voice = MagicMock()
        existing_voice.name = "Pride and Prejudice::Jane Austen::mr_bennet"
        existing_voice.voice_id = "existing_voice_abc"
        response = MagicMock()
        response.voices = [existing_voice]
        client.voices.get_all.return_value = response

        registry = ElevenLabsVoiceRegistry(client)

        with patch("src.tts.voice_registry.design_voice") as mock_design:
            # Act
            registry.get_or_create_voice(
                book_title="Pride and Prejudice",
                book_author="Jane Austen",
                character_id="mr_bennet",
                voice_description="middle-aged male",
                character_name="Mr. Bennet",
            )

            # Assert
            mock_design.assert_not_called()

    def test_fuzzy_search_partial_match_does_not_count_as_hit(self) -> None:
        """Voices with partial name matches must be filtered out (search is fuzzy)."""
        # Arrange — 1 mock: ElevenLabs client returns a partial match
        client = MagicMock()
        partial_match = MagicMock()
        partial_match.name = "Pride and Prejudice::Jane Austen"  # Missing character_id
        partial_match.voice_id = "partial_voice_xyz"
        response = MagicMock()
        response.voices = [partial_match]
        client.voices.get_all.return_value = response

        registry = ElevenLabsVoiceRegistry(client)

        with patch("src.tts.voice_registry.design_voice") as mock_design:
            mock_design.return_value = "new_voice_id"

            # Act
            result = registry.get_or_create_voice(
                book_title="Pride and Prejudice",
                book_author="Jane Austen",
                character_id="mr_bennet",
                voice_description="middle-aged male",
                character_name="Mr. Bennet",
            )

            # Assert — partial match ignored, new voice created
            assert result == "new_voice_id"
            mock_design.assert_called_once()


class TestVoiceRegistryCacheMiss:
    """When no voice exists, create a new one via design_voice()."""

    def test_no_matching_voice_calls_design_voice(self) -> None:
        """get_or_create_voice() must call design_voice() when no matching voice exists."""
        # Arrange — 1 mock: ElevenLabs client with no matching voices
        client = MagicMock()
        response = MagicMock()
        response.voices = []
        client.voices.get_all.return_value = response

        registry = ElevenLabsVoiceRegistry(client)

        with patch("src.tts.voice_registry.design_voice") as mock_design:
            mock_design.return_value = "new_voice_id"

            # Act
            registry.get_or_create_voice(
                book_title="Pride and Prejudice",
                book_author="Jane Austen",
                character_id="mr_bennet",
                voice_description="middle-aged male",
                character_name="Mr. Bennet",
            )

            # Assert — design_voice called with key as character_name
            mock_design.assert_called_once_with(
                description="middle-aged male",
                character_name="Pride and Prejudice::Jane Austen::mr_bennet",
                client=client,
            )

    def test_cache_miss_returns_designed_voice_id(self) -> None:
        """get_or_create_voice() must return the voice_id from design_voice()."""
        # Arrange — 1 mock: ElevenLabs client with no matching voices
        client = MagicMock()
        response = MagicMock()
        response.voices = []
        client.voices.get_all.return_value = response

        registry = ElevenLabsVoiceRegistry(client)

        with patch("src.tts.voice_registry.design_voice") as mock_design:
            mock_design.return_value = "newly_designed_voice_xyz"

            # Act
            result = registry.get_or_create_voice(
                book_title="Pride and Prejudice",
                book_author="Jane Austen",
                character_id="mr_bennet",
                voice_description="middle-aged male",
                character_name="Mr. Bennet",
            )

            # Assert
            assert result == "newly_designed_voice_xyz"


class TestVoiceRegistryAPIErrorFallback:
    """When the ElevenLabs search API fails, fall back to design_voice()."""

    def test_search_api_error_falls_back_to_design_voice(self) -> None:
        """When voices.get_all() raises an error, design_voice() must still be called."""
        # Arrange — 1 mock: ElevenLabs client that raises on search
        client = MagicMock()
        client.voices.get_all.side_effect = RuntimeError("API unavailable")

        registry = ElevenLabsVoiceRegistry(client)

        with patch("src.tts.voice_registry.design_voice") as mock_design:
            mock_design.return_value = "fallback_voice_id"

            # Act
            result = registry.get_or_create_voice(
                book_title="Pride and Prejudice",
                book_author="Jane Austen",
                character_id="mr_bennet",
                voice_description="middle-aged male",
                character_name="Mr. Bennet",
            )

            # Assert — design_voice called despite search failure
            assert result == "fallback_voice_id"
            mock_design.assert_called_once()

    def test_search_api_error_logs_warning(self) -> None:
        """When voices.get_all() fails, a warning must be logged."""
        # Arrange — 1 mock: ElevenLabs client that raises on search
        client = MagicMock()
        client.voices.get_all.side_effect = RuntimeError("API unavailable")

        with patch("src.tts.voice_registry.logger") as mock_logger:
            with patch("src.tts.voice_registry.design_voice") as mock_design:
                mock_design.return_value = "fallback_voice_id"

                registry = ElevenLabsVoiceRegistry(client)

                # Act
                registry.get_or_create_voice(
                    book_title="Pride and Prejudice",
                    book_author="Jane Austen",
                    character_id="mr_bennet",
                    voice_description="middle-aged male",
                    character_name="Mr. Bennet",
                )

                # Assert — warning logged
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[0]
                assert call_args[0] == "voice_search_failed"
