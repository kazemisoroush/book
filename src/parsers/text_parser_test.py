"""Tests for text book parser."""
import pytest
from pathlib import Path
from .text_parser import TextBookParser
from ..domain.models import SegmentType


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

        assert segments[2].is_narration()
        assert segments[2].text == "She smiled."

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
