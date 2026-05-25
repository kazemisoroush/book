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


def test_upsert_raises_not_implemented() -> None:
    # Arrange
    provider = FishAudioCharacterProvider()
    character = Character(character_id="book:alice", name="Alice")

    # Act / Assert
    with pytest.raises(NotImplementedError):
        provider.upsert(character)


def test_get_all_returns_persisted_voice_ids() -> None:
    # Arrange
    provider = FishAudioCharacterProvider()
    alice = Character(character_id="book:alice", name="Alice", voice_id="fa_alice")
    unprovisioned = Character(character_id="book:bob", name="Bob")

    # Act
    result = provider.get_all(_make_book([alice, unprovisioned]))

    # Assert
    assert result == {"book:alice": "fa_alice"}
