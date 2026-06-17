"""Tests for SfxWorkflow."""
from pathlib import Path

import pytest

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.domain.beat import Beat, BeatType
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
)
from src.stores.file_book_store import FileBookStore
from src.workflows.sfx_workflow import SfxWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.sfx_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


class StubSfxProvider(SoundEffectProvider):
    """Test stub that records calls."""

    @property
    def name(self) -> str:
        return "stub"

    def __init__(self) -> None:
        self.provide_call_count = 0
        self.provided_beats: list[Beat] = []

    def provide(self, beat: "Beat", book_id: str) -> None:
        self.provide_call_count += 1
        self.provided_beats.append(beat)

    def _generate(self, description: str, output_path: Path, duration_seconds: float = 2.0) -> Path | None:
        raise NotImplementedError


def _make_sfx_book() -> Book:
    return Book(
        metadata=BookMetadata(
            title="SFX Book", author="Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(
                number=1, title="Ch1",
                beats=[
                    Beat(text="door knock", beat_type=BeatType.SOUND_EFFECT),
                    Beat(text="sigh", beat_type=BeatType.VOCAL_EFFECT),
                    Beat(text="narration", beat_type=BeatType.NARRATION, character_id=1),
                ],
            ),
        ]),
    )


def test_run_calls_provider_for_sfx_and_vocal_beats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run() calls provide() for SOUND_EFFECT and VOCAL_EFFECT beats only."""
    # Arrange
    store = FileBookStore(base_dir=str(tmp_path))
    book = _make_sfx_book()
    book_id = book.book_id
    store.save(book)
    _patch_resolver(monkeypatch, book_id)

    stub = StubSfxProvider()
    workflow = SfxWorkflow(stores=[store], provider=stub, books_dir=tmp_path)

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert — 2 beats match (SOUND_EFFECT + VOCAL_EFFECT), narration skipped
    assert stub.provide_call_count == 2
    assert {b.beat_type for b in stub.provided_beats} == {
        BeatType.SOUND_EFFECT, BeatType.VOCAL_EFFECT,
    }


def test_run_raises_when_book_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run() raises ValueError when book_id not found in store."""
    # Arrange
    store = FileBookStore(base_dir=str(tmp_path))
    _patch_resolver(monkeypatch, "nonexistent")
    stub = StubSfxProvider()
    workflow = SfxWorkflow(stores=[store], provider=stub, books_dir=tmp_path)

    # Act & Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(WorkflowRequest(url=_URL))
