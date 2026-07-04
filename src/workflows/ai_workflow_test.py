"""Tests for AIWorkflow._apply_prompt_output: LLM response → Book mapping."""
import json
from typing import Any, Optional

import pytest

from src.ai.ai_provider import AIProvider
from src.domain.beat import BeatType
from src.domain.character import Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    BookParseContext,
    Chapter,
    Section,
)
from src.domain.voice_settings import VoiceSettings
from src.parsers.book_source import BookSource
from src.prompts.chapter_parser.chapter_parser_prompt_builder import (
    ChapterParserPromptBuilder,
)
from src.prompts.chapter_parser.output import (
    PromptOutput,
    PromptOutputBeat,
    PromptOutputChapter,
    PromptOutputCharacter,
)
from src.repository.artifact_repository import ArtifactRepository
from src.repository.book_repository import BookRepository
from src.validators.validation_gate_error import ValidationGateError
from src.validators.validation_result import ValidationResult
from src.validators.validator import Validator
from src.workflows.ai_workflow import AIWorkflow, _strip_code_fence
from src.workflows.workflow import WorkflowRequest


def _empty_book() -> Book:
    metadata = BookMetadata(
        title="Pride and Prejudice", author="Jane Austen",
        releaseDate=None, language=None,
        originalPublication=None, credits=None,
    )
    return Book(metadata=metadata, content=BookContent(chapters=[]))


def _chapter() -> Chapter:
    return Chapter(number=1, title="")


def _response() -> PromptOutput:
    return PromptOutput(
        chapters=[PromptOutputChapter(
            id=1,
            beats=[
                PromptOutputBeat(
                    id=1, type="narration", text="Hello.", char_id=1,
                    emotion="neutral",
                ),
                PromptOutputBeat(
                    id=2, type="dialogue", text="My dear.", char_id=2,
                    emotion="warmly insistent",
                    voice_settings=VoiceSettings(
                        stability=0.3,
                        style=0.5,
                        similarity_boost=0.75,
                        use_speaker_boost=True,
                    ),
                ),
            ],
        )],
        characters=[
            PromptOutputCharacter(
                id=1, name="Narrator",
                gender="male", age="middle_aged", accent="british",
            ),
            PromptOutputCharacter(
                id=2, name="Mrs. Bennet",
                gender="female", age="middle_aged", accent="british",
            ),
        ],
    )


def test_characters_are_upserted_with_int_ids_and_structured_attrs() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    chars = {c.id: c for c in book.character_registry.characters}
    assert chars[1].name == "Narrator"
    assert chars[2].name == "Mrs. Bennet"
    assert chars[1].gender == "male"
    assert chars[1].age == "middle_aged"
    assert chars[1].accent == "british"
    assert chars[2].gender == "female"
    assert chars[2].accent == "british"


def test_beat_character_id_is_the_llm_numeric_id() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    beats = book.content.chapters[0].beats
    assert beats[0].character_id == 1
    assert beats[1].character_id == 2


def test_beat_text_emotion_and_type_round_trip() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    beats = book.content.chapters[0].beats
    assert [b.text for b in beats] == ["Hello.", "My dear."]
    assert [b.beat_type for b in beats] == [BeatType.NARRATION, BeatType.DIALOGUE]
    assert [b.emotion for b in beats] == ["neutral", "warmly insistent"]
    assert beats[0].voice_settings is None
    assert beats[1].voice_settings == VoiceSettings(
        stability=0.3, style=0.5, similarity_boost=0.75, use_speaker_boost=True,
    )


def test_chapter_sections_cleared_and_beats_populated() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    stored_chapter = book.content.chapters[0]
    assert stored_chapter.sections == []
    assert len(stored_chapter.beats) == 2


def test_unknown_beat_type_falls_back_to_narration() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()
    response = PromptOutput(
        chapters=[PromptOutputChapter(
            id=1,
            beats=[PromptOutputBeat(
                id=1, type="not_a_real_type", text="x", char_id=1,
            )],
        )],
        characters=[PromptOutputCharacter(id=1, name="Narrator")],
    )

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, response)

    # Assert
    assert book.content.chapters[0].beats[0].beat_type == BeatType.NARRATION


