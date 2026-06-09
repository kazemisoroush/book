"""Tests for FishAudioCharacterProvider."""
import pytest

from src.characters.fish_audio_character_provider import FishAudioCharacterProvider
from src.domain.character import Character


def test_upsert_raises_not_implemented() -> None:
    # Arrange
    provider = FishAudioCharacterProvider()
    character = Character(id=2, name="Alice")

    # Act / Assert
    with pytest.raises(NotImplementedError):
        provider.upsert(character, "book:author")
