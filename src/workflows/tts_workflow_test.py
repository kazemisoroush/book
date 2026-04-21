"""Tests for TTSWorkflow."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config.feature_flags import FeatureFlags
from src.domain.models import Book, BookContent, BookMetadata, Chapter, Section
from src.audio.tts.tts_provider import StubTTSProvider
from src.audio.tts.voice_assigner import VoiceEntry
from src.repository.file_book_repository import FileBookRepository
from src.repository.book_id import generate_book_id
from src.workflows.tts_workflow import TTSWorkflow


@pytest.fixture
def stub_tts_provider() -> StubTTSProvider:
    """Create a StubTTSProvider with minimal voice entries."""
    return StubTTSProvider([
        VoiceEntry(voice_id="v1", name="Voice 1", labels={}),
        VoiceEntry(voice_id="v2", name="Voice 2", labels={}),
    ])


def _make_book() -> Book:
    """Create a minimal test book."""
    return Book(
        metadata=BookMetadata(
            title="Test Book",
            author="Test Author",
            language="en",
            releaseDate=None,
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(chapters=[
            Chapter(number=1, title="Chapter 1", sections=[
                Section(text="Test section.", section_type=None, segments=None)
            ])
        ]),
    )


def test_run_loads_from_repository_and_synthesises(
    stub_tts_provider: StubTTSProvider,
    tmp_path: Path,
) -> None:
    """TTSWorkflow.run() loads book from repository and runs synthesis."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_tts_provider,
        books_dir=tmp_path,
    )

    with patch("src.workflows.tts_workflow.AudioOrchestrator") as MockOrch, \
         patch("src.workflows.tts_workflow.get_book_id_from_url") as mock_mapper:
        mock_orch_instance = MagicMock()
        MockOrch.return_value = mock_orch_instance
        mock_mapper.return_value = book_id

        # Act
        result = workflow.run(url="https://example.com/book.zip")

    # Assert
    assert result.metadata.title == "Test Book"
    mock_orch_instance.synthesize_chapter.assert_called_once()


def test_run_accepts_feature_flags(
    stub_tts_provider: StubTTSProvider,
    tmp_path: Path,
) -> None:
    """TTSWorkflow.run() accepts feature_flags parameter."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_tts_provider,
        books_dir=tmp_path,
    )
    flags = FeatureFlags(emotion_enabled=False, voice_design_enabled=False)

    with patch("src.workflows.tts_workflow.AudioOrchestrator") as MockOrch, \
         patch("src.workflows.tts_workflow.get_book_id_from_url") as mock_mapper:
        MockOrch.return_value = MagicMock()
        mock_mapper.return_value = book_id

        # Act & Assert (should not raise)
        workflow.run(url="https://example.com/book.zip", feature_flags=flags)


def test_run_saves_book_back_to_repository(
    stub_tts_provider: StubTTSProvider,
    tmp_path: Path,
) -> None:
    """TTSWorkflow saves book to repository after synthesis."""
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = _make_book()
    book_id = generate_book_id(book.metadata)
    repository.save(book, book_id)

    workflow = TTSWorkflow(
        repository=repository,
        tts_provider=stub_tts_provider,
        books_dir=tmp_path,
    )

    with patch("src.workflows.tts_workflow.AudioOrchestrator") as MockOrch, \
         patch("src.workflows.tts_workflow.get_book_id_from_url") as mock_mapper:
        MockOrch.return_value = MagicMock()
        mock_mapper.return_value = book_id

        # Act
        workflow.run(url="https://example.com/book.zip")

    # Assert - book should still be in repository after TTS
    loaded = repository.load(book_id)
    assert loaded is not None
    assert loaded.metadata.title == "Test Book"


def test_create_requires_fish_audio_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """create() raises ValueError when FISH_AUDIO_API_KEY is missing."""
    # Arrange
    from src.config import reload_config

    monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)
    reload_config()

    # Act & Assert
    with pytest.raises(ValueError, match="FISH_AUDIO_API_KEY"):
        TTSWorkflow.create()


def test_create_instantiates_fish_audio_tts_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """create() instantiates FishAudioTTSProvider as the TTS provider."""
    # Arrange
    from src.config import reload_config

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-fish-key")
    reload_config()

    with patch("src.workflows.tts_workflow.FishAudioTTSProvider") as mock_fish_cls:
        mock_fish_cls.return_value = MagicMock()

        # Act
        TTSWorkflow.create()

    # Assert
    mock_fish_cls.assert_called_once_with(api_key="test-fish-key")
