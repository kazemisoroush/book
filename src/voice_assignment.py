"""Voice assignment for characters."""
from typing import Optional
from src.domain.models import Book


class VoiceAssigner:
    """Assigns voices to characters and narrator."""

    def __init__(self, narrator_voice: str):
        """
        Initialize voice assigner.

        Args:
            narrator_voice: Voice ID for the narrator
        """
        self.narrator_voice = narrator_voice
        self._character_voices: dict[str, str] = {}
        self._available_voices: list[str] = []
        self._next_voice_index = 0

    def set_available_voices(self, voices: list[str]) -> None:
        """
        Set the pool of available voices for characters.

        Args:
            voices: List of voice IDs available for character assignment
        """
        self._available_voices = voices
        self._next_voice_index = 0

    def assign_voice_to_character(self, character: str, voice_id: str) -> None:
        """
        Manually assign a specific voice to a character.

        Args:
            character: Character name
            voice_id: Voice ID to assign
        """
        # Normalize to lowercase for consistent storage
        self._character_voices[character.lower()] = voice_id

    def get_voice_for_character(self, character: Optional[str]) -> str:
        """
        Get the voice ID for a character.

        If the character hasn't been assigned a voice yet,
        assigns one from the available pool.

        Args:
            character: Character name, or None for narrator

        Returns:
            Voice ID to use
        """
        if character is None:
            return self.narrator_voice

        # Normalize character name
        character = character.lower()

        if character not in self._character_voices:
            # Assign a new voice from the pool
            if self._available_voices:
                voice_id = self._available_voices[self._next_voice_index % len(self._available_voices)]
                self._character_voices[character] = voice_id
                self._next_voice_index += 1
            else:
                # Fallback to narrator voice if no character voices available
                return self.narrator_voice

        return self._character_voices[character]

    def get_character_assignments(self) -> dict[str, str]:
        """Get all character-to-voice assignments."""
        return self._character_voices.copy()

    def discover_characters(self, book: Book) -> list[str]:
        """
        Discover all unique characters in the book.

        Args:
            book: The book to analyze

        Returns:
            List of unique character names
        """
        characters = set()

        for chapter in book.chapters:
            for segment in chapter.segments:
                if segment.speaker:
                    characters.add(segment.speaker.lower())

        return sorted(list(characters))
