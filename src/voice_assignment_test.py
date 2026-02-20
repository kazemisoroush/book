"""Tests for voice assignment."""
import pytest
from .voice_assignment import VoiceAssigner
from .domain.models import Book, Chapter, Segment, SegmentType


class TestVoiceAssigner:
    """Tests for VoiceAssigner."""

    @pytest.fixture
    def assigner(self):
        return VoiceAssigner(narrator_voice="narrator_voice")

    def test_get_narrator_voice(self, assigner):
        voice = assigner.get_voice_for_character(None)
        assert voice == "narrator_voice"

    def test_assign_character_voice(self, assigner):
        assigner.assign_voice_to_character("John", "john_voice")

        voice = assigner.get_voice_for_character("John")
        assert voice == "john_voice"

    def test_auto_assign_from_pool(self, assigner):
        assigner.set_available_voices(["voice1", "voice2", "voice3"])

        voice1 = assigner.get_voice_for_character("Alice")
        voice2 = assigner.get_voice_for_character("Bob")
        voice3 = assigner.get_voice_for_character("Charlie")

        assert voice1 == "voice1"
        assert voice2 == "voice2"
        assert voice3 == "voice3"

    def test_auto_assign_wraps_around(self, assigner):
        assigner.set_available_voices(["voice1", "voice2"])

        voice1 = assigner.get_voice_for_character("Alice")
        voice2 = assigner.get_voice_for_character("Bob")
        voice3 = assigner.get_voice_for_character("Charlie")  # Should wrap to voice1

        assert voice1 == "voice1"
        assert voice2 == "voice2"
        assert voice3 == "voice1"

    def test_discover_characters(self, assigner):
        chapters = [
            Chapter(
                number=1,
                title="Chapter I",
                segments=[
                    Segment("Narration", SegmentType.NARRATION),
                    Segment("Hello", SegmentType.DIALOGUE, speaker="Alice"),
                    Segment("Hi", SegmentType.DIALOGUE, speaker="Bob"),
                    Segment("Hey", SegmentType.DIALOGUE, speaker="Alice"),
                ]
            )
        ]
        book = Book(title="Test", author="Author", chapters=chapters)

        characters = assigner.discover_characters(book)

        assert len(characters) == 2
        assert "alice" in characters
        assert "bob" in characters

    def test_case_insensitive_assignment(self, assigner):
        assigner.assign_voice_to_character("John", "john_voice")

        assert assigner.get_voice_for_character("John") == "john_voice"
        assert assigner.get_voice_for_character("john") == "john_voice"
        assert assigner.get_voice_for_character("JOHN") == "john_voice"
