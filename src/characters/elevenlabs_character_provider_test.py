"""Tests for ElevenLabsCharacterProvider."""
from unittest.mock import MagicMock, patch

from src.characters.elevenlabs_character_provider import ElevenLabsCharacterProvider
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Character,
    CharacterRegistry,
)


def _make_book(characters: list[Character]) -> Book:
    metadata = BookMetadata(
        title="T", author=None, releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    return Book(
        metadata=metadata,
        content=BookContent(chapters=[]),
        character_registry=CharacterRegistry(characters=list(characters)),
    )


class TestUpsert:
    """upsert designs a new voice on cache miss and reuses it on cache hit."""

    def test_returns_existing_voice_id_on_cache_hit(self) -> None:
        # Arrange
        client = MagicMock()
        existing_voice = MagicMock()
        existing_voice.name = "book:harry_potter"
        existing_voice.voice_id = "v_existing"
        client.voices.get_all.return_value = MagicMock(voices=[existing_voice])
        provider = ElevenLabsCharacterProvider(client=client)
        character = Character(
            character_id="book:harry_potter", name="Harry Potter",
            description="brave young wizard", sex="male", age="young",
        )

        # Act
        with patch("src.characters.elevenlabs_character_provider.design_voice") as mock_design:
            voice_id = provider.upsert(_make_book([character]), character)

        # Assert
        assert voice_id == "v_existing"
        mock_design.assert_not_called()

    def test_designs_voice_on_cache_miss(self) -> None:
        # Arrange
        client = MagicMock()
        client.voices.get_all.return_value = MagicMock(voices=[])
        provider = ElevenLabsCharacterProvider(client=client)
        character = Character(
            character_id="book:hagrid", name="Hagrid",
            description="booming bass voice, thick West Country accent",
            sex="male", age="adult",
        )

        # Act
        with patch(
            "src.characters.elevenlabs_character_provider.design_voice",
            return_value="v_new",
        ) as mock_design:
            voice_id = provider.upsert(_make_book([character]), character)

        # Assert
        assert voice_id == "v_new"
        mock_design.assert_called_once()
        kwargs = mock_design.call_args.kwargs
        assert kwargs["voice_name"] == "book:hagrid"
        assert "adult male" in kwargs["description"]

    def test_falls_back_to_default_prompt_when_character_has_no_description(self) -> None:
        # Arrange
        client = MagicMock()
        client.voices.get_all.return_value = MagicMock(voices=[])
        provider = ElevenLabsCharacterProvider(client=client)
        narrator = Character(
            character_id="book:narrator", name="Narrator", is_narrator=True,
        )

        # Act
        with patch(
            "src.characters.elevenlabs_character_provider.design_voice",
            return_value="v_narr",
        ) as mock_design:
            provider.upsert(_make_book([narrator]), narrator)

        # Assert
        assert mock_design.call_args.kwargs["description"]


class TestGetAll:
    """get_all reads voice_id off persisted characters."""

    def test_returns_map_of_characters_with_voice_id(self) -> None:
        # Arrange
        client = MagicMock()
        provider = ElevenLabsCharacterProvider(client=client)
        narrator = Character(
            character_id="book:narrator", name="Narrator",
            is_narrator=True, voice_id="v_narr",
        )
        alice = Character(
            character_id="book:alice", name="Alice", voice_id="v_alice",
        )
        unprovisioned = Character(character_id="book:bob", name="Bob")

        # Act
        result = provider.get_all(_make_book([narrator, alice, unprovisioned]))

        # Assert
        assert result == {"book:narrator": "v_narr", "book:alice": "v_alice"}

    def test_returns_empty_when_no_characters_have_voice_id(self) -> None:
        # Arrange
        client = MagicMock()
        provider = ElevenLabsCharacterProvider(client=client)
        character = Character(character_id="book:harry", name="Harry")

        # Act
        result = provider.get_all(_make_book([character]))

        # Assert
        assert result == {}
