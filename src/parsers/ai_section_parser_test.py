"""Tests for AI-powered section parser."""
from typing import Optional
import pytest
from src.parsers.ai_section_parser import AISectionParser
from src.ai.ai_provider import AIProvider
from src.domain.models import (
    Section, Segment, SegmentType, CharacterRegistry, Character, SceneRegistry,
)


class MockAIProvider(AIProvider):
    """Mock AI provider for testing."""

    def __init__(self, response: str):
        self.response = response
        self.last_prompt: Optional[str] = None
        self.last_max_tokens: Optional[int] = None

    def generate(self, prompt: object, max_tokens: int = 1000) -> str:  # type: ignore[override]
        # Handle both AIPrompt and str for backward compatibility during testing
        from src.domain.models import AIPrompt
        if isinstance(prompt, AIPrompt):
            self.last_prompt = prompt.build_full_prompt()
        else:
            self.last_prompt = str(prompt)
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
        parser.parse(section, registry, context_window=None)

    def test_parse_accepts_empty_context_window(self):
        """parse() must accept an empty context_window list without error."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        section = Section(text='Test.')
        registry = self._default_registry()

        # Act / Assert — should not raise
        parser.parse(section, registry, context_window=[])

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

    def test_prompt_shows_speaker_labels_for_parsed_context_sections(self):
        """Context sections with resolved segments must show [character_id]: labels in the prompt."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        ctx = Section(
            text='"YOU want to tell me," said Mr. Bennet.',
            segments=[
                Segment(text="YOU want to tell me,", segment_type=SegmentType.DIALOGUE, character_id="mr_bennet"),
                Segment(text="said Mr. Bennet.", segment_type=SegmentType.NARRATION, character_id="narrator"),
            ],
        )
        section = Section(text='"What is his name?" he asked.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=[ctx])

        # Assert — speaker label for the dialogue segment must appear in prompt
        assert '[mr_bennet]:' in ai_provider.last_prompt

    def test_prompt_falls_back_to_raw_text_for_unparsed_context_sections(self):
        """Context sections with no segments (not yet parsed) must use raw text."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        ctx = Section(text='She walked into the room.', segments=None)
        section = Section(text='Target text.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=[ctx])

        # Assert — raw text must still appear in the prompt
        assert 'She walked into the room.' in ai_provider.last_prompt

    def test_noise_only_sections_are_excluded_from_context(self):
        """Sections whose every segment is other/illustration/copyright must be filtered out."""
        # Arrange — build 4 context sections; the middle one is pure noise
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider, context_window=3)
        substantive = Section(
            text='She replied.',
            segments=[Segment(text='She replied.', segment_type=SegmentType.NARRATION, character_id='narrator')],
        )
        noise = Section(
            text='{3}',
            segments=[Segment(text='{3}', segment_type=SegmentType.OTHER, character_id=None)],
        )
        section = Section(text='Target text.')
        registry = self._default_registry()

        # Act — pass [substantive, noise, substantive, substantive] as context
        ctx_a = Section(
            text='He asked.',
            segments=[Segment(text='He asked.', segment_type=SegmentType.DIALOGUE, character_id='mr_bennet')],
        )
        ctx_b = Section(
            text='She answered.',
            segments=[Segment(text='She answered.', segment_type=SegmentType.DIALOGUE, character_id='mrs_bennet')],
        )
        parser.parse(section, registry, context_window=[substantive, noise, ctx_a, ctx_b])

        # Assert — noise text absent; substantive sections present
        assert '{3}' not in ai_provider.last_prompt
        assert 'He asked.' in ai_provider.last_prompt
        assert 'She answered.' in ai_provider.last_prompt

    def test_mixed_section_with_some_noise_is_kept(self):
        """A section that has at least one dialogue/narration segment must not be filtered."""
        # Arrange
        ai_provider = MockAIProvider('[]')
        parser = AISectionParser(ai_provider)
        ctx = Section(
            text='"Hello," said Harry. {footnote}',
            segments=[
                Segment(text='Hello,', segment_type=SegmentType.DIALOGUE, character_id='harry'),
                Segment(text='{footnote}', segment_type=SegmentType.OTHER, character_id=None),
            ],
        )
        section = Section(text='Target.')
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=[ctx])

        # Assert — the dialogue part must appear
        assert 'harry' in ai_provider.last_prompt


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
        parser.parse(section, registry)

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


# ── US-010: freeform emotion field ────────────────────────────────────────────


class TestAISectionParserEmotion:
    """AISectionParser outputs emotion field on segments (US-009 → US-010)."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_prompt_mentions_emotion_examples_from_elevenlabs_docs(self) -> None:
        """The prompt must mention auditory examples drawn from ElevenLabs documentation."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Test text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert — prompt mentions documented ElevenLabs examples
        assert ai_provider.last_prompt is not None
        prompt_lower: str = ai_provider.last_prompt.lower()
        assert "neutral" in prompt_lower
        assert "whispers" in prompt_lower or "sighs" in prompt_lower

    def test_prompt_does_not_restrict_to_fixed_list(self) -> None:
        """The prompt must not say 'only use values from this list' (freeform guidance)."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Test text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert — must not say "only use values from this list" (the old hard constraint)
        assert ai_provider.last_prompt is not None
        assert "Only use values from this list" not in ai_provider.last_prompt

    def test_segment_with_known_lowercase_emotion_is_parsed(self) -> None:
        """When AI returns emotion='stern' (lowercase), the Segment has emotion='stern'."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Indeed.", "speaker": "mcgonagall", "emotion": "stern"}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Indeed," said McGonagall.')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].emotion == "stern"

    def test_segment_with_extended_emotion_tag_is_parsed(self) -> None:
        """When AI returns an extended tag like 'breathless', it is stored as-is."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "I cannot breathe.", "speaker": "harry", "emotion": "breathless"}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"I cannot breathe," said Harry.')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].emotion == "breathless"

    def test_segment_without_emotion_field_has_none_emotion(self) -> None:
        """When AI response omits emotion, the Segment.emotion is None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "She walked in."}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="She walked in.")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].emotion is None

    def test_segment_with_neutral_emotion_stores_lowercase_string(self) -> None:
        """When AI returns emotion='neutral', the Segment.emotion is the string 'neutral'."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Hello.", "speaker": "harry", "emotion": "neutral"}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Hello," said Harry.')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].emotion == "neutral"

    def test_prompt_instructs_auditory_constraint(self) -> None:
        """The prompt must instruct Sonnet that emotion tags must be auditory."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Test text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert — prompt uses the auditory constraint from ElevenLabs docs
        assert ai_provider.last_prompt is not None
        prompt_lower = ai_provider.last_prompt.lower()
        assert "auditory" in prompt_lower or "vocal" in prompt_lower


# ── US-016: context_window constructor param and capping ──────────────────────


class TestAISectionParserContextWindowCapping:
    """AISectionParser caps context_window list to configured max size (US-016)."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_parse_caps_context_to_configured_size(self) -> None:
        """When context_window=2 and 5 sections are passed, only the last 2 appear in the prompt."""
        # Arrange — 5 context sections, parser configured for window=2
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider, context_window=2)
        ctx_sections = [
            Section(text=f"Context section {i}.") for i in range(5)
        ]
        section = Section(text="Target text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=ctx_sections)

        # Assert — last 2 sections appear; first 3 do NOT
        prompt = ai_provider.last_prompt
        assert prompt is not None
        assert "Context section 3." in prompt
        assert "Context section 4." in prompt
        assert "Context section 0." not in prompt
        assert "Context section 1." not in prompt
        assert "Context section 2." not in prompt

    def test_parse_uses_default_window_of_five(self) -> None:
        """Default context_window=5 caps a 7-section list to the last 5."""
        # Arrange — 7 context sections, parser uses default window=5
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        ctx_sections = [
            Section(text=f"Para {i}.") for i in range(7)
        ]
        section = Section(text="Target.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=ctx_sections)

        # Assert — last 5 appear; first 2 do NOT
        prompt = ai_provider.last_prompt
        assert prompt is not None
        for i in range(2, 7):
            assert f"Para {i}." in prompt
        assert "Para 0." not in prompt
        assert "Para 1." not in prompt

    def test_parse_with_fewer_sections_than_window_uses_all(self) -> None:
        """When fewer preceding sections exist than the window size, all are included."""
        # Arrange — 2 context sections, parser configured for window=5
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider, context_window=5)
        ctx_sections = [
            Section(text="First section."),
            Section(text="Second section."),
        ]
        section = Section(text="Target text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry, context_window=ctx_sections)

        # Assert — both sections appear (window not truncated when fewer available)
        prompt = ai_provider.last_prompt
        assert prompt is not None
        assert "First section." in prompt
        assert "Second section." in prompt


# ── US-014 AC1: description extraction for new characters ─────────────────────


class TestAISectionParserDescriptionAC1:
    """AISectionParser prompt includes description field for new characters (US-014 AC1)."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_prompt_example_new_characters_entry_includes_description_field(self) -> None:
        """The example JSON in the prompt must include a 'description' key in new_characters."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Test text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert — 'description' must appear in the prompt example for new_characters
        assert ai_provider.last_prompt is not None
        assert '"description"' in ai_provider.last_prompt

    def test_prompt_instructs_voice_description_for_new_characters(self) -> None:
        """The prompt must instruct the AI to describe vocal quality/manner of speaking for new characters."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Test text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert — prompt must mention vocal quality / manner of speaking near new character instructions
        assert ai_provider.last_prompt is not None
        prompt_lower = ai_provider.last_prompt.lower()
        assert (
            "vocal" in prompt_lower
            or "voice" in prompt_lower
            or "manner of speaking" in prompt_lower
            or "speaking" in prompt_lower
        )

    def test_new_character_description_stored_in_registry(self) -> None:
        """When AI returns description in new_characters, that description is stored in the registry."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Right, let's get started.", "speaker": "hagrid", "emotion": "excited"}
            ],
            "new_characters": [
                {
                    "character_id": "hagrid",
                    "name": "Rubeus Hagrid",
                    "sex": "male",
                    "age": "adult",
                    "description": "booming bass voice, thick West Country accent, warm and boisterous"
                }
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Right, let\'s get started," said Hagrid.')
        registry = self._default_registry()

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert
        char = updated_registry.get("hagrid")
        assert char is not None
        assert char.description == "booming bass voice, thick West Country accent, warm and boisterous"


