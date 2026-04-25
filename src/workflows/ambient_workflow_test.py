"""Tests for AmbientWorkflow."""
from pathlib import Path

import pytest

from src.audio.ambient.ambient_provider import AmbientProvider
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Scene,
    SceneRegistry,
    Section,
)
from src.repository.book_id import generate_book_id
from src.repository.file_book_repository import FileBookRepository
from src.workflows.ambient_workflow import AmbientWorkflow


class StubAmbientProvider(AmbientProvider):
    """Test stub that records provide() calls."""

    @property
    def name(self) -> str:
        return "stub"

    def __init__(self, fixed_duration: float = 10.0) -> None:
        self._fixed_duration = fixed_duration
        self.provide_call_count = 0
        self.provided_scene_ids: list[str] = []

    def provide(self, scene: Scene, book_id: str) -> float:
        self.provide_call_count += 1
        self.provided_scene_ids.append(scene.scene_id)
        return self._fixed_duration

    def _generate(self, prompt: str, output_path: Path, duration_seconds: float = 60.0) -> Path | None:
        raise NotImplementedError


def _make_ambient_book() -> Book:
    scene_registry = SceneRegistry()
    scene_registry.upsert(Scene(
        scene_id="forest",
        environment="forest",
        ambient_prompt="gentle forest sounds",
    ))
    scene_registry.upsert(Scene(
        scene_id="no_prompt",
        environment="cave",
        ambient_prompt=None,
    ))

    return Book(
        metadata=BookMetadata(
            title="Ambient Book", author="Author", language="en",
            releaseDate=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(number=1, title="Ch1", sections=[Section(text="test")])
        ]),
        scene_registry=scene_registry,
    )


def test_run_calls_provider_for_scenes_with_ambient_prompt(tmp_path: Path) -> None:
    """run() calls provide() for scenes with ambient_prompt, skips those without."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_ambient_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    stub = StubAmbientProvider()
    workflow = AmbientWorkflow(repository=repository, provider=stub, books_dir=tmp_path)

    # Act
    workflow.run(book_id=book_id)

    # Assert — only the "forest" scene (with prompt) was called
    assert stub.provide_call_count == 1
    assert stub.provided_scene_ids == ["forest"]


def test_run_saves_book_to_repository(tmp_path: Path) -> None:
    """run() saves the book back to the repository."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_ambient_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    stub = StubAmbientProvider()
    workflow = AmbientWorkflow(repository=repository, provider=stub, books_dir=tmp_path)

    # Act
    workflow.run(book_id=book_id)

    # Assert
    loaded = repository.load(book_id)
    assert loaded is not None
    assert loaded.metadata.title == "Ambient Book"


def test_run_raises_when_book_not_found(tmp_path: Path) -> None:
    """run() raises ValueError when book_id not found."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    stub = StubAmbientProvider()
    workflow = AmbientWorkflow(repository=repository, provider=stub, books_dir=tmp_path)

    # Act & Assert
    with pytest.raises(ValueError, match="No book found"):
        workflow.run(book_id="nonexistent")
