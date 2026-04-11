"""Tests for PromptBuilder."""
from src.parsers.prompt_builder import PromptBuilder
from src.domain.models import (
    CharacterRegistry, Character, Section, SceneRegistry, Scene, AIPrompt,
    SegmentType,
)


def test_prompt_builder_with_no_book_context_builds_prompt_without_book_context():
    """PromptBuilder with no title/author should generate empty book_context."""
    # Arrange
    builder = PromptBuilder()
    registry = CharacterRegistry.with_default_narrator()
    text = "Some sample text."

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=None)

    # Assert
    assert isinstance(prompt, AIPrompt)
    assert prompt.book_context == ""


def test_prompt_builder_with_only_title_includes_title_in_book_context():
    """PromptBuilder with only title should include it in book_context."""
    # Arrange
    builder = PromptBuilder(book_title="Pride and Prejudice")
    registry = CharacterRegistry.with_default_narrator()
    text = "Some sample text."

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=None)

    # Assert
    assert "Pride and Prejudice" in prompt.book_context
    assert "Book context:" in prompt.book_context


def test_prompt_builder_with_title_and_author_includes_both():
    """PromptBuilder with title and author should include both in book_context."""
    # Arrange
    builder = PromptBuilder(
        book_title="Pride and Prejudice",
        book_author="Jane Austen"
    )
    registry = CharacterRegistry.with_default_narrator()
    text = "Some sample text."

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=None)

    # Assert
    assert "Pride and Prejudice" in prompt.book_context
    assert "Jane Austen" in prompt.book_context
    assert "by Jane Austen" in prompt.book_context


def test_build_prompt_returns_ai_prompt_with_all_six_fields_populated():
    """build_prompt should return an AIPrompt with all 6 fields."""
    # Arrange
    builder = PromptBuilder(book_title="Test Book", book_author="Test Author")
    registry = CharacterRegistry.with_default_narrator()
    text = "Sample text to segment."

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=None)

    # Assert
    assert isinstance(prompt, AIPrompt)
    assert hasattr(prompt, 'static_instructions')
    assert hasattr(prompt, 'book_context')
    assert hasattr(prompt, 'character_registry')
    assert hasattr(prompt, 'surrounding_context')
    assert hasattr(prompt, 'scene_registry')
    assert hasattr(prompt, 'text_to_segment')
    assert prompt.static_instructions != ""
    assert prompt.text_to_segment != ""


def test_static_instructions_field_contains_expected_segmentation_rules():
    """static_instructions should contain key segmentation rules."""
    # Arrange
    builder = PromptBuilder()
    registry = CharacterRegistry.with_default_narrator()
    text = "Test"

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=None)

    # Assert
    assert "Break down the following text" in prompt.static_instructions
    assert "dialogue" in prompt.static_instructions
    assert "narration" in prompt.static_instructions
    assert "Existing characters" in prompt.static_instructions


def test_character_registry_field_contains_registry_entries_formatted_correctly():
    """character_registry field should contain formatted character entries."""
    # Arrange
    builder = PromptBuilder()
    registry = CharacterRegistry()
    registry.upsert(Character(
        character_id="harry_potter",
        name="Harry Potter",
        description="young British wizard"
    ))
    text = "Test"

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=None)

    # Assert
    assert "harry_potter" in prompt.character_registry
    assert "Harry Potter" in prompt.character_registry


def test_surrounding_context_field_populated_when_context_window_provided():
    """surrounding_context should be populated when context_window is non-empty."""
    # Arrange
    builder = PromptBuilder()
    registry = CharacterRegistry.with_default_narrator()
    text = "Current section text."
    context_section = Section(
        text="Previous section text.",
        section_type=None
    )

    # Act
    prompt = builder.build_prompt(
        text, registry, context_window=[context_section], scene_registry=None
    )

    # Assert
    assert prompt.surrounding_context != ""
    assert "Surrounding context" in prompt.surrounding_context


def test_scene_registry_field_populated_when_scene_registry_has_scenes():
    """scene_registry field should be populated when scene_registry contains scenes."""
    # Arrange
    builder = PromptBuilder()
    registry = CharacterRegistry.with_default_narrator()
    scene_registry = SceneRegistry()
    scene = Scene(
        scene_id="scene_indoor_quiet",
        environment="indoor_quiet",
        acoustic_hints=["confined", "warm"],
        voice_modifiers={},
        ambient_prompt=None,
        ambient_volume=None
    )
    scene_registry.upsert(scene)
    text = "Test"

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=scene_registry)

    # Assert
    assert prompt.scene_registry != ""
    assert "Existing scenes" in prompt.scene_registry
    assert "indoor_quiet" in prompt.scene_registry


def test_text_to_segment_field_contains_the_input_text():
    """text_to_segment field should contain the input text."""
    # Arrange
    builder = PromptBuilder()
    registry = CharacterRegistry.with_default_narrator()
    text = "This is the exact text to segment."

    # Act
    prompt = builder.build_prompt(text, registry, None, scene_registry=None)

    # Assert
    assert "This is the exact text to segment." in prompt.text_to_segment


def test_prompt_type_enumeration_lists_every_ai_emittable_segment_type():
    """The prompt's type list must mention every SegmentType the parser handles.

    This is a sync-check: if a new SegmentType is added to the domain model
    and the parser, the prompt must also list it so the LLM knows it can emit
    that type. Without this, the LLM ignores the type even if instructions
    for it exist elsewhere in the prompt.

    Excluded types are those the AI never emits (ILLUSTRATION and COPYRIGHT
    are detected by the deterministic pre-parser, not the LLM).
    """
    # Arrange
    ai_emittable_types = {
        SegmentType.DIALOGUE,
        SegmentType.NARRATION,
        SegmentType.OTHER,
        SegmentType.SOUND_EFFECT,
    }
    builder = PromptBuilder()
    registry = CharacterRegistry.with_default_narrator()

    # Act
    prompt = builder.build_prompt("Test", registry, None, scene_registry=None)
    instructions = prompt.static_instructions

    # Assert — each AI-emittable type's value string appears in the type line
    for seg_type in ai_emittable_types:
        assert f'"{seg_type.value}"' in instructions, (
            f'SegmentType.{seg_type.name} ("{seg_type.value}") is missing '
            f"from the prompt's type enumeration. The LLM won't emit it."
        )
