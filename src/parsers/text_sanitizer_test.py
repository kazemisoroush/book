"""Tests for text_sanitizer module."""

from src.parsers.text_sanitizer import sanitize_beat_text


class TestSanitizeBeatText:
    """Test sanitize_beat_text removes trailing non-terminal punctuation."""

    def test_strips_trailing_comma(self) -> None:
        # Arrange
        text = "My dear Mr. Bennet,"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "My dear Mr. Bennet"

    def test_strips_trailing_em_dash(self) -> None:
        # Arrange
        text = "and so, she went—"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "and so, she went"

    def test_strips_trailing_ellipsis(self) -> None:
        # Arrange
        text = "but I never…"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "but I never"

    def test_strips_trailing_semicolon_and_space(self) -> None:
        # Arrange
        text = "he said; "

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "he said"

    def test_preserves_comma_inside_closing_quote(self) -> None:
        # Arrange
        text = '"Come here,"'

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == '"Come here,"'

    def test_preserves_terminal_period(self) -> None:
        # Arrange
        text = "Hello."

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "Hello."

    def test_preserves_terminal_question_mark(self) -> None:
        # Arrange
        text = "What?"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "What?"

    def test_strips_only_trailing_em_dash_not_internal(self) -> None:
        # Arrange
        text = "well—you know—"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "well—you know"

    def test_empty_string_returns_empty(self) -> None:
        # Arrange
        text = ""

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == ""

    def test_whitespace_only_returns_empty(self) -> None:
        # Arrange
        text = "   "

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == ""

    def test_only_punctuation_returns_empty(self) -> None:
        # Arrange
        text = "---"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == ""

    def test_strips_multiple_trailing_punctuation(self) -> None:
        # Arrange
        text = "text,;—"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "text"

    def test_collapses_internal_double_spaces(self) -> None:
        # Arrange
        text = "hello  world"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "hello world"

    def test_is_idempotent(self) -> None:
        # Arrange
        text = "trailing comma, "

        # Act
        first_pass = sanitize_beat_text(text)
        second_pass = sanitize_beat_text(first_pass)

        # Assert
        assert first_pass == second_pass
        assert first_pass == "trailing comma"

    def test_strips_trailing_colon(self) -> None:
        # Arrange
        text = "he said:"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "he said"

    def test_strips_trailing_en_dash(self) -> None:
        # Arrange
        text = "the year 1990–"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "the year 1990"

    def test_strips_trailing_hyphen(self) -> None:
        # Arrange
        text = "well-"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "well"

    def test_strips_trailing_asterisk(self) -> None:
        # Arrange
        text = "see footnote*"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "see footnote"

    def test_strips_trailing_hash(self) -> None:
        # Arrange
        text = "chapter 3#"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "chapter 3"

    def test_preserves_exclamation_mark(self) -> None:
        # Arrange
        text = "Stop!"

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "Stop!"

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        # Arrange
        text = "  hello world  "

        # Act
        result = sanitize_beat_text(text)

        # Assert
        assert result == "hello world"
