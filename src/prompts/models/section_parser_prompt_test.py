"""Tests for SectionParserPrompt.create() — the factory for section-parser prompts."""
from src.domain.beat import BeatType
from src.domain.models import (
    Character,
    CharacterRegistry,
    Scene,
    SceneRegistry,
    Section,
)
from src.prompts.models.ai_prompt import AIPrompt
from src.prompts.models.section_parser_prompt import SectionParserPrompt


def test_create_with_no_book_context_omits_book_context():
    """No title/author -> empty book_context."""
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create("Some sample text.", registry)

    # Assert
    assert isinstance(prompt, AIPrompt)
    assert prompt.book_context == ""


def test_create_with_only_title_includes_title_in_book_context():
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create(
        "Some sample text.", registry, book_title="Pride and Prejudice",
    )

    # Assert
    assert "Pride and Prejudice" in prompt.book_context
    assert "Book context:" in prompt.book_context


def test_create_with_title_and_author_includes_both():
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create(
        "Some sample text.", registry,
        book_title="Pride and Prejudice",
        book_author="Jane Austen",
    )

    # Assert
    assert "Pride and Prejudice" in prompt.book_context
    assert "by Jane Austen" in prompt.book_context


def test_create_returns_prompt_with_all_six_fields_populated():
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create(
        "Sample text to beat.", registry,
        book_title="Test Book", book_author="Test Author",
    )

    # Assert
    assert isinstance(prompt, AIPrompt)
    assert prompt.static_instructions != ""
    assert prompt.text_to_parse != ""


def test_static_instructions_contain_expected_beatation_rules():
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create("Test", registry)

    # Assert
    assert "Break down the following text" in prompt.static_instructions
    assert "dialogue" in prompt.static_instructions
    assert "narration" in prompt.static_instructions
    assert "Existing characters" in prompt.static_instructions


def test_character_registry_field_contains_registry_entries():
    # Arrange
    registry = CharacterRegistry()
    registry.upsert(Character(
        character_id="harry_potter",
        name="Harry Potter",
        description="young British wizard",
    ))

    # Act
    prompt = SectionParserPrompt.create("Test", registry)

    # Assert
    assert "harry_potter" in prompt.character_registry
    assert "Harry Potter" in prompt.character_registry


def test_surrounding_context_populated_when_context_window_provided():
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")
    context_section = Section(text="Previous section text.")

    # Act
    prompt = SectionParserPrompt.create(
        "Current section text.", registry, context_window=[context_section],
    )

    # Assert
    assert prompt.surrounding_context != ""
    assert "Surrounding context" in prompt.surrounding_context


def test_scene_registry_field_populated_when_scenes_exist():
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")
    scene_registry = SceneRegistry()
    scene_registry.upsert(Scene(
        scene_id="scene_indoor_quiet",
        environment="indoor_quiet",
        acoustic_hints=["confined", "warm"],
        voice_modifiers={},
        ambient_prompt=None,
        ambient_volume=None,
    ))

    # Act
    prompt = SectionParserPrompt.create("Test", registry, scene_registry=scene_registry)

    # Assert
    assert "Existing scenes" in prompt.scene_registry
    assert "indoor_quiet" in prompt.scene_registry


def test_text_to_parse_field_contains_the_input_text():
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create("This is the exact text to beat.", registry)

    # Assert
    assert "This is the exact text to beat." in prompt.text_to_parse


def test_prompt_lists_every_ai_emittable_beat_type():
    """Sync check: every BeatType the parser handles must appear in the prompt.

    If a new BeatType is added to the domain and the parser, the prompt must
    list it so the LLM knows it can emit that type. Excluded: types the AI
    never emits (illustration/copyright via deterministic pre-parser,
    book_title/chapter_announcement injected by the workflow).
    """
    # Arrange
    ai_emittable_types = {
        BeatType.DIALOGUE,
        BeatType.NARRATION,
        BeatType.OTHER,
        BeatType.SOUND_EFFECT,
        BeatType.VOCAL_EFFECT,
    }
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create("Test", registry)
    instructions = prompt.static_instructions

    # Assert
    for beat_type in ai_emittable_types:
        assert f'"{beat_type.value}"' in instructions, (
            f'BeatType.{beat_type.name} ("{beat_type.value}") is missing '
            f"from the prompt's type enumeration. The LLM won't emit it."
        )


def test_prompt_does_not_include_deterministic_beat_types():
    """book_title and chapter_announcement are injected by the workflow, not the LLM."""
    # Arrange
    registry = CharacterRegistry.with_default_narrator("book")

    # Act
    prompt = SectionParserPrompt.create("Test", registry)
    instructions = prompt.static_instructions

    # Assert
    assert '"book_title"' not in instructions
    assert '"chapter_announcement"' not in instructions
