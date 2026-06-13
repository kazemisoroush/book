"""Tests for TTSWorkflow."""
from pathlib import Path

import pytest

from src.audio.tts.tts_provider import StubTTSProvider
from src.characters.character_provider import CharacterProvider
from src.domain.beat import Beat, BeatType
from src.domain.character import NARRATOR_ID, Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
)
from src.repository.file_book_repository import FileBookRepository
from src.workflows.tts_workflow import TTSWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"
_ALICE_ID = 2


class _UnusedCharacterProvider(CharacterProvider):
    """TTSWorkflow no longer calls the character provider; this just satisfies the type."""

    def upsert(self, character: Character, book_id: str) -> str:
        raise AssertionError("upsert should not be called by TTSWorkflow")


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.tts_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _make_book(voice_assignments: dict[int, str] | None = None) -> Book:
    """Create a test book with two narratable beats."""
    registry = CharacterRegistry(characters=[make_default_narrator()])
    registry.add(Character(
        id=_ALICE_ID, name="Alice", description="A young girl",
        sex="female", age="young",
    ))
    chapter = Chapter(
        number=1, title="Chapter 1",
        beats=[
            Beat(text="Once upon a time.", beat_type=BeatType.NARRATION, character_id=NARRATOR_ID),
            Beat(text="Hello, world!", beat_type=BeatType.DIALOGUE, character_id=_ALICE_ID),
        ],
    )
    return Book(
        metadata=BookMetadata(
            title="Test Book", author="Test Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[chapter]),
        character_registry=registry,
        voice_assignments=voice_assignments or {},
    )


def _two_chapter_book(voices: dict[int, str]) -> Book:
    registry = CharacterRegistry(characters=[make_default_narrator()])
    return Book(
        metadata=BookMetadata(
            title="Test Book", author="Test Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(
                number=1, title="Chapter 1",
                beats=[Beat(
                    text="Ch1 beat.", beat_type=BeatType.NARRATION,
                    character_id=NARRATOR_ID,
                )],
            ),
            Chapter(
                number=2, title="Chapter 2",
                beats=[Beat(
                    text="Ch2 beat.", beat_type=BeatType.NARRATION,
                    character_id=NARRATOR_ID,
                )],
            ),
        ]),
        character_registry=registry,
        voice_assignments=voices,
    )


def test_run_respects_chapter_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _two_chapter_book({NARRATOR_ID: "v_narr"})
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book)
    _patch_resolver(monkeypatch, book.book_id)

    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act: ask for chapter 2 only.
    workflow.run(WorkflowRequest(url=_URL, start_chapter=2, end_chapter=2))

    # Assert: only the chapter-2 beat was synthesised.
    assert stub_provider._provide_call_count == 1


def test_run_synthesises_narratable_beats_via_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _make_book({NARRATOR_ID: "v_narr", _ALICE_ID: "v_alice"})
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book)
    _patch_resolver(monkeypatch, book.book_id)

    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert stub_provider._provide_call_count == 2


def test_run_skips_non_narratable_beats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    metadata = BookMetadata(
        title="Test Book", author="Author", language="en",
        releaseDate=None, originalPublication=None, credits=None,
    )
    registry = CharacterRegistry(characters=[make_default_narrator()])
    book = Book(
        metadata=metadata,
        content=BookContent(chapters=[
            Chapter(
                number=1, title="Ch1",
                beats=[Beat(text="boom", beat_type=BeatType.SOUND_EFFECT)],
            ),
        ]),
        character_registry=registry,
        voice_assignments={NARRATOR_ID: "v_narr"},
    )
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book)
    _patch_resolver(monkeypatch, book.book_id)

    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert stub_provider._provide_call_count == 0


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent-book-id")

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=StubTTSProvider(),
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))


def test_run_raises_when_voice_assignments_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _make_book()
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book)
    _patch_resolver(monkeypatch, book.book_id)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=StubTTSProvider(),
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act / Assert
    with pytest.raises(ValueError, match="No voices registered"):
        workflow.run(WorkflowRequest(url=_URL))


def test_run_threads_context_with_previous_text_and_request_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    registry = CharacterRegistry(characters=[make_default_narrator()])
    chapter = Chapter(
        number=1, title="Chapter 1",
        beats=[
            Beat(text="First narration.", beat_type=BeatType.NARRATION, character_id=NARRATOR_ID),
            Beat(text="Second narration.", beat_type=BeatType.NARRATION, character_id=NARRATOR_ID),
            Beat(text="Third narration.", beat_type=BeatType.NARRATION, character_id=NARRATOR_ID),
        ],
    )
    book = Book(
        metadata=BookMetadata(
            title="Test Book", author="Test Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[chapter]),
        character_registry=registry,
        voice_assignments={NARRATOR_ID: "v_narr"},
    )
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book)
    _patch_resolver(monkeypatch, book.book_id)

    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert stub_provider._provide_call_count == 3
    first_ctx, second_ctx, third_ctx = stub_provider.provide_contexts
    assert first_ctx is not None
    assert first_ctx.previous_text is None
    assert first_ctx.next_text == "Second narration."
    assert first_ctx.previous_request_ids is None
    assert second_ctx is not None
    assert second_ctx.previous_text == "First narration."
    assert second_ctx.previous_request_ids == ["stub-req-0001"]
    assert third_ctx is not None
    assert third_ctx.previous_text == "Second narration."
    assert third_ctx.previous_request_ids == ["stub-req-0001", "stub-req-0002"]


def test_run_resets_request_id_chain_per_chapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    book = _two_chapter_book({NARRATOR_ID: "v_narr"})
    repository = FileBookRepository(base_dir=str(tmp_path))
    repository.save(book)
    _patch_resolver(monkeypatch, book.book_id)

    stub_provider = StubTTSProvider()
    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_provider,
        character_provider=_UnusedCharacterProvider(),
        books_dir=tmp_path,
    )

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert stub_provider._provide_call_count == 2
    first_ctx, second_ctx = stub_provider.provide_contexts
    assert first_ctx is not None
    assert first_ctx.previous_request_ids is None
    assert second_ctx is not None
    assert second_ctx.previous_request_ids is None
