"""Tests for the VibeVoice character provider."""
from typing import Optional

from src.characters.vibevoice_character_provider import VibeVoiceCharacterProvider
from src.domain.character import Character


def _character(character_id: int, gender: Optional[str]) -> Character:
    return Character(id=character_id, name=f"c{character_id}", gender=gender)


def test_narrator_gets_first_neutral_male_voice() -> None:
    # Arrange
    provider = VibeVoiceCharacterProvider()

    # Act
    voice_id = provider.upsert(_character(1, "male"), "book")

    # Assert
    assert voice_id == "en-Carter_man"


def test_male_characters_cycle_through_male_pool() -> None:
    # Arrange
    provider = VibeVoiceCharacterProvider()

    # Act
    voices = [provider.upsert(_character(i, "male"), "book") for i in range(1, 4)]

    # Assert
    assert voices == ["en-Carter_man", "en-Frank_man", "in-Samuel_man"]


def test_female_character_gets_female_voice() -> None:
    # Arrange
    provider = VibeVoiceCharacterProvider()

    # Act
    voice_id = provider.upsert(_character(2, "female"), "book")

    # Assert
    assert voice_id == "en-Alice_woman"


def test_same_character_keeps_same_voice() -> None:
    # Arrange
    provider = VibeVoiceCharacterProvider()
    first = provider.upsert(_character(5, "male"), "book")

    # Act
    second = provider.upsert(_character(5, "male"), "book")

    # Assert
    assert first == second


def test_unknown_gender_falls_back_to_default_voice() -> None:
    # Arrange
    provider = VibeVoiceCharacterProvider()

    # Act
    voice_id = provider.upsert(_character(9, None), "book")

    # Assert
    assert voice_id == "en-Carter_man"
