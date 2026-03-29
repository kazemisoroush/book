"""Tests for AI-powered section parser."""
from typing import Optional
import pytest
from src.parsers.ai_section_parser import AISectionParser
from src.ai.ai_provider import AIProvider
from src.domain.models import Section, SegmentType, CharacterRegistry, Character


class MockAIProvider(AIProvider):
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

    def test_parse_simple_dialogue_and_narration(self):
        # Arrange
        mock_response = '''[
            {"type": "dialogue", "text": "Hello", "speaker": "Harry"},
            {"type": "narration", "text": "said Harry."}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Hello," said Harry.')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 2
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].text == "Hello"
        assert segments[0].character_id == "Harry"
        assert segments[1].segment_type == SegmentType.NARRATION
        assert segments[1].text == "said Harry."
        assert segments[1].character_id == "narrator"

    def test_parse_handles_markdown_code_blocks(self):
        # Arrange — AI sometimes wraps response in markdown
        mock_response = '''```json
        [
            {"type": "dialogue", "text": "Test", "speaker": "Bob"}
        ]
        ```'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Test," said Bob.')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].text == "Test"

    def test_parse_dialogue_without_speaker(self):
        # Arrange
        mock_response = '''[
            {"type": "dialogue", "text": "Who goes there?", "speaker": null}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Who goes there?"')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].character_id is None

    def test_parse_illustration_segment(self):
        # Arrange
        mock_response = '''[
            {"type": "illustration", "text": "[Illustration: A castle]"}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='[Illustration: A castle]')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.ILLUSTRATION

    def test_parse_copyright_segment(self):
        # Arrange
        mock_response = '''[
            {"type": "copyright", "text": "Copyright 2020"}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Copyright 2020')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.COPYRIGHT

    def test_parse_unknown_type_defaults_to_narration(self):
        # Arrange
        mock_response = '''[
            {"type": "unknown_type", "text": "Some text"}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.NARRATION

    def test_parse_raises_error_on_invalid_json(self):
        # Arrange
        ai_provider = MockAIProvider("not valid json")
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')
        registry = self._default_registry()

        # Act / Assert
        with pytest.raises(
            ValueError, match="Failed to parse AI response as JSON"
        ):
            parser.parse(section, registry)

    def test_parse_raises_error_on_non_array_non_object_response(self):
        """A JSON value that is neither an array nor an object raises ValueError."""
        # Arrange — a bare JSON number is neither array nor object
        mock_response = '42'
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='Some text')
        registry = self._default_registry()

        # Act / Assert
        with pytest.raises(ValueError, match="Response must be a JSON array"):
            parser.parse(section, registry)

    def test_prompt_includes_section_text(self):
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test section text')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert 'Test section text' in ai_provider.last_prompt

    def test_prompt_includes_book_context_when_provided(self):
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(
            ai_provider,
            book_title="Harry Potter",
            book_author="J.K. Rowling"
        )
        section = Section(text='Test')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert 'Harry Potter' in ai_provider.last_prompt
        assert 'J.K. Rowling' in ai_provider.last_prompt

    def test_prompt_works_without_book_context(self):
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert ai_provider.last_prompt is not None
        assert 'Test' in ai_provider.last_prompt

    def test_narration_segment_gets_narrator_character_id(self):
        """Narration segments must receive character_id='narrator', not None."""
        # Arrange
        mock_response = '''[
            {"type": "narration", "text": "It was a dark night."}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='It was a dark night.')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.NARRATION
        assert segments[0].character_id == "narrator"

    def test_narration_with_null_speaker_gets_narrator_character_id(self):
        """Narration segments with explicit null speaker get character_id='narrator'."""
        # Arrange
        mock_response = '''[
            {"type": "narration", "text": "She walked away.", "speaker": null}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='She walked away.')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].character_id == "narrator"

    def test_dialogue_without_speaker_keeps_none_character_id(self):
        """Dialogue with unknown speaker keeps character_id=None (not narrator)."""
        # Arrange
        mock_response = '''[
            {"type": "dialogue", "text": "Who goes there?", "speaker": null}
        ]'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Who goes there?"')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].segment_type == SegmentType.DIALOGUE
        assert segments[0].character_id is None

    def test_prompt_includes_registry_context(self):
        """Prompt must include the existing characters from the registry."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test text.')
        registry = CharacterRegistry(characters=[
            Character(character_id="narrator", name="Narrator", is_narrator=True),
            Character(character_id="harry", name="Harry Potter"),
        ])

        # Act
        parser.parse(section, registry)

        # Assert — prompt must mention both character_id and name for existing chars
        assert "harry" in ai_provider.last_prompt
        assert "Harry Potter" in ai_provider.last_prompt

    def test_prompt_instructs_to_reuse_existing_ids(self):
        """Prompt must instruct the AI to reuse known character IDs."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test text.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert — the prompt should mention reuse of existing IDs
        prompt_lower = ai_provider.last_prompt.lower()
        assert "reuse" in prompt_lower or "existing" in prompt_lower

    def test_new_characters_in_response_are_upserted_into_registry(self):
        """When AI returns new_characters, they are upserted into the registry."""
        # Arrange
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

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert
        found = updated_registry.get("hermione")
        assert found is not None
        assert found.name == "Hermione Granger"

    def test_returned_registry_contains_narrator_from_input(self):
        """The returned registry must still include the narrator character."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test.')
        registry = self._default_registry()

        # Act
        _, returned_registry = parser.parse(section, registry)

        # Assert
        assert returned_registry.get("narrator") is not None

    def test_parse_response_with_wrapped_segments_format(self):
        """Parser handles {'segments': [...], 'new_characters': [...]} format."""
        # Arrange
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

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].text == "He walked in."

    # ------------------------------------------------------------------ #
    #  context_window parameter tests                                       #
    # ------------------------------------------------------------------ #

    def test_parse_accepts_context_window_none(self):
        """parse() must accept context_window=None without error."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test.')
        registry = self._default_registry()

        # Act / Assert — should not raise
        result = parser.parse(section, registry, context_window=None)
        assert isinstance(result, tuple)

    def test_parse_accepts_empty_context_window(self):
        """parse() must accept an empty context_window list without error."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test.')
        registry = self._default_registry()

        # Act / Assert — should not raise
        result = parser.parse(section, registry, context_window=[])
        assert isinstance(result, tuple)

    def test_prompt_includes_context_window_text_when_provided(self):
        """When context_window is supplied, the context section text appears in the prompt."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        ctx1 = Section(text='Mrs. Bennet spoke first.')
        ctx2 = Section(text='Mr. Bennet listened quietly.')
        section = Section(text='"You want to tell me," said he.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=[ctx1, ctx2])

        # Assert — both context texts appear in the prompt
        assert 'Mrs. Bennet spoke first.' in ai_provider.last_prompt
        assert 'Mr. Bennet listened quietly.' in ai_provider.last_prompt

    def test_prompt_without_context_window_does_not_include_surrounding_context_header(self):
        """Without context_window, no 'surrounding context' header appears in the prompt."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=None)

        # Assert
        assert 'Surrounding context' not in ai_provider.last_prompt
        assert 'surrounding context' not in ai_provider.last_prompt

    def test_prompt_includes_surrounding_context_header_when_window_provided(self):
        """When context_window has sections, the prompt labels them as surrounding context."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        ctx = Section(text='Context paragraph.')
        section = Section(text='Target paragraph.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=[ctx])

        # Assert — prompt must contain some label for the context block
        prompt_lower = ai_provider.last_prompt.lower()
        assert 'surrounding context' in prompt_lower or 'context' in prompt_lower

    def test_prompt_still_includes_main_section_text_when_context_provided(self):
        """The main section text must still appear in the prompt alongside the context."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        ctx = Section(text='Context paragraph.')
        section = Section(text='Main target text.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=[ctx])

        # Assert — both texts present
        assert 'Main target text.' in ai_provider.last_prompt
        assert 'Context paragraph.' in ai_provider.last_prompt

    def test_prompt_does_not_ask_ai_to_segment_context_sections(self):
        """The context block must instruct the AI to use context for inference only, not re-segment it."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        ctx = Section(text='Context paragraph.')
        section = Section(text='Main text.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=[ctx])

        # Assert — prompt must indicate context is read-only / for reference
        prompt_lower = ai_provider.last_prompt.lower()
        assert (
            'do not segment' in prompt_lower
            or 'read-only' in prompt_lower
            or 'for context' in prompt_lower
            or 'reference only' in prompt_lower
            or 'for speaker inference' in prompt_lower
            or 'context only' in prompt_lower
        )


# ── sex / age extraction ───────────────────────────────────────────────────────

class TestAISectionParserSexAge:
    """Tests that AISectionParser extracts sex and age for new characters."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_new_character_with_sex_and_age_are_populated(self):
        """When AI returns sex and age in new_characters, Character has those values."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Hello", "speaker": "hermione"}
            ],
            "new_characters": [
                {"character_id": "hermione", "name": "Hermione Granger", "sex": "female", "age": "young"}
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Hello," said Hermione.')
        registry = self._default_registry()

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert
        char = updated_registry.get("hermione")
        assert char is not None
        assert char.sex == "female"
        assert char.age == "young"

    def test_new_character_without_sex_and_age_defaults_to_none(self):
        """When AI omits sex and age, Character has sex=None and age=None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Morning", "speaker": "ron"}
            ],
            "new_characters": [
                {"character_id": "ron", "name": "Ron Weasley"}
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Morning," said Ron.')
        registry = self._default_registry()

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert
        char = updated_registry.get("ron")
        assert char is not None
        assert char.sex is None
        assert char.age is None

    def test_new_character_with_null_sex_and_age_gives_none(self):
        """When AI returns null for sex and age, Character has sex=None and age=None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Yes", "speaker": "voldemort"}
            ],
            "new_characters": [
                {"character_id": "voldemort", "name": "Lord Voldemort", "sex": null, "age": null}
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Yes," said Voldemort.')
        registry = self._default_registry()

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert
        char = updated_registry.get("voldemort")
        assert char is not None
        assert char.sex is None
        assert char.age is None

    def test_new_character_with_sex_but_not_age(self):
        """When AI returns sex but omits age, Character has sex set and age=None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Indeed", "speaker": "mcgonagall"}
            ],
            "new_characters": [
                {"character_id": "mcgonagall", "name": "Professor McGonagall", "sex": "female"}
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Indeed," said McGonagall.')
        registry = self._default_registry()

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert
        char = updated_registry.get("mcgonagall")
        assert char is not None
        assert char.sex == "female"
        assert char.age is None

    def test_prompt_mentions_sex_field(self):
        """The prompt instructs the AI to infer sex for new characters."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test text.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert '"sex"' in ai_provider.last_prompt or "'sex'" in ai_provider.last_prompt or 'sex' in ai_provider.last_prompt

    def test_prompt_mentions_age_field(self):
        """The prompt instructs the AI to infer age for new characters."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test text.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert '"age"' in ai_provider.last_prompt or "'age'" in ai_provider.last_prompt or 'age' in ai_provider.last_prompt

    def test_prompt_example_new_characters_entry_includes_sex_and_age(self):
        """The example JSON in the prompt shows sex and age keys in new_characters."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test text.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert — both fields appear in the prompt example
        prompt = ai_provider.last_prompt
        assert '"sex"' in prompt
        assert '"age"' in prompt


# ── US-007: illustration skip and empty-text guard ────────────────────────────


class TestAISectionParserIllustrationSkip:
    """AI parser skips sections tagged section_type='illustration' (US-007)."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_illustration_section_is_not_sent_to_ai(self) -> None:
        """When section_type='illustration', the AI provider is never called."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text="Mr. & Mrs. Bennet", section_type="illustration")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert ai_provider.last_prompt is None

    def test_illustration_section_returns_single_illustration_segment(self) -> None:
        """Illustration section is passed through as a single ILLUSTRATION segment."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text="Mr. & Mrs. Bennet", section_type="illustration")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.ILLUSTRATION

    def test_illustration_section_segment_text_preserved(self) -> None:
        """The text of the pass-through illustration segment equals the section text."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text="Mr. & Mrs. Bennet", section_type="illustration")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].text == "Mr. & Mrs. Bennet"

    def test_illustration_section_registry_unchanged(self) -> None:
        """Registry is returned unchanged when an illustration section is skipped."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text="Mr. & Mrs. Bennet", section_type="illustration")
        registry = self._default_registry()

        # Act
        _, returned_registry = parser.parse(section, registry)

        # Assert
        assert returned_registry.get("narrator") is not None

    def test_non_illustration_section_still_calls_ai(self) -> None:
        """Sections without section_type still go through the AI provider."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Normal prose section.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert ai_provider.last_prompt is not None


class TestAISectionParserEmptyTextGuard:
    """AI parser does not crash when section text is empty (US-007)."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_empty_text_section_does_not_raise(self) -> None:
        """parse() with section.text='' must not raise an exception."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="")
        registry = self._default_registry()

        # Act / Assert — must not raise
        result = parser.parse(section, registry)
        assert isinstance(result, tuple)

    def test_empty_text_section_returns_empty_segments(self) -> None:
        """parse() with section.text='' returns an empty segments list."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments == []

    def test_empty_text_section_does_not_call_ai(self) -> None:
        """parse() with section.text='' does not invoke the AI provider."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text="")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert ai_provider.last_prompt is None
