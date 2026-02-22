"""Tests for text book parser."""
import json
import pytest
from pathlib import Path
from unittest.mock import Mock
from .text_parser import TextBookParser
from ..domain.models import SegmentType
from ..character_registry import CharacterRegistry


class TestTextBookParser:
    """Tests for TextBookParser."""

    @pytest.fixture
    def parser(self):
        return TextBookParser()

    def test_parse_paragraph_with_dialogue(self, parser):
        paragraph = 'He walked in. "Hello there," said John. She smiled.'

        segments = parser._parse_paragraph(paragraph)

        assert len(segments) == 3
        assert segments[0].is_narration()
        assert segments[0].text == "He walked in."

        assert segments[1].is_dialogue()
        assert segments[1].text == "Hello there,"
        assert segments[1].speaker == "John"

        # Attribution "said John." is kept as narration (everything must be in audio)
        assert segments[2].is_narration()
        assert segments[2].text == "said John. She smiled."

    def test_parse_paragraph_narration_only(self, parser):
        paragraph = "It was a beautiful day. The sun shone brightly."

        segments = parser._parse_paragraph(paragraph)

        assert len(segments) == 1
        assert segments[0].is_narration()
        assert segments[0].text == paragraph

    def test_extract_speaker_after_dialogue(self, parser):
        paragraph = '"Hello there," said Mr. Smith to his friend.'

        segments = parser._parse_paragraph(paragraph)

        assert len(segments) == 2
        assert segments[0].is_dialogue()
        assert segments[0].speaker == "Smith"

    def test_extract_speaker_before_dialogue(self, parser):
        paragraph = 'John replied, "I am well, thank you."'

        segments = parser._parse_paragraph(paragraph)

        dialogue_segments = [s for s in segments if s.is_dialogue()]
        assert len(dialogue_segments) == 1
        assert dialogue_segments[0].speaker == "John"

    def test_dialogue_split_by_attribution_keeps_full_text(self, parser):
        # Test case from Pride and Prejudice - everything must be in the audio
        paragraph = '"My dear Mr. Bennet," said his lady to him one day, "have you heard that Netherfield Park is let at last?"'

        segments = parser._parse_paragraph(paragraph)

        # Should have 3 segments: dialogue, narration (attribution), dialogue
        assert len(segments) == 3

        # First dialogue
        assert segments[0].is_dialogue()
        assert segments[0].text == "My dear Mr. Bennet,"
        assert segments[0].speaker == "lady"

        # Attribution as narration - MUST include full text
        assert segments[1].is_narration()
        assert "said his lady to him one day" in segments[1].text
        # Should not be missing parts
        assert "said" in segments[1].text
        assert "his lady" in segments[1].text

        # Second dialogue
        assert segments[2].is_dialogue()
        assert segments[2].text == "have you heard that Netherfield Park is let at last?"
        assert segments[2].speaker == "lady"

    def test_normalize_speaker_name(self, parser):
        assert parser._normalize_speaker_name("Mr. Bennet") == "Bennet"
        assert parser._normalize_speaker_name("Mrs. Smith") == "Smith"
        assert parser._normalize_speaker_name("Lady Catherine") == "Catherine"
        assert parser._normalize_speaker_name("his wife") == "wife"

    def test_roman_to_int(self, parser):
        assert parser._roman_to_int("I") == 1
        assert parser._roman_to_int("IV") == 4
        assert parser._roman_to_int("IX") == 9
        assert parser._roman_to_int("XLII") == 42
        assert parser._roman_to_int("99") == 99

    def test_empty_or_whitespace_dialogue_filtered(self, parser):
        # Test that dialogue with only whitespace and punctuation is filtered out
        # This happens in corrupted book files where dialogue text is missing
        paragraph = 'Text before. "    ," said someone, "actual dialogue here."'

        segments = parser._parse_paragraph(paragraph)

        # Should not have meaningless dialogue (only whitespace + punctuation)
        dialogue_segments = [s for s in segments if s.is_dialogue()]

        for seg in dialogue_segments:
            # Remove whitespace and common punctuation
            meaningful = seg.text.strip().strip('.,;:!?"\'-')
            assert meaningful, f"Meaningless dialogue segment found: {repr(seg.text)}"

    def test_quoted_phrase_without_attribution_stays_narration(self, parser):
        # Quotes without speaker attribution should be treated as narration
        # Example: book titles, phrases, references
        paragraph = 'Walt Whitman has a distinction between "loving by allowance" and "loving with personal love." This applies to books.'

        segments = parser._parse_paragraph(paragraph)

        # Should be treated as narration only since there's no dialogue attribution
        assert len(segments) == 1
        assert segments[0].is_narration()
        # Quotes should be preserved in the text
        assert '"loving by allowance"' in segments[0].text
        assert '"loving with personal love."' in segments[0].text

    def test_parse_real_book(self, parser):
        book_path = Path("/workspaces/book/books/pg1342.txt")

        if book_path.exists():
            book = parser.parse(str(book_path))

            assert book.title == "Pride and Prejudice"
            assert book.author == "Jane Austen"
            assert len(book.chapters) > 1

            # Check first chapter is preface (chapter 0)
            preface = book.chapters[0]
            assert preface.number == 0
            assert preface.title == "Preface"
            assert len(preface.segments) > 0

            # Check second chapter is chapter 1 with dialogue
            first_chapter = book.chapters[1]
            assert first_chapter.number == 1
            assert len(first_chapter.segments) > 0

            # Should have both narration and dialogue
            has_narration = any(s.is_narration() for s in first_chapter.segments)
            has_dialogue = any(s.is_dialogue() for s in first_chapter.segments)
            assert has_narration
            assert has_dialogue

    def test_parse_with_character_registry_identifies_speakers(self):
        """Test parser uses character registry to identify speakers."""
        # Create mock AI provider
        mock_ai = Mock()

        # Mock AI response for "his lady"
        mock_ai.generate.return_value = json.dumps({
            "speaker": "Mrs. Bennet",
            "registry": {
                "Mrs. Bennet": {
                    "aliases": ["Mrs. Bennet", "his lady", "lady"],
                    "context": "Married to Mr. Bennet. Mother of five daughters.",
                    "first_seen_chapter": 1
                }
            }
        })

        # Create registry with AI
        registry = CharacterRegistry(ai_provider=mock_ai)

        # Create parser with registry
        parser = TextBookParser(character_registry=registry)

        # Parse paragraph with "his lady"
        paragraph = '"My dear," said his lady to him one day.'
        segments = parser._parse_paragraph(paragraph)

        # Should identify speaker as "Mrs. Bennet" via registry
        dialogue_segments = [s for s in segments if s.is_dialogue()]
        assert len(dialogue_segments) == 1
        assert dialogue_segments[0].speaker == "Mrs. Bennet"

        # AI should have been called
        mock_ai.generate.assert_called_once()

    def test_parse_with_character_registry_uses_fast_path(self):
        """Test parser uses registry fast path for known speakers."""
        # Create mock AI provider
        mock_ai = Mock()

        # Create registry with AI
        registry = CharacterRegistry(ai_provider=mock_ai)

        # Pre-populate registry
        registry.characters["Mrs. Bennet"] = type('Character', (), {
            'canonical_name': 'Mrs. Bennet',
            'aliases': ['Mrs. Bennet', 'his lady', 'lady'],
            'context': 'Mother',
            'first_seen_chapter': 1
        })()

        # Create parser with registry
        parser = TextBookParser(character_registry=registry)

        # Parse paragraph with known alias
        paragraph = '"Hello," said his lady.'
        segments = parser._parse_paragraph(paragraph)

        # Should use fast path (no AI call)
        dialogue_segments = [s for s in segments if s.is_dialogue()]
        assert len(dialogue_segments) == 1
        assert dialogue_segments[0].speaker == "Mrs. Bennet"

        # AI should NOT have been called (fast path)
        mock_ai.generate.assert_not_called()
