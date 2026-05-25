"""Tests for FishAudioCharacterProvider."""
import pytest

from src.characters.fish_audio_character_provider import FishAudioCharacterProvider
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Character,
    CharacterRegistry,
)


def _empty_book() -> Book:
    return Book(
        metadata=BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[]),
        character_registry=CharacterRegistry(),
    )


def test_upsert_raises_not_implemented() -> None:
    # Arrange
    provider = FishAudioCharacterProvider()
    character = Character(character_id="book:alice", name="Alice")

    # Act / Assert
    with pytest.raises(NotImplementedError):
        provider.upsert(character)


def test_get_all_raises_not_implemented() -> None:
    # Arrange
    provider = FishAudioCharacterProvider()

    # Act / Assert
    with pytest.raises(NotImplementedError):
        provider.get_all(_empty_book())
