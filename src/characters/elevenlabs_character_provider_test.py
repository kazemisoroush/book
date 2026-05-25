"""Tests for ElevenLabsCharacterProvider."""
from unittest.mock import MagicMock

import pytest

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


def _designing_client(designed_voice_id: str) -> MagicMock:
    """Return a mock ElevenLabs client that returns *designed_voice_id* from voice design."""
    client = MagicMock()
    client.voices.get_all.return_value = MagicMock(voices=[])
    client.text_to_voice.create_previews.return_value = MagicMock(
        previews=[MagicMock(generated_voice_id="gen_id")],
    )
    client.text_to_voice.create.return_value = MagicMock(voice_id=designed_voice_id)
    return client


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
        voice_id = provider.upsert(character)

        # Assert
        assert voice_id == "v_existing"
        client.text_to_voice.create.assert_not_called()

    def test_designs_voice_on_cache_miss(self) -> None:
        # Arrange
        client = _designing_client("v_new")
        provider = ElevenLabsCharacterProvider(client=client)
        character = Character(
            character_id="book:hagrid", name="Hagrid",
            description="booming bass voice, thick West Country accent",
            sex="male", age="adult",
        )

        # Act
        voice_id = provider.upsert(character)

        # Assert
        assert voice_id == "v_new"
        create_kwargs = client.text_to_voice.create.call_args.kwargs
        assert create_kwargs["voice_name"] == "book:hagrid"
        assert "adult male" in create_kwargs["voice_description"]
        assert create_kwargs["generated_voice_id"] == "gen_id"

    def test_raises_when_character_has_no_description(self) -> None:
        # Arrange
        client = _designing_client("v_narr")
        provider = ElevenLabsCharacterProvider(client=client)
        character = Character(character_id="book:silent", name="Silent")

        # Act / Assert
        with pytest.raises(ValueError, match="no voice description"):
            provider.upsert(character)
        client.text_to_voice.create.assert_not_called()


class TestGetAll:
    """get_all queries ElevenLabs for voices prefixed with the book id."""

    def _voice(self, name: str, voice_id: str) -> MagicMock:
        v = MagicMock()
        v.name = name
        v.voice_id = voice_id
        return v

    def _book_with_metadata(self, title: str, author: str) -> Book:
        return Book(
            metadata=BookMetadata(
                title=title, author=author, releaseDate=None,
                language=None, originalPublication=None, credits=None,
            ),
            content=BookContent(chapters=[]),
            character_registry=CharacterRegistry(),
        )

    def test_returns_voices_matching_book_prefix(self) -> None:
        # Arrange
        book = self._book_with_metadata("Pride and Prejudice", "Jane Austen")
        prefix = "Pride and Prejudice - Jane Austen:"
        client = MagicMock()
        client.voices.get_all.return_value = MagicMock(voices=[
            self._voice(f"{prefix}narrator", "v_narr"),
            self._voice(f"{prefix}elizabeth_bennet", "v_eliza"),
        ])
        provider = ElevenLabsCharacterProvider(client=client)

        # Act
        result = provider.get_all(book)

        # Assert
        assert result == {
            f"{prefix}narrator": "v_narr",
            f"{prefix}elizabeth_bennet": "v_eliza",
        }
        client.voices.get_all.assert_called_once_with(search=prefix)

    def test_filters_out_voices_not_matching_book_prefix(self) -> None:
        # Arrange — ElevenLabs search is fuzzy; results may include partial matches.
        book = self._book_with_metadata("The Book", "Author")
        prefix = "The Book - Author:"
        client = MagicMock()
        client.voices.get_all.return_value = MagicMock(voices=[
            self._voice(f"{prefix}alice", "v_alice"),
            self._voice("Other Book - Other Author:narrator", "v_other"),
        ])
        provider = ElevenLabsCharacterProvider(client=client)

        # Act
        result = provider.get_all(book)

        # Assert
        assert result == {f"{prefix}alice": "v_alice"}

    def test_returns_empty_when_vendor_lookup_fails(self) -> None:
        # Arrange
        book = self._book_with_metadata("The Book", "Author")
        client = MagicMock()
        client.voices.get_all.side_effect = RuntimeError("boom")
        provider = ElevenLabsCharacterProvider(client=client)

        # Act
        result = provider.get_all(book)

        # Assert
        assert result == {}