# ── US-014 AC2: character_description_updates ─────────────────────────────────


class TestAISectionParserDescriptionAC2:
    """AISectionParser handles character_description_updates in the AI response (US-014 AC2)."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def _registry_with_hagrid(self) -> CharacterRegistry:
        """Return a registry that already contains Hagrid with an initial description."""
        registry = CharacterRegistry.with_default_narrator()
        registry.upsert(Character(
            character_id="hagrid",
            name="Rubeus Hagrid",
            sex="male",
            age="adult",
            description="booming bass voice, thick West Country accent",
        ))
        return registry

    def test_character_description_update_replaces_existing_description(self) -> None:
        """When AI returns character_description_updates, the character's description is replaced."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "Hagrid's voice cracked.", "emotion": "neutral"}
            ],
            "new_characters": [],
            "character_description_updates": [
                {
                    "character_id": "hagrid",
                    "description": "booming bass voice, thick West Country accent; voice trembles and cracks when distressed"
                }
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="Hagrid's voice cracked.")
        registry = self._registry_with_hagrid()

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert — description is the updated (full-replacement) value
        char = updated_registry.get("hagrid")
        assert char is not None
        assert char.description == (
            "booming bass voice, thick West Country accent; "
            "voice trembles and cracks when distressed"
        )

    def test_character_description_update_does_not_affect_other_characters(self) -> None:
        """A description update for hagrid must not change other characters."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "He left.", "emotion": "neutral"}
            ],
            "new_characters": [],
            "character_description_updates": [
                {"character_id": "hagrid", "description": "Updated voice description"}
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="He left.")
        registry = CharacterRegistry.with_default_narrator()
        registry.upsert(Character(character_id="hagrid", name="Rubeus Hagrid", description="original"))
        registry.upsert(Character(character_id="harry", name="Harry Potter", description="clear young voice"))

        # Act
        _, updated_registry = parser.parse(section, registry)

        # Assert — harry's description unchanged
        harry = updated_registry.get("harry")
        assert harry is not None
        assert harry.description == "clear young voice"

    def test_prompt_includes_existing_character_description(self) -> None:
        """When a character in the registry has a description, it must appear in the prompt."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Test text.")
        registry = CharacterRegistry.with_default_narrator()
        registry.upsert(Character(
            character_id="hagrid",
            name="Rubeus Hagrid",
            description="booming bass voice, thick West Country accent",
        ))

        # Act
        parser.parse(section, registry)

        # Assert — the description must appear in the prompt for existing characters
        assert ai_provider.last_prompt is not None
        assert "booming bass voice, thick West Country accent" in ai_provider.last_prompt

    def test_prompt_includes_character_description_updates_instruction(self) -> None:
        """The prompt must instruct the AI to return character_description_updates."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Test text.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert ai_provider.last_prompt is not None
        assert "character_description_updates" in ai_provider.last_prompt

    def test_character_description_update_for_unknown_character_is_ignored(self) -> None:
        """A description update for a character_id not in the registry is silently ignored."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "She spoke.", "emotion": "neutral"}
            ],
            "new_characters": [],
            "character_description_updates": [
                {"character_id": "unknown_char", "description": "some description"}
            ]
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="She spoke.")
        registry = self._default_registry()

        # Act / Assert — must not raise
        _, updated_registry = parser.parse(section, registry)
        assert updated_registry.get("unknown_char") is None


