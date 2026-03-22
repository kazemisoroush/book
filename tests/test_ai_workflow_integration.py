"""Integration test for the AI workflow — chapter 1 of Pride and Prejudice.

Uses the local HTML fixture at books/1342/pg1342-images.html (already
downloaded — no network call to Gutenberg).  Calls the real AWS Bedrock
provider, so this test requires valid credentials and incurs API cost.

Run explicitly:
    pytest tests/test_ai_workflow_integration.py -v

The test is marked ``integration`` so it can be excluded from the default
unit-test run:
    pytest -m "not integration"
"""
import json
import os
import pytest

from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.parsers.ai_section_parser import AISectionParser
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config.config import Config
from src.domain.models import Book, EmphasisSpan

_HTML_PATH = "books/1342/pg1342-images.html"
_CHAPTER_LIMIT = 1


@pytest.fixture(scope="module")
def book_dict() -> dict:
    """Parse chapter 1 of Pride and Prejudice through the full AI pipeline."""
    if not os.path.exists(_HTML_PATH):
        pytest.skip(f"Local HTML fixture not found: {_HTML_PATH}")

    with open(_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    metadata = StaticProjectGutenbergHTMLMetadataParser().parse(html)
    content = StaticProjectGutenbergHTMLContentParser().parse(html)

    section_parser = AISectionParser(AWSBedrockProvider(Config.from_env()))

    for section in content.chapters[0].sections:
        try:
            section.segments = section_parser.parse(section)
        except Exception:
            pass  # leave segments=None on transient AI failures

    content.chapters = content.chapters[:_CHAPTER_LIMIT]
    return Book(metadata=metadata, content=content).to_dict()


@pytest.mark.integration
class TestAIWorkflowChapter1:

    def test_metadata_title(self, book_dict: dict) -> None:
        assert book_dict["metadata"]["title"] == "Pride and Prejudice"

    def test_metadata_author(self, book_dict: dict) -> None:
        assert "Austen" in book_dict["metadata"]["author"]

    def test_exactly_one_chapter(self, book_dict: dict) -> None:
        assert len(book_dict["content"]["chapters"]) == 1

    def test_chapter_has_sections(self, book_dict: dict) -> None:
        assert len(book_dict["content"]["chapters"][0]["sections"]) > 0

    def test_sections_have_segment_lists(self, book_dict: dict) -> None:
        """Most sections should have been segmented by the AI."""
        sections = book_dict["content"]["chapters"][0]["sections"]
        segmented = [s for s in sections if s.get("segments") is not None]
        # Allow up to 2 transient AI failures out of all sections
        assert len(segmented) >= len(sections) - 2

    def test_no_word_merge_in_any_section(self, book_dict: dict) -> None:
        """No section text should contain words merged without a space (e.g. 'Youwant')."""
        sections = book_dict["content"]["chapters"][0]["sections"]
        for sec in sections:
            text = sec["text"]
            # Every transition from lowercase to uppercase mid-word is suspicious.
            # The known culprit: <i>You</i>want → 'Youwant'
            assert "Youwant" not in text, f"Word merge detected: {text!r}"

    def test_you_want_section_text_is_correct(self, book_dict: dict) -> None:
        """The '<i>You</i> want' line must be parsed as 'You want' (space preserved)."""
        sections = book_dict["content"]["chapters"][0]["sections"]
        matches = [s for s in sections if "want to tell me" in s["text"]]
        assert matches, "Could not find 'want to tell me' section"
        assert matches[0]["text"].startswith("\u201cYou want"), (
            f"Expected '\"You want ...', got: {matches[0]['text']!r}"
        )

    def test_you_want_section_has_emphasis(self, book_dict: dict) -> None:
        """The 'You' in 'You want to tell me' must have an EmphasisSpan."""
        sections = book_dict["content"]["chapters"][0]["sections"]
        matches = [s for s in sections if "want to tell me" in s["text"]]
        assert matches
        emphases = matches[0]["emphases"]
        assert len(emphases) == 1
        assert emphases[0]["kind"] == "i"
        # 'You' sits at offset 1 (after the opening curly-quote)
        assert emphases[0]["start"] == 1
        assert emphases[0]["end"] == 4

    def test_section_emphases_are_lists(self, book_dict: dict) -> None:
        """Every section must have an 'emphases' key that is a list."""
        sections = book_dict["content"]["chapters"][0]["sections"]
        for sec in sections:
            assert isinstance(sec.get("emphases"), list), (
                f"Section missing emphases list: {sec['text'][:60]!r}"
            )

    def test_segments_have_no_emphases_field(self, book_dict: dict) -> None:
        """Segments must not carry an 'emphases' key (removed as unused)."""
        sections = book_dict["content"]["chapters"][0]["sections"]
        for sec in sections:
            for seg in sec.get("segments") or []:
                assert "emphases" not in seg, (
                    f"Unexpected emphases on segment: {seg}"
                )
