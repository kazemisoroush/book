"""Tests for AI-powered section parser."""
from typing import Optional
import pytest
from src.parsers.ai_section_parser import AISectionParser
from src.domain.models import Section, SegmentType, CharacterRegistry, Character


class MockAIProvider:
    """Mock AI provider for testing."""

    def __init__(self, response: str):
        self.response = response
        self.last_prompt: Optional[str] = None
        self.last_max_tokens: Optional[int] = None

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return self.response


class TestAISectionParser:

    def _default_registry(self) -> CharacterRegistry:
        """Helper: return a registry with only the narrator."""
        return CharacterRegistry.with_default_narrator()

    def test_parse_returns_tuple_of_segments_and_registry(self):
        """parse() must return a (list[Segment], CharacterRegistry) tuple."""
        # Given
        mock_response = '[]'
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Test.')
        registry = self._default_registry()

        # When
        result = parser.parse(section, registry)

        # Then
        assert isinstance(result, tuple)
        assert len(result) == 2
        segments, returned_registry = result
        assert isinstance(segments, list)
        assert isinstance(returned_registry, CharacterRegistry)

    def test_parse_simple_dialogue_and_narration(self):
        # Given
        mock_response = '''[
            {"type": "dialogue", "text": "Hello", "speaker": "Harry"},
            {"type": "narration", "text": "said Harry."}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Hello," said Harry.')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 2
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].text == "Hello"
        assert segments[0].character_id == "Harry"
        assert segments[1].segment_type == SegmentType.NARRATION
        assert segments[1].text == "said Harry."
        assert segments[1].character_id == "narrator"

    def test_parse_handles_markdown_code_blocks(self):
        # Given - AI sometimes wraps response in markdown
        mock_response = '''```json
        [
            {"type": "dialogue", "text": "Test", "speaker": "Bob"}
        ]
        ```'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Test," said Bob.')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 1
        assert segments[0].text == "Test"

    def test_parse_dialogue_without_speaker(self):
        # Given
        mock_response = '''[
            {"type": "dialogue", "text": "Who goes there?", "speaker": null}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Who goes there?"')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].character_id is None

    def test_parse_illustration_segment(self):
        # Given
        mock_response = '''[
            {"type": "illustration", "text": "[Illustration: A castle]"}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='[Illustration: A castle]')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.ILLUSTRATION

    def test_parse_copyright_segment(self):
        # Given
        mock_response = '''[
            {"type": "copyright", "text": "Copyright 2020"}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Copyright 2020')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.COPYRIGHT

    def test_parse_unknown_type_defaults_to_narration(self):
        # Given
        mock_response = '''[
            {"type": "unknown_type", "text": "Some text"}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.NARRATION

    def test_parse_raises_error_on_invalid_json(self):
        # Given
        ai_provider = MockAIProvider("not valid json")
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')
        registry = self._default_registry()

        # When/Then
        with pytest.raises(
            ValueError, match="Failed to parse AI response as JSON"
        ):
            parser.parse(section, registry)

    def test_parse_raises_error_on_non_array_non_object_response(self):
        """A JSON value that is neither an array nor an object raises ValueError."""
        # Given — a bare JSON number is neither array nor object
        mock_response = '42'
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')
        registry = self._default_registry()

        # When/Then
        with pytest.raises(ValueError, match="Response must be a JSON array"):
            parser.parse(section, registry)

    def test_prompt_includes_section_text(self):
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test section text')
        registry = self._default_registry()

        # When
        parser.parse(section, registry)

        # Then
        assert 'Test section text' in ai_provider.last_prompt

    def test_prompt_includes_book_context_when_provided(self):
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(
            ai_provider,
            book_title="Harry Potter",
            book_author="J.K. Rowling"
        )
        section = Section(text='Test')
        registry = self._default_registry()

        # When
        parser.parse(section, registry)

        # Then
        assert 'Harry Potter' in ai_provider.last_prompt
        assert 'J.K. Rowling' in ai_provider.last_prompt

    def test_prompt_works_without_book_context(self):
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test')
        registry = self._default_registry()

        # When
        parser.parse(section, registry)

        # Then
        assert ai_provider.last_prompt is not None
        assert 'Test' in ai_provider.last_prompt

    def test_uses_max_tokens_parameter(self):
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test')
        registry = self._default_registry()

        # When
        parser.parse(section, registry)

        # Then
        assert ai_provider.last_max_tokens == 2000

    def test_narration_segment_gets_narrator_character_id(self):
        """Narration segments must receive character_id='narrator', not None."""
        # Given
        mock_response = '''[
            {"type": "narration", "text": "It was a dark night."}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='It was a dark night.')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.NARRATION
        assert segments[0].character_id == "narrator"

    def test_narration_with_null_speaker_gets_narrator_character_id(self):
        """Narration segments with explicit null speaker get character_id='narrator'."""
        # Given
        mock_response = '''[
            {"type": "narration", "text": "She walked away.", "speaker": null}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='She walked away.')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert segments[0].character_id == "narrator"

    def test_dialogue_without_speaker_keeps_none_character_id(self):
        """Dialogue with unknown speaker keeps character_id=None (not narrator)."""
        # Given
        mock_response = '''[
            {"type": "dialogue", "text": "Who goes there?", "speaker": null}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Who goes there?"')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].character_id is None

    def test_prompt_includes_registry_context(self):
        """Prompt must include the existing characters from the registry."""
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test text.')
        registry = CharacterRegistry(characters=[
            Character(character_id="narrator", name="Narrator", is_narrator=True),
            Character(character_id="harry", name="Harry Potter"),
        ])

        # When
        parser.parse(section, registry)

        # Then - prompt must mention both character_id and name for existing chars
        assert "harry" in ai_provider.last_prompt
        assert "Harry Potter" in ai_provider.last_prompt

    def test_prompt_instructs_to_reuse_existing_ids(self):
        """Prompt must instruct the AI to reuse known character IDs."""
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test text.')
        registry = self._default_registry()

        # When
        parser.parse(section, registry)

        # Then - the prompt should mention reuse of existing IDs
        prompt_lower = ai_provider.last_prompt.lower()
        assert "reuse" in prompt_lower or "existing" in prompt_lower

    def test_new_characters_in_response_are_upserted_into_registry(self):
        """When AI returns new_characters, they are upserted into the registry."""
        # Given
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Hello", "speaker": "hermione"}
            ],
            "new_characters": [
                {"character_id": "hermione", "name": "Hermione Granger"}
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Hello," said Hermione.')
        registry = self._default_registry()

        # When
        _, updated_registry = parser.parse(section, registry)

        # Then
        found = updated_registry.get("hermione")
        assert found is not None
        assert found.name == "Hermione Granger"

    def test_returned_registry_contains_narrator_from_input(self):
        """The returned registry must still include the narrator character."""
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test.')
        registry = self._default_registry()

        # When
        _, returned_registry = parser.parse(section, registry)

        # Then
        assert returned_registry.get("narrator") is not None

    def test_parse_response_with_wrapped_segments_format(self):
        """Parser handles {'segments': [...], 'new_characters': [...]} format."""
        # Given
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "He walked in."}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='He walked in.')
        registry = self._default_registry()

        # When
        segments, _ = parser.parse(section, registry)

        # Then
        assert len(segments) == 1
        assert segments[0].text == "He walked in."