# ── voice settings in prompt and response parsing (US-019 Fix 3) ──────────────


class TestVoiceSettingsPromptAndParsing:
    """Tests for LLM-provided voice_stability/style/speed in AI section parser."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_prompt_includes_voice_settings_guide(self) -> None:
        """The prompt must include voice_stability/style/speed guidance for the LLM."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Hello world.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        prompt = ai_provider.last_prompt
        assert prompt is not None
        assert "voice_stability" in prompt
        assert "voice_style" in prompt
        assert "voice_speed" in prompt

    def test_parse_response_reads_voice_settings_from_segment(self) -> None:
        """_parse_response sets voice_stability/style/speed on Segment."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "I WILL DESTROY YOU!", "speaker": "villain",
                 "emotion": "furious", "voice_stability": 0.25, "voice_style": 0.60, "voice_speed": 1.05}
            ],
            "new_characters": [],
            "character_description_updates": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"I WILL DESTROY YOU!"')
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].voice_stability == 0.25
        assert segments[0].voice_style == 0.60
        assert segments[0].voice_speed == 1.05

    def test_parse_response_voice_settings_none_when_absent(self) -> None:
        """Segments without voice settings in LLM output get None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "She walked in.", "emotion": "neutral"}
            ],
            "new_characters": [],
            "character_description_updates": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="She walked in.")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert segments[0].voice_stability is None
        assert segments[0].voice_style is None
        assert segments[0].voice_speed is None


