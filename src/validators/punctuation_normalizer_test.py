"""Tests for PunctuationNormalizer."""
from src.validators.punctuation_normalizer import PunctuationNormalizer


def test_removes_ascii_punctuation():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("Hello, world! How are you?")

    # Assert
    assert result == "Hello world How are you"


def test_removes_curly_quotes():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("“My dear Mr. Bennet,” said she.")

    # Assert
    assert result == "My dear Mr Bennet said she"


def test_removes_em_and_en_dashes():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("Here—take 100 thalers–now.")

    # Assert
    assert result == "Heretake 100 thalersnow"


def test_removes_brackets_and_braces():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("at last?{2}")

    # Assert
    assert result == "at last2"


def test_preserves_whitespace_runs():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("a, b")

    # Assert
    assert result == "a b"


def test_text_without_punctuation_is_unchanged():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("just plain words 123")

    # Assert
    assert result == "just plain words 123"


def test_empty_string():
    # Arrange
    normalizer = PunctuationNormalizer()

    # Act
    result = normalizer.normalize("")

    # Assert
    assert result == ""
