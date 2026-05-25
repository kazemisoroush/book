"""Tests for character_id helpers."""
from src.domain.character_id import build_character_id, narrator_id, slugify_name


class TestSlugifyName:
    """slugify_name lowercases and collapses non-alphanum runs to underscores."""

    def test_lowercases_letters(self) -> None:
        # Arrange / Act / Assert
        assert slugify_name("Hagrid") == "hagrid"

    def test_collapses_spaces(self) -> None:
        # Arrange / Act / Assert
        assert slugify_name("Mr Darcy") == "mr_darcy"

    def test_strips_punctuation(self) -> None:
        # Arrange / Act / Assert
        assert slugify_name("Mr. O'Brien") == "mr_o_brien"

    def test_collapses_repeated_separators(self) -> None:
        # Arrange / Act / Assert
        assert slugify_name("  Albus   Dumbledore  ") == "albus_dumbledore"

    def test_strips_leading_trailing_separators(self) -> None:
        # Arrange / Act / Assert
        assert slugify_name("!!Sirius!!") == "sirius"


class TestBuildCharacterId:
    """build_character_id joins book_id and slug with a colon."""

    def test_prefixes_with_book_id(self) -> None:
        # Arrange / Act / Assert
        assert build_character_id("pride-and-prejudice", "Elizabeth Bennet") == (
            "pride-and-prejudice:elizabeth_bennet"
        )

    def test_keeps_book_id_verbatim(self) -> None:
        # Arrange — book_id may already contain spaces and dashes.
        # Act / Assert
        assert build_character_id("Pride and Prejudice - Jane Austen", "Mr Darcy") == (
            "Pride and Prejudice - Jane Austen:mr_darcy"
        )


class TestNarratorId:
    """narrator_id returns the canonical narrator id for a book."""

    def test_format(self) -> None:
        # Arrange / Act / Assert
        assert narrator_id("the-book") == "the-book:narrator"