def test_build_prompt_input_threads_known_characters_into_the_prompt() -> None:
    # Arrange
    metadata = BookMetadata(
        title="Alice's Adventures in Wonderland", author="Lewis Carroll",
        releaseDate=None, language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(number=2, title="The Pool of Tears")
    known = [
        Character(id=1, name="Narrator", gender="male", age="middle_aged", accent="british"),
        Character(id=2, name="Alice", gender="female", age="young", accent="british"),
    ]

    # Act
    result = AIWorkflow._build_prompt_input(metadata, chapter, known_characters=known)

    # Assert
    assert [c.id for c in result.characters] == [1, 2]
    assert [c.name for c in result.characters] == ["Narrator", "Alice"]


def test_build_prompt_input_defaults_to_empty_characters() -> None:
    # Arrange
    metadata = BookMetadata(
        title="T", author="A", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(number=1, title="")

    # Act
    result = AIWorkflow._build_prompt_input(metadata, chapter)

    # Assert
    assert result.characters == []


class _RecordingArtifactRepository(ArtifactRepository):
    def __init__(self) -> None:
        self.prompts: list[tuple[str, int, str]] = []
        self.responses: list[tuple[str, int, str]] = []

    def save_prompt(self, book_id: str, chapter: Chapter, prompt: str) -> None:
        self.prompts.append((book_id, chapter.number, prompt))

    def save_response(self, book_id: str, chapter: Chapter, response: str) -> None:
        self.responses.append((book_id, chapter.number, response))

    def save_request(self, key: str, method: str, url: str, headers: Any, body: Any) -> None:
        pass


class _StubAIProvider(AIProvider):
    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[str] = []

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        self.calls.append(prompt)
        return self._response


class _PreloadedSource(BookSource):
    def __init__(self, ctx: BookParseContext) -> None:
        self._ctx = ctx

    def get_book(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> BookParseContext:
        return self._ctx


class _RecordingRepository(BookRepository):
    """Captures save_chapter calls and the book state at the moment of each call."""

    def __init__(self) -> None:
        self.saved_chapters: list[tuple[str, int]] = []

    def save(self, book: Book) -> None:
        return None

    def save_chapter(self, book: Book, chapter: Chapter) -> None:
        self.saved_chapters.append((book.book_id, chapter.number))

    def load(self, book_id: str) -> Optional[Book]:
        return None

    def exists(self, book_id: str) -> bool:
        return False

    def save_input(self, book: Book) -> None:
        return None

    def load_input(self, book_id: str) -> Optional[Book]:
        return None


def _wonderland_context() -> BookParseContext:
    metadata = BookMetadata(
        title="Wonderland", author="Lewis Carroll", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(
        number=1, title="Down the Rabbit-Hole",
        sections=[Section(text="Once upon a time.")],
    )
    book = Book(
        metadata=metadata,
        content=BookContent(chapters=[]),
        character_registry=CharacterRegistry(characters=[make_default_narrator()]),
    )
    return BookParseContext(
        book=book,
        chapters_to_parse=[chapter],
        content=BookContent(chapters=[chapter]),
    )


def test_run_writes_prompt_and_response_artifacts_per_chapter() -> None:
    # Arrange
    ctx = _wonderland_context()
    response_payload = json.dumps({
        "chapters": [{"id": 1, "beats": [
            {"id": 1, "type": "narration", "text": "Once upon a time.", "char_id": 1},
        ]}],
        "characters": [{"id": 1, "name": "Narrator"}],
    })
    ai = _StubAIProvider(response=response_payload)
    artifacts = _RecordingArtifactRepository()
    workflow = AIWorkflow(
        book_source=_PreloadedSource(ctx),
        prompt_builder=ChapterParserPromptBuilder(),
        ai_provider=ai,
        repositories=[_RecordingRepository()],
        artifact_repository=artifacts,
    )

    # Act
    workflow.run(WorkflowRequest(url="ignored"))

    # Assert
    assert len(artifacts.prompts) == 1
    saved_book_id, saved_chapter, saved_prompt = artifacts.prompts[0]
    assert saved_book_id == ctx.book.book_id
    assert saved_chapter == 1
    assert saved_prompt == ai.calls[0]
    assert artifacts.responses == [(ctx.book.book_id, 1, response_payload)]


def test_build_prompt_input_avoids_redundant_announcement_for_labelled_section() -> None:
    # Arrange
    metadata = BookMetadata(
        title="Frankenstein", author="Mary Shelley",
        releaseDate=None, language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(number=1, title="Letter 1", label="Letter 1")

    # Act
    result = AIWorkflow._build_prompt_input(metadata, chapter)

    # Assert
    announcement_sections = [
        s for s in result.chapters[0].sections
        if s.type == "chapter_announcement"
    ]
    assert len(announcement_sections) == 1
    assert announcement_sections[0].text == "Letter 1."


def test_build_prompt_input_includes_title_when_different_from_display_name() -> None:
    # Arrange
    metadata = BookMetadata(
        title="Alice", author="Lewis Carroll",
        releaseDate=None, language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(number=1, title="CHAPTER I. Down the Rabbit-Hole")

    # Act
    result = AIWorkflow._build_prompt_input(metadata, chapter)

    # Assert
    announcement_sections = [
        s for s in result.chapters[0].sections
        if s.type == "chapter_announcement"
    ]
    assert len(announcement_sections) == 1
    assert announcement_sections[0].text == "Chapter 1. CHAPTER I. Down the Rabbit-Hole."


class _StubValidator(Validator):
    """Returns a fixed deviation and records the books it was given."""

    def __init__(self, deviation: float, detail: str = "") -> None:
        self.deviation = deviation
        self.detail = detail
        self.input_books: list[Book] = []
        self.output_books: list[Book] = []

    def validate(self, input_book: Book, output_book: Book) -> ValidationResult:
        self.input_books.append(input_book)
        self.output_books.append(output_book)
        return ValidationResult(deviation=self.deviation, detail=self.detail)


def _workflow_with_validator(
    ctx: BookParseContext, validator: Validator, repository: BookRepository,
) -> AIWorkflow:
    response_payload = json.dumps({
        "chapters": [{"id": 1, "beats": [
            {"id": 1, "type": "narration", "text": "Once upon a time.", "char_id": 1},
        ]}],
        "characters": [{"id": 1, "name": "Narrator"}],
    })
    return AIWorkflow(
        book_source=_PreloadedSource(ctx),
        prompt_builder=ChapterParserPromptBuilder(),
        ai_provider=_StubAIProvider(response=response_payload),
        repositories=[repository],
        validators=[validator],
    )


def test_run_raises_and_skips_save_when_a_validator_fails() -> None:
    # Arrange
    ctx = _wonderland_context()
    repository = _RecordingRepository()
    workflow = _workflow_with_validator(ctx, _StubValidator(deviation=0.2), repository)

    # Act
    with pytest.raises(ValidationGateError) as exc_info:
        workflow.run(WorkflowRequest(url="ignored"))

    # Assert
    assert repository.saved_chapters == []
    assert exc_info.value.chapter_number == 1
    assert exc_info.value.failures == [("_StubValidator", 0.2, "")]


def test_validation_failure_surfaces_validator_detail() -> None:
    # Arrange
    ctx = _wonderland_context()
    repository = _RecordingRepository()
    validator = _StubValidator(deviation=0.5, detail="dropped 1/2: section 3: 'x'")
    workflow = _workflow_with_validator(ctx, validator, repository)

    # Act
    with pytest.raises(ValidationGateError) as exc_info:
        workflow.run(WorkflowRequest(url="ignored"))

    # Assert
    assert exc_info.value.failures == [("_StubValidator", 0.5, "dropped 1/2: section 3: 'x'")]
    assert "dropped 1/2" in str(exc_info.value)


def test_run_saves_chapter_when_validators_pass() -> None:
    # Arrange
    ctx = _wonderland_context()
    repository = _RecordingRepository()
    workflow = _workflow_with_validator(ctx, _StubValidator(deviation=0.0), repository)

    # Act
    workflow.run(WorkflowRequest(url="ignored"))

    # Assert
    assert repository.saved_chapters == [(ctx.book.book_id, 1)]


def test_validators_compare_input_sections_against_output_beats() -> None:
    # Arrange
    ctx = _wonderland_context()
    validator = _StubValidator(deviation=0.0)
    workflow = _workflow_with_validator(ctx, validator, _RecordingRepository())

    # Act
    workflow.run(WorkflowRequest(url="ignored"))

    # Assert
    input_chapter = validator.input_books[0].content.chapters[0]
    output_chapter = validator.output_books[0].content.chapters[0]
    assert [s.text for s in input_chapter.sections] == ["Once upon a time."]
    assert output_chapter.sections == []
    assert [b.text for b in output_chapter.beats] == ["Once upon a time."]


def test_run_calls_save_chapter_on_every_store_per_chapter() -> None:
    # Arrange
    ctx = _wonderland_context()
    response_payload = json.dumps({
        "chapters": [{"id": 1, "beats": [
            {"id": 1, "type": "narration", "text": "Once upon a time.", "char_id": 1},
        ]}],
        "characters": [{"id": 1, "name": "Narrator"}],
    })
    ai = _StubAIProvider(response=response_payload)
    repo_a = _RecordingRepository()
    repo_b = _RecordingRepository()
    workflow = AIWorkflow(
        book_source=_PreloadedSource(ctx),
        prompt_builder=ChapterParserPromptBuilder(),
        ai_provider=ai,
        repositories=[repo_a, repo_b],
    )

    # Act
    workflow.run(WorkflowRequest(url="ignored"))

    # Assert
    assert repo_a.saved_chapters == [(ctx.book.book_id, 1)]
    assert repo_b.saved_chapters == [(ctx.book.book_id, 1)]




def test_strip_code_fence_removes_json_fence():
    # Arrange
    fenced = "```json\n{\"chapters\": []}\n```"

    # Act
    result = _strip_code_fence(fenced)

    # Assert
    assert result == "{\"chapters\": []}"


def test_strip_code_fence_leaves_plain_json_untouched():
    # Arrange
    plain = "{\"chapters\": []}"

    # Act
    result = _strip_code_fence(plain)

    # Assert
    assert result == plain
