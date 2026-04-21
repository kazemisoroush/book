"""Tests for AmbientWorkflow."""
from pathlib import Path
from unittest.mock import Mock, patch

from src.workflows.ambient_workflow import AmbientWorkflow
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Scene,
    SceneRegistry,
    Section,
    Segment,
    SegmentType,
)
from src.repository.book_repository import BookRepository


class TestAmbientWorkflowConstructor:
    """Test AmbientWorkflow accepts provider and books_dir."""

    def test_accepts_provider_and_books_dir(self) -> None:
        """AmbientWorkflow constructor accepts AmbientProvider and books_dir."""
        # Arrange
        mock_provider = Mock()
        mock_repository = Mock()
        books_dir = Path("/tmp/books")

        # Act
        workflow = AmbientWorkflow(
            provider=mock_provider,
            repository=mock_repository,
            books_dir=books_dir,
        )

        # Assert
        assert workflow._provider == mock_provider
        assert workflow._books_dir == books_dir


class TestAmbientWorkflowCreate:
    """Test AmbientWorkflow.create() factory."""

    def test_create_instantiates_provider(self) -> None:
        """create() reads STABILITY_API_KEY and instantiates StableAudioAmbientProvider."""
        # Arrange
        mock_config = Mock()
        mock_config.stability_api_key = "test-key"

        # Act
        with patch("src.workflows.ambient_workflow.get_config", return_value=mock_config):
            workflow = AmbientWorkflow.create()

        # Assert
        # Verify workflow was created with default books_dir
        assert workflow._books_dir == Path("books")


class TestAmbientWorkflowRun:
    """Tests for AmbientWorkflow.run method."""

    def test_run_loads_and_saves_book_via_repository(self) -> None:
        """AmbientWorkflow.run() loads book from repository and saves it back."""
        # Arrange
        url = "https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip"
        mock_repository = Mock(spec=BookRepository)
        mock_book = Book(
            metadata=BookMetadata(
                title="Pride and Prejudice",
                author="Jane Austen",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[]),
        )
        mock_repository.load.return_value = mock_book

        # Mock the URL mapper to avoid actual HTTP calls
        with patch("src.workflows.ambient_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "Pride and Prejudice - Jane Austen"

            workflow = AmbientWorkflow(repository=mock_repository)

            # Act
            result = workflow.run(url)

        # Assert
        assert result == mock_book
        mock_repository.load.assert_called_once_with("Pride and Prejudice - Jane Austen")
        mock_repository.save.assert_called_once()
        saved_book, saved_book_id = mock_repository.save.call_args[0]
        assert saved_book == mock_book
        assert saved_book_id == "Pride and Prejudice - Jane Austen"

    def test_calls_provider_generate_for_scenes_with_ambient_prompt(self) -> None:
        """run() calls provider.generate() for each scene with ambient_prompt."""
        # Arrange
        mock_provider = Mock()
        mock_provider.generate.return_value = Path("/fake/ambient.mp3")

        mock_repository = Mock()

        # Create a book with a scene that has an ambient_prompt
        scene = Scene(
            scene_id="scene_1",
            environment="forest",
            ambient_prompt="gentle forest sounds",
            ambient_volume=-18.0,
        )
        scene_registry = SceneRegistry()
        scene_registry.upsert(scene)

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            scene_id="scene_1",
            duration_seconds=10.0,
        )
        section = Section(text="Test", segments=[segment])
        chapter = Chapter(number=1, title="Chapter 1", sections=[section])
        book = Book(
            metadata=BookMetadata(
                title="Test Book",
                author="Test Author",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[chapter]),
            scene_registry=scene_registry,
        )
        mock_repository.load.return_value = book

        with patch("src.workflows.ambient_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = AmbientWorkflow(
                provider=mock_provider,
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args[0][0] == "gentle forest sounds"  # prompt
        assert call_args[1]["duration_seconds"] == 10.0

    def test_stores_generated_paths_in_chapter_ambient_audio_paths(self) -> None:
        """run() stores generated paths in chapter.ambient_audio_paths."""
        # Arrange
        generated_path = Path("/tmp/books/123/audio/ambient/scene_1.mp3")
        mock_provider = Mock()
        mock_provider.generate.return_value = generated_path

        mock_repository = Mock()

        scene = Scene(
            scene_id="scene_1",
            environment="forest",
            ambient_prompt="gentle forest sounds",
        )
        scene_registry = SceneRegistry()
        scene_registry.upsert(scene)

        segment = Segment(
            text="Test",
            segment_type=SegmentType.NARRATION,
            scene_id="scene_1",
            duration_seconds=10.0,
        )
        section = Section(text="Test", segments=[segment])
        chapter = Chapter(number=1, title="Chapter 1", sections=[section])
        book = Book(
            metadata=BookMetadata(
                title="Test Book",
                author="Test Author",
                releaseDate=None,
                language=None,
                originalPublication=None,
                credits=None,
            ),
            content=BookContent(chapters=[chapter]),
            scene_registry=scene_registry,
        )
        mock_repository.load.return_value = book

        with patch("src.workflows.ambient_workflow.get_book_id_from_url") as mock_mapper:
            mock_mapper.return_value = "123"

            workflow = AmbientWorkflow(
                provider=mock_provider,
                repository=mock_repository,
                books_dir=Path("/tmp/books"),
            )

            # Act
            result = workflow.run(url="https://www.gutenberg.org/ebooks/123")

        # Assert
        assert len(result.content.chapters[0].ambient_audio_paths) == 1
        assert result.content.chapters[0].ambient_audio_paths[0] == str(generated_path)