# ── US-019 Fix 4: aggressive emotional inflection splitting ───────────────────


class TestEmotionalInflectionSplitting:
    """Tests that the prompt encourages aggressive splitting at emotional inflection points."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def _get_prompt(self, text: str = "Test text.") -> str:
        """Helper: parse a section and return the prompt sent to the AI."""
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text=text)
        registry = self._default_registry()
        parser.parse(section, registry)
        assert ai_provider.last_prompt is not None
        return ai_provider.last_prompt

    def test_prompt_does_not_require_significant_shift_for_splitting(self) -> None:
        """The prompt must NOT use 'significantly' as a threshold for emotional splitting.

        The old prompt said 'if the emotional tone shifts significantly' which
        discouraged splitting at subtle inflection points. Fix 4 removes this
        high threshold.
        """
        # Act
        prompt = self._get_prompt()

        # Assert -- the word 'significantly' must not appear in the emotion splitting instruction
        assert "significantly" not in prompt.lower()

    def test_prompt_encourages_splitting_at_emotional_inflection_points(self) -> None:
        """The prompt must explicitly mention splitting at emotional inflection points."""
        # Act
        prompt = self._get_prompt()
        prompt_lower = prompt.lower()

        # Assert -- must mention inflection points or emotional shifts as split triggers
        assert "inflection" in prompt_lower or "emotional shift" in prompt_lower or "tone shift" in prompt_lower

    def test_prompt_encourages_nuanced_emotion_labels(self) -> None:
        """The prompt must encourage specific/nuanced emotion labels rather than generic ones.

        Instead of just 'angry', the prompt should guide the LLM toward labels
        like 'frustrated', 'seething', 'bitter', etc.
        """
        # Act
        prompt = self._get_prompt()
        prompt_lower = prompt.lower()

        # Assert -- must mention nuance or specificity for emotion labels
        assert ("nuanced" in prompt_lower
                or "specific" in prompt_lower
                or "precise" in prompt_lower
                or "granular" in prompt_lower)

    def test_prompt_gives_examples_of_nuanced_emotions(self) -> None:
        """The prompt must provide examples of nuanced emotion labels beyond the basic set."""
        # Act
        prompt = self._get_prompt()
        prompt_lower = prompt.lower()

        # Assert -- at least two nuanced/specific emotion examples must appear
        nuanced_examples = [
            "frustrated", "seething", "bitter", "wistful", "hesitant",
            "pleading", "contemptuous", "incredulous", "resigned", "defiant",
            "trembling", "guarded", "awed", "exasperated",
        ]
        found = [e for e in nuanced_examples if e in prompt_lower]
        assert len(found) >= 2, (
            f"Expected at least 2 nuanced emotion examples in prompt, found: {found}"
        )

    def test_prompt_mentions_mid_utterance_vocal_shifts(self) -> None:
        """The prompt must guide the LLM to split when a character's vocal delivery
        changes mid-utterance (e.g. starts calm, becomes agitated).
        """
        # Act
        prompt = self._get_prompt()
        prompt_lower = prompt.lower()

        # Assert -- must mention splitting mid-utterance or within a single line of dialogue
        assert ("mid-utterance" in prompt_lower
                or "mid-sentence" in prompt_lower
                or "within a single" in prompt_lower
                or "starts calm" in prompt_lower
                or "vocal shift" in prompt_lower)


# ── US-020: Scene detection ──────────────────────────────────────────────────


class TestSceneDetection:
    """Tests that the AI parser detects and returns scene info (US-020)."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_parse_extracts_scene_from_response(self) -> None:
        """When AI returns a 'scene' key, parser stores it as last_detected_scene."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "The cave was dark.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": [],
            "scene": {
                "environment": "cave",
                "acoustic_hints": ["echo", "confined"]
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="The cave was dark.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        scene = parser.last_detected_scene
        assert scene is not None
        assert scene.environment == "cave"
        assert scene.acoustic_hints == ["echo", "confined"]

    def test_parse_without_scene_sets_none(self) -> None:
        """When AI response has no 'scene' key, last_detected_scene is None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "Hello.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="Hello.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert parser.last_detected_scene is None

    def test_scene_id_derived_from_environment(self) -> None:
        """The scene_id is automatically derived when the AI provides environment."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "On the battlefield.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": [],
            "scene": {
                "environment": "battlefield",
                "acoustic_hints": ["loud", "open"]
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="On the battlefield.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        scene = parser.last_detected_scene
        assert scene is not None
        assert scene.scene_id  # non-empty string
        assert "battlefield" in scene.scene_id

    def test_prompt_asks_for_scene_detection(self) -> None:
        """The prompt must include instructions for scene/environment detection."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="They entered the dark cave.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        prompt = ai_provider.last_prompt
        assert prompt is not None
        prompt_lower = prompt.lower()
        assert "environment" in prompt_lower or "scene" in prompt_lower
        assert "acoustic" in prompt_lower or "setting" in prompt_lower

    def test_short_circuit_section_does_not_set_scene(self) -> None:
        """Sections with pre-resolved section_type skip AI and have no scene."""
        # Arrange
        ai_provider = MockAIProvider('should not be called')
        parser = AISectionParser(ai_provider)
        section = Section(text="[Illustration]", section_type="illustration")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        assert parser.last_detected_scene is None

    def test_parse_extracts_voice_modifiers_from_scene(self) -> None:
        """When AI returns voice_modifiers in scene, parser stores them on Scene."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "The cave was dark.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": [],
            "scene": {
                "environment": "cave",
                "acoustic_hints": ["echo", "confined"],
                "voice_modifiers": {"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90}
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="The cave was dark.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        scene = parser.last_detected_scene
        assert scene is not None
        assert scene.voice_modifiers == {
            "stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90,
        }

    def test_scene_without_voice_modifiers_gets_empty_dict(self) -> None:
        """When AI omits voice_modifiers from scene, it defaults to empty dict."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "Hello.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": [],
            "scene": {
                "environment": "indoor_quiet",
                "acoustic_hints": []
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="Hello.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        scene = parser.last_detected_scene
        assert scene is not None
        assert scene.voice_modifiers == {}

    def test_prompt_asks_for_voice_modifiers_in_scene(self) -> None:
        """The prompt must instruct the AI to provide voice_modifiers in scene."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="They entered the dark cave.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        prompt = ai_provider.last_prompt
        assert prompt is not None
        assert "voice_modifiers" in prompt
        assert "stability_delta" in prompt
        assert "style_delta" in prompt


# ── SceneRegistry threading through parse ────────────────────────────────────


class TestSceneRegistryThreading:
    """Parser accepts SceneRegistry, upserts scenes, and assigns scene_id to segments."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_parse_upserts_detected_scene_into_scene_registry(self) -> None:
        """When AI returns a scene, parse() upserts it into the SceneRegistry."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "The cave was dark.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": [],
            "scene": {
                "environment": "cave",
                "acoustic_hints": ["echo", "confined"],
                "voice_modifiers": {"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90}
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="The cave was dark.")
        char_registry = self._default_registry()
        scene_registry = SceneRegistry()

        # Act
        parser.parse(section, char_registry, scene_registry=scene_registry)

        # Assert -- scene was upserted into the mutable registry
        cave = scene_registry.get("scene_cave")
        assert cave is not None
        assert cave.environment == "cave"

    def test_parse_assigns_scene_id_to_segments(self) -> None:
        """When a scene is detected, all returned segments get its scene_id."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "The cave was dark.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0},
                {"type": "dialogue", "text": "Hello?", "speaker": "explorer", "emotion": "curious",
                 "voice_stability": 0.50, "voice_style": 0.20, "voice_speed": 1.0}
            ],
            "new_characters": [{"character_id": "explorer", "name": "Explorer"}],
            "scene": {
                "environment": "cave",
                "acoustic_hints": ["echo"]
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='The cave was dark. "Hello?"')
        char_registry = self._default_registry()
        scene_registry = SceneRegistry()

        # Act
        segments, _ = parser.parse(
            section, char_registry, scene_registry=scene_registry,
        )

        # Assert
        for seg in segments:
            assert seg.scene_id == "scene_cave"

    def test_parse_without_scene_does_not_assign_scene_id(self) -> None:
        """When AI returns no scene, segments get scene_id=None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "Hello.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="Hello.")
        char_registry = self._default_registry()
        scene_registry = SceneRegistry()

        # Act
        segments, _ = parser.parse(
            section, char_registry, scene_registry=scene_registry,
        )

        # Assert
        assert segments[0].scene_id is None

    def test_prompt_includes_existing_scenes_from_registry(self) -> None:
        """When SceneRegistry has scenes, they appear in the prompt for reuse."""
        # Arrange
        from src.domain.models import Scene
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="Back in the cave.")
        char_registry = self._default_registry()
        scene_registry = SceneRegistry()
        scene_registry.upsert(Scene(
            scene_id="scene_cave", environment="cave",
            acoustic_hints=["echo"], voice_modifiers={},
        ))

        # Act
        parser.parse(section, char_registry, scene_registry=scene_registry)

        # Assert
        prompt = ai_provider.last_prompt
        assert prompt is not None
        assert "scene_cave" in prompt
        assert "cave" in prompt

    def test_parse_backward_compatible_without_scene_registry(self) -> None:
        """parse() still works as 2-tuple when no scene_registry is passed."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "Hello.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="Hello.")
        char_registry = self._default_registry()

        # Act -- no scene_registry kwarg
        segments, updated_registry = parser.parse(section, char_registry)

        # Assert
        assert len(segments) == 1


