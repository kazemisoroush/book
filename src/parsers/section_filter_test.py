"""Tests for SectionFilter — junk section filtering (US-007).

Tests are written BEFORE implementation (TDD, red phase).
"""
from src.parsers.section_filter import SectionFilter
from src.domain.models import Section


class TestSectionFilterPageNumbers:
    """SectionFilter removes page number artifact sections entirely."""

    def test_page_number_artifact_single_digit_is_removed(self) -> None:
        """A section whose text is '{6}' is dropped entirely."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="{6}")])

        # Assert
        assert result == []

    def test_page_number_artifact_two_digits_is_removed(self) -> None:
        """A section whose text is '{12}' is dropped entirely."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="{12}")])

        # Assert
        assert result == []

    def test_page_number_artifact_three_digits_is_removed(self) -> None:
        """A section whose text is '{123}' is dropped entirely."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="{123}")])

        # Assert
        assert result == []

    def test_page_number_with_surrounding_whitespace_is_removed(self) -> None:
        """A section with text '  {6}  ' (whitespace around) is dropped."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="  {6}  ")])

        # Assert
        assert result == []

    def test_normal_text_with_braces_is_kept(self) -> None:
        """Text that contains braces but is not a page number artifact is kept."""
        # Arrange
        f = SectionFilter()
        sections = [Section(text="He said {hello} there.")]

        # Act
        result = f.filter(sections)

        # Assert
        assert len(result) == 1

    def test_multiple_page_number_artifacts_all_removed(self) -> None:
        """Multiple page number sections are all removed."""
        # Arrange
        f = SectionFilter()
        sections = [Section(text="{1}"), Section(text="{2}"), Section(text="{100}")]

        # Act
        result = f.filter(sections)

        # Assert
        assert result == []


class TestSectionFilterCopyright:
    """SectionFilter removes in-page copyright block sections entirely."""

    def test_copyright_block_is_removed(self) -> None:
        """A section matching '[Copyright 1894 by George Allen. ]' is dropped."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="[Copyright 1894 by George Allen. ]")])

        # Assert
        assert result == []

    def test_copyright_block_short_form_is_removed(self) -> None:
        """A section matching '[Copyright 2020]' is dropped."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="[Copyright 2020]")])

        # Assert
        assert result == []

    def test_copyright_block_multiword_is_removed(self) -> None:
        """Copyright block with extra words is removed."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="[Copyright 1894 by Publisher Inc.]")])

        # Assert
        assert result == []

    def test_non_copyright_bracket_text_is_kept(self) -> None:
        """Text like '[Illustration: A painting]' is NOT a copyright block."""
        # Arrange
        f = SectionFilter()
        sections = [Section(text="[Illustration: A painting]")]

        # Act
        result = f.filter(sections)

        # Assert
        assert len(result) == 1

    def test_copyright_in_prose_context_is_not_removed(self) -> None:
        """Plain text mentioning 'copyright' without bracket format is kept."""
        # Arrange
        f = SectionFilter()
        sections = [Section(text="This book is copyright protected.")]

        # Act
        result = f.filter(sections)

        # Assert
        assert len(result) == 1


class TestSectionFilterIllustrationCaptions:
    """SectionFilter keeps illustration captions but tags them as illustration."""

    def test_mr_and_mrs_bennet_pattern_is_kept(self) -> None:
        """The Pride and Prejudice caption 'Mr. & Mrs. Bennet' is kept (not discarded)."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="Mr. & Mrs. Bennet")])

        # Assert
        assert len(result) == 1

    def test_mr_and_mrs_bennet_pattern_tagged_illustration(self) -> None:
        """'Mr. & Mrs. Bennet' is tagged with section_type='illustration'."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="Mr. & Mrs. Bennet")])

        # Assert
        assert result[0].section_type == "illustration"

    def test_illustration_caption_amp_pattern_tagged(self) -> None:
        """Pattern 'Word & Word' (short, two-word with &) is tagged as illustration."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="Sir & Lady Fitzwilliam")])

        # Assert
        assert len(result) == 1
        assert result[0].section_type == "illustration"

    def test_long_text_with_ampersand_is_not_tagged_illustration(self) -> None:
        """A long prose line with & is not tagged as illustration caption."""
        # Arrange
        f = SectionFilter()
        long_text = "It was a truth universally acknowledged that Mr. Bennet & his family were well established in the neighbourhood."  # noqa: E501

        # Act
        result = f.filter([Section(text=long_text)])

        # Assert
        assert len(result) == 1
        assert result[0].section_type is None

    def test_illustration_caption_section_text_preserved(self) -> None:
        """Illustration caption section retains its original text."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="Mr. & Mrs. Bennet")])

        # Assert
        assert result[0].text == "Mr. & Mrs. Bennet"

    def test_illustration_caption_section_not_discarded(self) -> None:
        """Illustration captions appear in the output (not discarded like page numbers)."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="Mr. & Mrs. Bennet")])

        # Assert
        assert len(result) == 1  # kept, not discarded


class TestSectionFilterMixed:
    """SectionFilter applied to mixed lists of sections."""

    def test_normal_sections_pass_through_unchanged(self) -> None:
        """Normal prose sections are returned unchanged with section_type=None."""
        # Arrange
        f = SectionFilter()
        sections = [
            Section(text="It is a truth universally acknowledged."),
            Section(text="She was a woman of mean understanding."),
        ]

        # Act
        result = f.filter(sections)

        # Assert
        assert len(result) == 2
        for s in result:
            assert s.section_type is None

    def test_mixed_list_filters_junk_keeps_prose_and_illustrations(self) -> None:
        """Mixed list: page number dropped, copyright dropped, caption kept, prose kept."""
        # Arrange
        f = SectionFilter()
        sections = [
            Section(text="It is a truth universally acknowledged."),
            Section(text="{6}"),
            Section(text="[Copyright 1894 by George Allen. ]"),
            Section(text="Mr. & Mrs. Bennet"),
            Section(text="She was a woman of mean understanding."),
        ]

        # Act
        result = f.filter(sections)

        # Assert
        assert len(result) == 3
        assert result[0].text == "It is a truth universally acknowledged."
        assert result[1].text == "Mr. & Mrs. Bennet"
        assert result[1].section_type == "illustration"
        assert result[2].text == "She was a woman of mean understanding."

    def test_empty_list_returns_empty_list(self) -> None:
        """filter([]) returns []."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([])

        # Assert
        assert result == []

    def test_already_tagged_illustration_section_passes_through(self) -> None:
        """A section already tagged section_type='illustration' is passed through unchanged."""
        # Arrange
        f = SectionFilter()
        section = Section(text="Some caption", section_type="illustration")

        # Act
        result = f.filter([section])

        # Assert
        assert len(result) == 1
        assert result[0].section_type == "illustration"

    def test_filter_does_not_mutate_input_list(self) -> None:
        """filter() returns a new list; the original list is not modified."""
        # Arrange
        f = SectionFilter()
        original = [Section(text="{6}"), Section(text="Normal text.")]

        # Act
        result = f.filter(original)

        # Assert
        assert len(original) == 2  # original unchanged
        assert len(result) == 1

    def test_filter_returns_list_type(self) -> None:
        """filter() return type is list."""
        # Arrange
        f = SectionFilter()

        # Act
        result = f.filter([Section(text="Normal.")])

        # Assert
        assert isinstance(result, list)
