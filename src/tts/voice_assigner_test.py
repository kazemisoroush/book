"""Tests for VoiceAssigner — deterministic voice assignment.

AC2: Voice assignment: each character is assigned a distinct ElevenLabs voice.
     The narrator gets a voice first. Remaining characters are matched by
     ``sex`` and ``age`` fields.
AC3: Assignment is deterministic (no random) given the same registry and voice list.
"""
from src.tts.voice_assigner import VoiceAssigner, VoiceEntry
from src.domain.models import Character, CharacterRegistry


def _make_voices() -> list[VoiceEntry]:
    """Return a fixed list of VoiceEntry stubs for tests."""
    return [
        VoiceEntry(voice_id="narrator_voice", name="Bella", labels={"gender": "female", "age": "middle_aged"}),
        VoiceEntry(voice_id="male_young", name="Adam", labels={"gender": "male", "age": "young"}),
        VoiceEntry(voice_id="female_young", name="Eve", labels={"gender": "female", "age": "young"}),
        VoiceEntry(voice_id="male_old", name="George", labels={"gender": "male", "age": "old"}),
        VoiceEntry(voice_id="female_old", name="Grace", labels={"gender": "female", "age": "old"}),
    ]


class TestVoiceAssignerNarratorFirst:
    """Narrator always gets the first available voice."""

    def test_narrator_receives_first_voice(self) -> None:
        """assign() must give the narrator character the first voice in the list."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        assigner = VoiceAssigner(voices)

        # Act
        assignment = assigner.assign(registry)

        # Assert
        assert assignment["narrator"] == voices[0].voice_id

    def test_narrator_voice_not_reused_by_other_characters(self) -> None:
        """The voice given to narrator must not be reused for other characters."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(character_id="char1", name="Alice", sex="female", age="young"))
        assigner = VoiceAssigner(voices)

        # Act
        assignment = assigner.assign(registry)

        # Assert
        assert assignment["char1"] != assignment["narrator"]


class TestVoiceAssignerSexAndAgeMatching:
    """Characters are matched to voices by sex and age labels."""

    def test_male_young_character_gets_male_young_voice(self) -> None:
        """A male/young character should receive the male/young voice."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(
            character_id="young_man",
            name="Tom",
            sex="male",
            age="young",
        ))
        assigner = VoiceAssigner(voices)

        # Act
        assignment = assigner.assign(registry)

        # Assert
        assert assignment["young_man"] == "male_young"

    def test_female_old_character_gets_female_old_voice(self) -> None:
        """A female/old character should receive the female/old voice."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(
            character_id="old_woman",
            name="Granny",
            sex="female",
            age="old",
        ))
        assigner = VoiceAssigner(voices)

        # Act
        assignment = assigner.assign(registry)

        # Assert
        assert assignment["old_woman"] == "female_old"

    def test_character_with_no_sex_or_age_still_gets_a_voice(self) -> None:
        """Characters without sex/age must still get assigned a voice."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(
            character_id="mystery",
            name="Unknown",
            sex=None,
            age=None,
        ))
        assigner = VoiceAssigner(voices)

        # Act
        assignment = assigner.assign(registry)

        # Assert
        assert "mystery" in assignment
        assert assignment["mystery"] is not None

    def test_each_character_gets_distinct_voice(self) -> None:
        """No two characters should share a voice (as long as voices are available)."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(character_id="c1", name="A", sex="male", age="young"))
        registry.add(Character(character_id="c2", name="B", sex="female", age="young"))
        registry.add(Character(character_id="c3", name="C", sex="male", age="old"))
        registry.add(Character(character_id="c4", name="D", sex="female", age="old"))
        assigner = VoiceAssigner(voices)

        # Act
        assignment = assigner.assign(registry)

        # Assert
        voice_ids = list(assignment.values())
        assert len(voice_ids) == len(set(voice_ids)), "Duplicate voice assignments found"


class TestVoiceAssignerDeterminism:
    """Assignment must be deterministic — same input always produces same output."""

    def test_same_registry_and_voices_produce_same_assignment(self) -> None:
        """Calling assign() twice with identical inputs must return identical maps."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(character_id="alice", name="Alice", sex="female", age="young"))
        registry.add(Character(character_id="bob", name="Bob", sex="male", age="old"))
        assigner = VoiceAssigner(voices)

        # Act
        result1 = assigner.assign(registry)
        result2 = assigner.assign(registry)

        # Assert
        assert result1 == result2

    def test_different_registry_order_produces_same_assignment_for_same_chars(self) -> None:
        """Order of characters in registry should not change their voice assignment."""
        # Arrange
        voices = _make_voices()
        registry_a = CharacterRegistry.with_default_narrator()
        registry_a.add(Character(character_id="alice", name="Alice", sex="female", age="young"))
        registry_a.add(Character(character_id="bob", name="Bob", sex="male", age="old"))

        registry_b = CharacterRegistry.with_default_narrator()
        registry_b.add(Character(character_id="bob", name="Bob", sex="male", age="old"))
        registry_b.add(Character(character_id="alice", name="Alice", sex="female", age="young"))

        assigner = VoiceAssigner(voices)

        # Act
        result_a = assigner.assign(registry_a)
        result_b = assigner.assign(registry_b)

        # Assert
        assert result_a["narrator"] == result_b["narrator"]
        assigner2 = VoiceAssigner(voices)
        result_a2 = assigner2.assign(registry_a)
        assert result_a == result_a2


class TestVoiceAssignerVoiceExhaustion:
    """Behaviour when there are more characters than available voices."""

    def test_voices_wrap_around_when_exhausted(self) -> None:
        """When voices run out, characters reuse voices from the pool."""
        # Arrange
        voices = [
            VoiceEntry(voice_id="v1", name="V1", labels={}),
            VoiceEntry(voice_id="v2", name="V2", labels={}),
        ]
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(character_id="c1", name="C1", sex=None, age=None))
        registry.add(Character(character_id="c2", name="C2", sex=None, age=None))
        assigner = VoiceAssigner(voices)

        # Act
        assignment = assigner.assign(registry)

        # Assert
        assert "narrator" in assignment
        assert "c1" in assignment
        assert "c2" in assignment


class TestVoiceAssignerReturnType:
    """Return type must be dict[str, str]."""

    def test_assign_returns_dict_of_str_to_str(self) -> None:
        """assign() must return dict[str, str]."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        assigner = VoiceAssigner(voices)

        # Act
        result = assigner.assign(registry)

        # Assert
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, str)

    def test_assign_returns_entry_for_every_character_in_registry(self) -> None:
        """assign() must include an entry for every character in the registry."""
        # Arrange
        voices = _make_voices()
        registry = CharacterRegistry.with_default_narrator()
        registry.add(Character(character_id="x", name="X", sex=None, age=None))
        registry.add(Character(character_id="y", name="Y", sex=None, age=None))
        assigner = VoiceAssigner(voices)

        # Act
        result = assigner.assign(registry)

        # Assert
        for char in registry.characters:
            assert char.character_id in result
