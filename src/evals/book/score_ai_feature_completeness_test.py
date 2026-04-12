"""Unit tests for score_ai_feature_completeness (EV-006).

These tests verify:
  - The feature-rich golden passage expects 'chapter_announcement' type
  - The scorer's scoring logic correctly identifies present / absent types
    without calling the real AI (parser is stubbed via monkeypatch)

The scorer calls the real LLM at integration time — those calls are
excluded here because they are expensive (paid API).
"""
from unittest.mock import MagicMock

from src.domain.models import (
    CharacterRegistry,
    SceneRegistry,
    Section,
    Segment,
    SegmentType,
)
from src.evals.fixtures.golden_feature_passages import (
    GoldenFeaturePassage,
    PASSAGE_FEATURE_RICH,
)
from src.evals.book.score_ai_feature_completeness import _run_passage
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.prompt_builder import PromptBuilder


def _make_stub_parser(segments: list[Segment]) -> AISectionParser:
    """Return an AISectionParser whose parse() returns the given segments."""
    ai_provider = MagicMock()
    parser = AISectionParser(ai_provider, prompt_builder=PromptBuilder())

    def _fake_parse(
        section: Section,
        registry: CharacterRegistry,
        context_window: object = None,
        *,
        scene_registry: SceneRegistry | None = None,
    ) -> tuple[list[Segment], CharacterRegistry]:
        return segments, registry

    parser.parse = _fake_parse  # type: ignore[method-assign]
    return parser


class TestFeatureRichPassageExpectsNewTypes:
    """The feature-rich golden passage must declare chapter_announcement."""

    def test_feature_rich_expects_chapter_announcement_type(self) -> None:
        """PASSAGE_FEATURE_RICH must list 'chapter_announcement' in expected_segment_types."""
        # Arrange / Act / Assert
        assert "chapter_announcement" in PASSAGE_FEATURE_RICH.expected_segment_types


class TestScorerRecallLogic:
    """_run_passage scores segment types correctly against stub parser output."""

    def test_scorer_passes_when_expected_type_present(self) -> None:
        """Recall check passes when the expected segment type appears in output."""
        # Arrange
        segments = [
            Segment(text="Chapter One.", segment_type=SegmentType.CHAPTER_ANNOUNCEMENT, character_id="narrator"),
            Segment(text="It began.", segment_type=SegmentType.NARRATION, character_id="narrator"),
        ]
        passage = GoldenFeaturePassage(
            name="test_passage",
            text="Chapter One. It began.",
            book_title="Test Book",
            book_author="Test Author",
            expected_segment_types=["chapter_announcement", "narration"],
        )
        parser = _make_stub_parser(segments)

        # Act
        results = _run_passage(parser, passage)

        # Assert — both recall checks must PASS (True)
        recall_by_tag = {tag: ok for tag, _, ok in results["recall"]}
        assert recall_by_tag["type-chapter_announcement"] is True
        assert recall_by_tag["type-narration"] is True

    def test_scorer_fails_when_expected_type_absent(self) -> None:
        """Recall check fails when the expected segment type is missing from output."""
        # Arrange
        segments = [
            Segment(text="It was quiet.", segment_type=SegmentType.NARRATION, character_id="narrator"),
        ]
        passage = GoldenFeaturePassage(
            name="test_passage",
            text="It was quiet.",
            book_title="Test Book",
            book_author="Test Author",
            expected_segment_types=["chapter_announcement"],
        )
        parser = _make_stub_parser(segments)

        # Act
        results = _run_passage(parser, passage)

        # Assert — chapter_announcement recall check must FAIL (False)
        recall_by_tag = {tag: ok for tag, _, ok in results["recall"]}
        assert recall_by_tag["type-chapter_announcement"] is False
