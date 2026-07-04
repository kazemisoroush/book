"""Tests for SectionCoverageValidator: every section must appear in the beats."""
from src.domain.beat import Beat, BeatType
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.validators.normalizers.lowercase_normalizer import LowercaseNormalizer
from src.validators.normalizers.punctuation_normalizer import PunctuationNormalizer
from src.validators.normalizers.whitespace_normalizer import WhitespaceNormalizer
from src.validators.section_coverage_validator import SectionCoverageValidator

_NORMALIZERS = [PunctuationNormalizer(), WhitespaceNormalizer(), LowercaseNormalizer()]


def _validator(**kwargs) -> SectionCoverageValidator:
    return SectionCoverageValidator(_NORMALIZERS, **kwargs)


def _meta() -> BookMetadata:
    return BookMetadata(
        title="The Gambler", author="Fyodor Dostoyevsky",
        releaseDate=None, language=None, originalPublication=None, credits=None,
    )


def _input_book(section_texts: list[str]) -> Book:
    chapter = Chapter(
        number=1, title="",
        sections=[Section(text=t) for t in section_texts],
    )
    return Book(metadata=_meta(), content=BookContent(chapters=[chapter]))


def _output_book(beat_texts: list[str]) -> Book:
    chapter = Chapter(number=1, title="", sections=[])
    chapter.beats = [
        Beat(text=t, beat_type=BeatType.NARRATION, character_id=1) for t in beat_texts
    ]
    return Book(metadata=_meta(), content=BookContent(chapters=[chapter]))


def test_all_sections_present_passes():
    # Arrange
    sections = ["The general frowned.", "Farewell, said Alexei."]
    inp = _input_book(sections)
    out = _output_book(["The general frowned.", "Farewell,", "said Alexei."])

    # Act
    result = _validator().validate(inp, out)

    # Assert
    assert result.deviation == 0.0
    assert result.passed


def test_dropped_section_fails_and_is_named():
    # Arrange
    sections = [
        "De Grieux stamped his foot with vexation and hastened away.",
        "Stop her, whispered the general.",
    ]
    inp = _input_book(sections)
    # the first section is missing from the beats entirely
    out = _output_book(["Stop her, whispered the general."])

    # Act
    result = _validator().validate(inp, out)

    # Assert
    assert not result.passed
    assert result.deviation > 0.0
    assert "stamped his foot" in result.detail.lower()


def test_reworded_section_is_not_flagged():
    # Arrange
    sections = ["Farewell Mlle. Blanche, I remarked."]
    inp = _input_book(sections)
    # the model expanded the abbreviation but kept the sentence
    out = _output_book(["Farewell Mademoiselle Blanche, I remarked."])

    # Act
    result = _validator().validate(inp, out)

    # Assert
    assert result.passed


def test_skip_types_sections_are_ignored():
    # Arrange
    chapter = Chapter(
        number=1, title="",
        sections=[
            Section(text="Chapter Two.", section_type="chapter_announcement"),
            Section(text="The old lady arrived."),
        ],
    )
    inp = Book(metadata=_meta(), content=BookContent(chapters=[chapter]))
    out = _output_book(["The old lady arrived."])

    # Act
    result = _validator(
        skip_types={"chapter_announcement"},
    ).validate(inp, out)

    # Assert
    assert result.passed


def test_tolerant_threshold_lets_a_small_drop_pass():
    # Arrange
    sections = [
        "De Grieux stamped his foot with vexation and hastened away.",
        "Stop her, whispered the general.",
    ]
    inp = _input_book(sections)
    out = _output_book(["Stop her, whispered the general."])

    # Act
    strict = _validator().validate(inp, out)
    tolerant = _validator(threshold=0.9).validate(inp, out)

    # Assert
    assert not strict.passed
    assert tolerant.passed
    assert tolerant.deviation == strict.deviation


def test_no_sections_passes():
    # Arrange
    inp = _input_book([])
    out = _output_book([])

    # Act
    result = _validator().validate(inp, out)

    # Assert
    assert result.passed
