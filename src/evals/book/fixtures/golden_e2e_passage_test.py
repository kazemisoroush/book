"""Tests for GoldenE2EPassage dataclass and the dracula_arrival golden passage.

Tests:
- dracula_arrival passage has all required fields non-empty
- dracula_arrival expected_features contains at least 6 features
- dracula_arrival gutenberg_url points to Dracula on Project Gutenberg (reference-only)
- dracula_arrival has embedded sections (non-empty strings, 150-250 words total)
- dracula_arrival has author, chapter_number, chapter_title fields
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

    def test_author_is_non_empty_string(self) -> None:
        assert isinstance(dracula_arrival.author, str) and len(dracula_arrival.author) > 0

    def test_gutenberg_url_points_to_dracula(self) -> None:
        assert "gutenberg.org" in dracula_arrival.gutenberg_url
        # Dracula is Gutenberg text #345
        assert "345" in dracula_arrival.gutenberg_url

    def test_chapter_number_is_positive_int(self) -> None:
        assert isinstance(dracula_arrival.chapter_number, int)
        assert dracula_arrival.chapter_number >= 1

    def test_chapter_title_is_non_empty_string(self) -> None:
        assert isinstance(dracula_arrival.chapter_title, str) and len(dracula_arrival.chapter_title) > 0

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


class TestGoldenE2EPassageSections:
    """Validate the embedded passage sections."""

    def test_sections_is_non_empty_list(self) -> None:
        assert isinstance(dracula_arrival.sections, list)
        assert len(dracula_arrival.sections) >= 1

    def test_each_section_is_non_empty_string(self) -> None:
        for section in dracula_arrival.sections:
            assert isinstance(section, str) and len(section.strip()) > 0

    def test_total_word_count_between_150_and_250(self) -> None:
        total_text = " ".join(dracula_arrival.sections)
        word_count = len(total_text.split())
        assert 150 <= word_count <= 250, (
            f"Expected 150-250 words, got {word_count}"
        )

    def test_sections_contain_dialogue(self) -> None:
        """At least one section must contain a speech-marking character."""
        all_text = " ".join(dracula_arrival.sections)
        # Dialogue is signalled by quotation marks
        has_dialogue = '"' in all_text or "\u201c" in all_text or "'" in all_text
        assert has_dialogue, "Passage sections must contain dialogue"

    def test_has_at_least_two_sections(self) -> None:
        """The passage should have at least 2 paragraphs for context variety."""
        assert len(dracula_arrival.sections) >= 2


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