# ── US-011: Ambient fields in scene detection ────────────────────────────────


class TestSceneAmbientFieldsParsing:
    """Parser extracts ambient_prompt and ambient_volume from AI scene response."""

    def _default_registry(self) -> CharacterRegistry:
        return CharacterRegistry.with_default_narrator()

    def test_parse_extracts_ambient_fields_from_scene(self) -> None:
        """When AI returns ambient_prompt/ambient_volume in scene, parser stores them."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "The clock ticked.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": [],
            "scene": {
                "environment": "indoor_quiet",
                "acoustic_hints": ["warm"],
                "voice_modifiers": {},
                "ambient_prompt": "quiet drawing room, clock ticking, distant servant footsteps",
                "ambient_volume": -18.0
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="The clock ticked.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        scene = parser.last_detected_scene
        assert scene is not None
        assert scene.ambient_prompt == "quiet drawing room, clock ticking, distant servant footsteps"
        assert scene.ambient_volume == -18.0

    def test_scene_without_ambient_fields_defaults_to_none(self) -> None:
        """When AI omits ambient fields from scene, they default to None."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "Hello.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": [],
            "scene": {
                "environment": "indoor_quiet",
                "acoustic_hints": [],
                "voice_modifiers": {}
            }
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="Hello.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        scene = parser.last_detected_scene
        assert scene is not None
        assert scene.ambient_prompt is None
        assert scene.ambient_volume is None

    def test_prompt_asks_for_ambient_fields(self) -> None:
        """The prompt must instruct the AI to provide ambient_prompt and ambient_volume."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="They sat by the fire.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        prompt = ai_provider.last_prompt
        assert prompt is not None
        assert "ambient_prompt" in prompt
        assert "ambient_volume" in prompt


# ── sound_effect_description extraction (US-023) ─────────────────────────────

class TestAISectionParserSoundEffectDescription:
    """Tests for sound_effect_description extraction (US-023 Cinematic Sound Effects)."""

    def _default_registry(self) -> CharacterRegistry:
        """Helper: return a registry with only the narrator."""
        return CharacterRegistry.with_default_narrator()

    def test_parse_segment_with_sound_effect_description(self) -> None:
        """Parser extracts sound_effect_description='dry cough' when AI provides it."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "She coughed loudly.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0,
                 "sound_effect_description": "dry cough"}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="She coughed loudly.")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].sound_effect_description == "dry cough"

    def test_parse_segment_with_none_sound_effect_description(self) -> None:
        """Parser accepts sound_effect_description=null from AI (evidence-based only)."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "They talked.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0,
                 "sound_effect_description": null}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="They talked.")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].sound_effect_description is None

    def test_parse_segment_without_sound_effect_description_defaults_to_none(self) -> None:
        """Parser defaults sound_effect_description to None when field is omitted."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "The door opened.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="The door opened.")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 1
        assert segments[0].sound_effect_description is None

    def test_parse_multiple_segments_with_different_sound_effect_descriptions(self) -> None:
        """Parser preserves sound_effect_description for each segment independently."""
        # Arrange
        mock_response = '''{
            "segments": [
                {"type": "narration", "text": "Thunder crashed.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0,
                 "sound_effect_description": "thunder crash"},
                {"type": "dialogue", "text": "Help!", "speaker": "alice", "emotion": "fearful",
                 "voice_stability": 0.35, "voice_style": 0.40, "voice_speed": 1.0,
                 "sound_effect_description": null},
                {"type": "narration", "text": "Rain began.", "emotion": "neutral",
                 "voice_stability": 0.65, "voice_style": 0.05, "voice_speed": 1.0,
                 "sound_effect_description": "heavy rain"}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text="Thunder crashed. Help! Rain began.")
        registry = self._default_registry()

        # Act
        segments, _ = parser.parse(section, registry)

        # Assert
        assert len(segments) == 3
        assert segments[0].sound_effect_description == "thunder crash"
        assert segments[1].sound_effect_description is None
        assert segments[2].sound_effect_description == "heavy rain"

    def test_prompt_asks_for_sound_effect_description(self) -> None:
        """The prompt must instruct the AI to provide sound_effect_description for explicit actions."""
        # Arrange
        ai_provider = MockAIProvider('{"segments": [], "new_characters": []}')
        parser = AISectionParser(ai_provider)
        section = Section(text="She coughed.")
        registry = self._default_registry()

        # Act
        parser.parse(section, registry)

        # Assert
        prompt = ai_provider.last_prompt
        assert prompt is not None
        # Prompt should mention sound effects or narrative descriptions
        assert "sound" in prompt.lower() or "effect" in prompt.lower() or "knock" in prompt.lower()


class TestJSONRepairFunction:
    """Tests for the _repair_json function."""

    def _default_registry(self) -> CharacterRegistry:
        """Helper: return a registry with only the narrator."""
        return CharacterRegistry.with_default_narrator()

    def test_repair_json_with_broken_newlines_in_strings(self):
        """Repair function handles raw newlines/tabs inside string values."""
        # Arrange
        from src.parsers.ai_section_parser import _repair_json
        broken_json = '''{
            "segments": [
                {"type": "dialogue", "text": "Line one
and line two", "speaker": "alice"}
            ]
        }'''

        # Act
        repaired = _repair_json(broken_json)

        # Assert
        import json
        data = json.loads(repaired)
        assert len(data["segments"]) == 1
        # Newlines should be escaped or the string properly formatted
        assert "alice" in repaired

    def test_repair_json_with_trailing_commas(self):
        """Repair function handles trailing commas before ] or }."""
        # Arrange
        from src.parsers.ai_section_parser import _repair_json
        broken_json = '''{
            "segments": [
                {"type": "dialogue", "text": "Hello", "speaker": "alice",},
            ],
            "new_characters": []
        }'''

        # Act
        repaired = _repair_json(broken_json)

        # Assert
        import json
        data = json.loads(repaired)
        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "Hello"

    def test_repair_json_with_truncated_string(self):
        """Repair function handles truncated strings (unclosed quotes)."""
        # Arrange
        from src.parsers.ai_section_parser import _repair_json
        # Simpler case: unclosed quote in a string value at end of JSON
        broken_json = '{"segments": [], "note": "incomplete'

        # Act
        repaired = _repair_json(broken_json)

        # Assert
        # Should return a string (type guaranteed by function signature)
        assert isinstance(repaired, str)
        # And should be parseable as JSON (repair closes unterminated strings and brackets)
        import json
        data = json.loads(repaired)
        assert isinstance(data, dict)

    def test_repair_json_passes_through_valid_json(self):
        """Repair function returns valid JSON unchanged."""
        # Arrange
        from src.parsers.ai_section_parser import _repair_json
        valid_json = '''{
            "segments": [
                {"type": "dialogue", "text": "Hello", "speaker": "alice"}
            ],
            "new_characters": []
        }'''

        # Act
        repaired = _repair_json(valid_json)

        # Assert
        import json
        original_data = json.loads(valid_json)
        repaired_data = json.loads(repaired)
        assert original_data == repaired_data

    def test_parse_uses_repair_json_on_json_decode_error(self):
        """Parse uses _repair_json when json.loads fails initially."""
        # Arrange - return broken JSON that can be repaired by removing trailing commas
        mock_response = '''{
            "segments": [
                {"type": "dialogue", "text": "Hello", "speaker": "alice",}
            ],
            "new_characters": []
        }'''
        ai_provider = MockAIProvider(mock_response)
        parser = AISectionParser(ai_provider)
        section = Section(text='"Hello," said Alice.')
        registry = self._default_registry()

        # Act
        segments, updated_registry = parser.parse(section, registry)

        # Assert
        # Should successfully parse despite the broken JSON
        assert len(segments) == 1
        assert segments[0].text == "Hello"
        assert segments[0].character_id == "alice"
