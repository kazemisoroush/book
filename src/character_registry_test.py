"""Tests for character registry."""
import json
import pytest
from unittest.mock import Mock

from .character_registry import CharacterRegistry, Character


class TestCharacterRegistry:
    """Tests for CharacterRegistry."""

    @pytest.fixture
    def mock_ai_provider(self):
        """Create a mock AI provider."""
        return Mock()

    def test_init_without_ai(self):
        """Test initialization without AI provider."""
        registry = CharacterRegistry()

        assert registry.ai_provider is None
        assert registry.characters == {}
        assert registry.current_chapter == 0

    def test_init_with_ai(self, mock_ai_provider):
        """Test initialization with AI provider."""
        registry = CharacterRegistry(ai_provider=mock_ai_provider)

        assert registry.ai_provider == mock_ai_provider
        assert registry.characters == {}

    def test_set_chapter(self):
        """Test setting current chapter."""
        registry = CharacterRegistry()
        registry.set_chapter(5)

        assert registry.current_chapter == 5

    def test_get_canonical_name_not_found(self):
        """Test getting canonical name when not in registry."""
        registry = CharacterRegistry()

        result = registry.get_canonical_name("Mrs. Bennet")

        assert result is None

    def test_get_canonical_name_exact_match(self):
        """Test getting canonical name with exact match."""
        registry = CharacterRegistry()
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet", "his wife"],
            context="Married to Mr. Bennet",
            first_seen_chapter=1
        )

        result = registry.get_canonical_name("Mrs. Bennet")

        assert result == "Mrs. Bennet"

    def test_get_canonical_name_case_insensitive(self):
        """Test canonical name lookup is case insensitive."""
        registry = CharacterRegistry()
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet"],
            context="Mother",
            first_seen_chapter=1
        )

        result = registry.get_canonical_name("mrs. bennet")

        assert result == "Mrs. Bennet"

    def test_get_canonical_name_via_alias(self):
        """Test getting canonical name via alias."""
        registry = CharacterRegistry()
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet", "his wife", "lady"],
            context="Mother",
            first_seen_chapter=1
        )

        result = registry.get_canonical_name("his wife")

        assert result == "Mrs. Bennet"

    def test_get_canonical_name_alias_case_insensitive(self):
        """Test alias lookup is case insensitive."""
        registry = CharacterRegistry()
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet", "his wife"],
            context="Mother",
            first_seen_chapter=1
        )

        result = registry.get_canonical_name("HIS WIFE")

        assert result == "Mrs. Bennet"

    def test_identify_speaker_fast_path(self, mock_ai_provider):
        """Test speaker identification uses fast path when descriptor is known."""
        registry = CharacterRegistry(ai_provider=mock_ai_provider)
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet", "his wife"],
            context="Mother",
            first_seen_chapter=1
        )

        result = registry.identify_speaker(
            "his wife",
            '"Hello," said his wife.',
            None
        )

        assert result == "Mrs. Bennet"
        # AI should NOT be called (fast path)
        mock_ai_provider.generate.assert_not_called()

    def test_identify_speaker_without_ai_fallback(self):
        """Test speaker identification without AI provider uses normalized name."""
        registry = CharacterRegistry()  # No AI

        result = registry.identify_speaker(
            "mrs. bennet",
            '"Hello," said Mrs. Bennet.',
            None
        )

        assert result == "Mrs. Bennet"  # Normalized

    def test_identify_speaker_with_ai_new_character(self, mock_ai_provider):
        """Test speaker identification with AI for new character."""
        registry = CharacterRegistry(ai_provider=mock_ai_provider)
        registry.set_chapter(1)

        # Mock AI response
        ai_response = {
            "speaker": "Mrs. Bennet",
            "registry": {
                "Mrs. Bennet": {
                    "aliases": ["Mrs. Bennet"],
                    "context": "Married to Mr. Bennet. Mother of five daughters.",
                    "first_seen_chapter": 1
                }
            }
        }
        mock_ai_provider.generate.return_value = json.dumps(ai_response)

        result = registry.identify_speaker(
            "Mrs. Bennet",
            '"Hello," said Mrs. Bennet to her husband.',
            "Mr. Bennet was reading."
        )

        assert result == "Mrs. Bennet"
        assert "Mrs. Bennet" in registry.characters
        assert registry.characters["Mrs. Bennet"].context == "Married to Mr. Bennet. Mother of five daughters."

        # Verify AI was called with correct prompt
        mock_ai_provider.generate.assert_called_once()
        prompt = mock_ai_provider.generate.call_args[0][0]
        assert "Mrs. Bennet" in prompt
        assert "Mr. Bennet was reading" in prompt

    def test_identify_speaker_with_ai_adds_alias(self, mock_ai_provider):
        """Test speaker identification with AI adds new alias to existing character."""
        registry = CharacterRegistry(ai_provider=mock_ai_provider)
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet"],
            context="Mother",
            first_seen_chapter=1
        )

        # Mock AI response adding "his wife" as alias
        ai_response = {
            "speaker": "Mrs. Bennet",
            "registry": {
                "Mrs. Bennet": {
                    "aliases": ["Mrs. Bennet", "his wife"],
                    "context": "Married to Mr. Bennet. Mother of five daughters.",
                    "first_seen_chapter": 1
                }
            }
        }
        mock_ai_provider.generate.return_value = json.dumps(ai_response)

        result = registry.identify_speaker(
            "his wife",
            '"Yes," his wife replied.',
            None
        )

        assert result == "Mrs. Bennet"
        assert "his wife" in registry.characters["Mrs. Bennet"].aliases

    def test_identify_speaker_ai_error_fallback(self, mock_ai_provider):
        """Test speaker identification falls back on AI error."""
        registry = CharacterRegistry(ai_provider=mock_ai_provider)

        # Mock AI error
        mock_ai_provider.generate.side_effect = Exception("API error")

        result = registry.identify_speaker(
            "mrs. bennet",
            '"Hello," said Mrs. Bennet.',
            None
        )

        # Should fallback to normalized name
        assert result == "Mrs. Bennet"

    def test_identify_speaker_ai_invalid_json_fallback(self, mock_ai_provider):
        """Test speaker identification falls back on invalid JSON."""
        registry = CharacterRegistry(ai_provider=mock_ai_provider)

        # Mock invalid JSON response
        mock_ai_provider.generate.return_value = "This is not JSON"

        result = registry.identify_speaker(
            "elizabeth",
            '"Hello," said Elizabeth.',
            None
        )

        # Should fallback to normalized name
        assert result == "Elizabeth"

    def test_get_all_characters(self):
        """Test getting all characters returns a copy."""
        registry = CharacterRegistry()
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet"],
            context="Mother",
            first_seen_chapter=1
        )

        result = registry.get_all_characters()

        assert "Mrs. Bennet" in result
        assert result is not registry.characters  # Should be a copy

    def test_to_dict(self):
        """Test registry serialization to dict."""
        registry = CharacterRegistry()
        registry.characters["Mrs. Bennet"] = Character(
            canonical_name="Mrs. Bennet",
            aliases=["Mrs. Bennet", "his wife"],
            context="Mother",
            first_seen_chapter=1
        )

        result = registry.to_dict()

        assert "Mrs. Bennet" in result
        assert result["Mrs. Bennet"]["canonical_name"] == "Mrs. Bennet"
        assert "his wife" in result["Mrs. Bennet"]["aliases"]

    def test_from_dict(self):
        """Test registry deserialization from dict."""
        registry = CharacterRegistry()
        data = {
            "Mrs. Bennet": {
                "canonical_name": "Mrs. Bennet",
                "aliases": ["Mrs. Bennet", "his wife"],
                "context": "Mother",
                "first_seen_chapter": 1
            }
        }

        registry.from_dict(data)

        assert "Mrs. Bennet" in registry.characters
        assert registry.characters["Mrs. Bennet"].canonical_name == "Mrs. Bennet"
        assert "his wife" in registry.characters["Mrs. Bennet"].aliases

    def test_multiple_characters(self, mock_ai_provider):
        """Test registry with multiple characters."""
        registry = CharacterRegistry(ai_provider=mock_ai_provider)

        # Add first character via AI
        ai_response_1 = {
            "speaker": "Mrs. Bennet",
            "registry": {
                "Mrs. Bennet": {
                    "aliases": ["Mrs. Bennet"],
                    "context": "Mother",
                    "first_seen_chapter": 1
                }
            }
        }
        mock_ai_provider.generate.return_value = json.dumps(ai_response_1)
        registry.identify_speaker("Mrs. Bennet", "...", None)

        # Add second character via AI
        ai_response_2 = {
            "speaker": "Elizabeth Bennet",
            "registry": {
                "Mrs. Bennet": {
                    "aliases": ["Mrs. Bennet"],
                    "context": "Mother",
                    "first_seen_chapter": 1
                },
                "Elizabeth Bennet": {
                    "aliases": ["Elizabeth", "Lizzy"],
                    "context": "Second daughter",
                    "first_seen_chapter": 1
                }
            }
        }
        mock_ai_provider.generate.return_value = json.dumps(ai_response_2)
        registry.identify_speaker("Elizabeth", "...", None)

        assert len(registry.characters) == 2
        assert "Mrs. Bennet" in registry.characters
        assert "Elizabeth Bennet" in registry.characters
