"""VibeVoice implementation of :class:`CharacterProvider`."""
from typing import Optional

from src.audio.tts.vibevoice_tts_provider import VOICES
from src.characters.character_provider import CharacterProvider
from src.domain.character import Character

_MALE_VOICES = [v["voice_id"] for v in VOICES if v["labels"]["gender"] == "male"]
_FEMALE_VOICES = [v["voice_id"] for v in VOICES if v["labels"]["gender"] == "female"]
_FALLBACK_VOICE = _MALE_VOICES[0]


class VibeVoiceCharacterProvider(CharacterProvider):
    """Assigns VibeVoice reference voices to characters by gender."""

    def __init__(self) -> None:
        self._assigned: dict[int, str] = {}
        self._male_index = 0
        self._female_index = 0

    def upsert(
        self, character: Character, book_id: str, refresh: bool = False,
    ) -> str:
        """Return a stable voice id chosen from the matching gender pool."""
        if character.id in self._assigned and not refresh:
            return self._assigned[character.id]
        voice_id = self._next_voice(character.gender)
        self._assigned[character.id] = voice_id
        return voice_id

    def _next_voice(self, gender: Optional[str]) -> str:
        if gender == "female":
            voice_id = _FEMALE_VOICES[self._female_index % len(_FEMALE_VOICES)]
            self._female_index += 1
            return voice_id
        if gender == "male":
            voice_id = _MALE_VOICES[self._male_index % len(_MALE_VOICES)]
            self._male_index += 1
            return voice_id
        return _FALLBACK_VOICE
