"""Tests for AI-powered section parser."""
import pytest
from src.parsers.ai_section_parser import AISectionParser
from src.domain.models import Section, SegmentType


class MockAIProvider:
    """Mock AI provider for testing."""

    def __init__(self, response: str):
        self.response = response
        self.last_prompt = None
        self.last_max_tokens = None

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        self.last_prompt = prompt
        self.last_max_tokens = max_tokens
        return self.response


class TestAISectionParser:

    def test_parse_simple_dialogue_and_narration(self):
        # Given
        mock_response = '''[
            {"type": "dialogue", "text": "Hello", "speaker": "Harry"},
            {"type": "narration", "text": "said Harry."}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Hello," said Harry.')

        # When
        segments = parser.parse(section)

        # Then
        assert len(segments) == 2
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].text == "Hello"
        assert segments[0].speaker == "Harry"
        assert segments[1].segment_type == SegmentType.NARRATION
        assert segments[1].text == "said Harry."
        assert segments[1].speaker is None

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

        # When
        segments = parser.parse(section)

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

        # When
        segments = parser.parse(section)

        # Then
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].speaker is None

    def test_parse_illustration_segment(self):
        # Given
        mock_response = '''[
            {"type": "illustration", "text": "[Illustration: A castle]"}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='[Illustration: A castle]')

        # When
        segments = parser.parse(section)

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

        # When
        segments = parser.parse(section)

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

        # When
        segments = parser.parse(section)

        # Then
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.NARRATION

    def test_parse_raises_error_on_invalid_json(self):
        # Given
        ai_provider = MockAIProvider("not valid json")
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')

        # When/Then
        with pytest.raises(
            ValueError, match="Failed to parse AI response as JSON"
        ):
            parser.parse(section)

    def test_parse_raises_error_on_non_array_response(self):
        # Given
        mock_response = '{"type": "dialogue", "text": "wrong"}'
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')

        # When/Then
        with pytest.raises(ValueError, match="Response must be a JSON array"):
            parser.parse(section)

    def test_prompt_includes_section_text(self):
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test section text')

        # When
        parser.parse(section)

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

        # When
        parser.parse(section)

        # Then
        assert 'Harry Potter' in ai_provider.last_prompt
        assert 'J.K. Rowling' in ai_provider.last_prompt

    def test_prompt_works_without_book_context(self):
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test')

        # When
        parser.parse(section)

        # Then
        assert ai_provider.last_prompt is not None
        assert 'Test' in ai_provider.last_prompt

    def test_uses_max_tokens_parameter(self):
        # Given
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test')

        # When
        parser.parse(section)

        # Then
        assert ai_provider.last_max_tokens == 2000
