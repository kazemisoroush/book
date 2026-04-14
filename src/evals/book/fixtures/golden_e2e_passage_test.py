"""Tests for GoldenE2EPassage dataclass and the dracula_arrival golden passage.

Tests:
- dracula_arrival passage has all required fields non-empty
- dracula_arrival expected_features contains at least 6 features
- dracula_arrival start_chapter and end_chapter are valid positive ints
- dracula_arrival gutenberg_url points to Dracula on Project Gutenberg
- ALL_E2E_PASSAGES registry lookup works by name
- GoldenE2EPassage is hashable (frozen dataclass)
"""

import pytest
from src.evals.book.fixtures.golden_e2e_passage import ALL_E2E_PASSAGES, dracula_arrival


class TestGoldenE2EPassageFields:
    """Validate the dracula_arrival passage has well-formed, non-empty fields."""

    def test_name_is_non_empty_string(self) -> None:
        assert isinstance(dracula_arrival.name, str) and len(dracula_arrival.name) > 0

    def test_book_title_is_non_empty_string(self) -> None:
        assert isinstance(dracula_arrival.book_title, str) and len(dracula_arrival.book_title) > 0

    def test_gutenberg_url_points_to_dracula(self) -> None:
        assert "gutenberg.org" in dracula_arrival.gutenberg_url
        # Dracula is Gutenberg text #345
        assert "345" in dracula_arrival.gutenberg_url

    def test_start_chapter_is_positive_int(self) -> None:
        assert isinstance(dracula_arrival.start_chapter, int)
        assert dracula_arrival.start_chapter >= 1

    def test_end_chapter_is_positive_int(self) -> None:
        assert isinstance(dracula_arrival.end_chapter, int)
        assert dracula_arrival.end_chapter >= 1

    def test_end_chapter_gte_start_chapter(self) -> None:
        assert dracula_arrival.end_chapter >= dracula_arrival.start_chapter

    def test_expected_features_has_at_least_six(self) -> None:
        assert len(dracula_arrival.expected_features) >= 6

    def test_notes_is_non_empty_string(self) -> None:
        assert isinstance(dracula_arrival.notes, str) and len(dracula_arrival.notes) > 0


class TestGoldenE2EPassageAudioFeatures:
    """Validate expected audio features cover all required categories."""

    def test_dialogue_feature_present(self) -> None:
        assert "dialogue" in dracula_arrival.expected_features

    def test_narration_feature_present(self) -> None:
        assert "narration" in dracula_arrival.expected_features

    def test_sfx_or_sound_effects_present(self) -> None:
        features = dracula_arrival.expected_features
        assert any("sfx" in f or "sound" in f for f in features)


class TestAllE2EPassagesRegistry:
    """Validate ALL_E2E_PASSAGES registry contains at least one passage."""

    def test_registry_has_at_least_one_passage(self) -> None:
        assert len(ALL_E2E_PASSAGES) >= 1

    def test_registry_contains_dracula_arrival(self) -> None:
        names = [p.name for p in ALL_E2E_PASSAGES]
        assert "dracula_arrival" in names

    def test_registry_lookup_by_name(self) -> None:
        passage = next((p for p in ALL_E2E_PASSAGES if p.name == "dracula_arrival"), None)
        assert passage is not None
        assert passage.book_title == dracula_arrival.book_title

    def test_frozen_dataclass_is_immutable(self) -> None:
        # frozen=True means attributes cannot be reassigned
        with pytest.raises(AttributeError):
            dracula_arrival.name = "other"  # type: ignore[misc]
