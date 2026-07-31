"""Tests for CastingCandidatesWorkflow."""
import json
from pathlib import Path

import pytest

from src.characters.character_provider import (
    DEFAULT_CANDIDATE_LIMIT,
    CharacterProvider,
)
from src.characters.voice_candidate import VoiceCandidate
from src.domain.character import Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book, BookContent, BookMetadata
from src.downloader.file_downloader import FileDownloader
from src.repository.file_book_repository import FileBookRepository
from src.storage.local_storage import LocalStorage
from src.workflows.casting_candidates_workflow import CastingCandidatesWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"
_ALICE_ID = 2


def _candidate(voice_id: str) -> VoiceCandidate:
    return VoiceCandidate(
        voice_id=voice_id,
        public_owner_id=f"own_{voice_id}",
        name=f"Voice {voice_id}",
        preview_url=f"https://cdn.example.com/{voice_id}.mp3",
    )


class _StubCharacterProvider(CharacterProvider):
    """Returns a fixed shortlist and records who it was asked about."""

    def __init__(self, candidates: list[VoiceCandidate]) -> None:
        self._candidates = candidates
        self.asked: list[int] = []

    def upsert(
        self, character: Character, book_id: str, refresh: bool = False,
    ) -> str:
        raise AssertionError("upsert must not be called while shortlisting")

    def candidates(
        self, character: Character, limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> list[VoiceCandidate]:
        self.asked.append(character.id)
        return self._candidates


class _RecordingDownloader(FileDownloader):
    """Counts downloads per url and can be told to fail for one of them."""

    def __init__(self, failing_url: str = "") -> None:
        self.urls: list[str] = []
        self._failing_url = failing_url

    def download_bytes(self, url: str) -> bytes:
        self.urls.append(url)
        if url == self._failing_url:
            raise RuntimeError(f"Failed to download {url!r}")
        return b"audio"


def _patch_resolver(monkeypatch: pytest.MonkeyPatch, book_id: str) -> None:
    monkeypatch.setattr(
        "src.workflows.casting_candidates_workflow.get_book_id_from_url",
        lambda _url: book_id,
    )


def _save_book(
    tmp_path: Path, voice_assignments: "dict[int, str] | None" = None,
) -> tuple[FileBookRepository, str]:
    metadata = BookMetadata(
        title="The Book", author="Author", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    registry = CharacterRegistry(characters=[make_default_narrator()])
    registry.add(Character(
        id=_ALICE_ID, name="Alice", gender="female", age="young", accent="british",
    ))
    book = Book(
        metadata=metadata,
        content=BookContent(chapters=[]),
        character_registry=registry,
        voice_assignments=voice_assignments or {},
    )
    store = FileBookRepository(base_dir=str(tmp_path))
    store.save(book)
    return store, metadata.book_id


def _make_workflow(
    tmp_path: Path,
    store: FileBookRepository,
    provider: _StubCharacterProvider,
    downloader: _RecordingDownloader,
) -> CastingCandidatesWorkflow:
    return CastingCandidatesWorkflow(
        repositories=[store],
        character_provider=provider,
        downloader=downloader,
        storage=LocalStorage(base_dir=str(tmp_path)),
    )


def _read_candidates(tmp_path: Path, book_id: str, slug: str) -> dict:  # type: ignore[type-arg]
    path = tmp_path / book_id / "casting" / slug / "candidates.json"
    return json.loads(path.read_text())


def test_writes_candidates_per_character(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store, book_id = _save_book(tmp_path)
    _patch_resolver(monkeypatch, book_id)
    provider = _StubCharacterProvider([_candidate("sv1"), _candidate("sv2")])
    workflow = _make_workflow(tmp_path, store, provider, _RecordingDownloader())

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    alice = _read_candidates(tmp_path, book_id, "alice")
    assert alice["character_id"] == _ALICE_ID
    assert [c["voice_id"] for c in alice["candidates"]] == ["sv1", "sv2"]
    assert alice["candidates"][0]["preview_path"] == "casting/alice/preview_sv1.mp3"
    assert _read_candidates(tmp_path, book_id, "narrator")["character_name"] == "Narrator"


def test_preview_downloaded_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store, book_id = _save_book(tmp_path)
    _patch_resolver(monkeypatch, book_id)
    provider = _StubCharacterProvider([_candidate("sv1")])
    downloader = _RecordingDownloader()
    workflow = _make_workflow(tmp_path, store, provider, downloader)

    # Act
    workflow.run(WorkflowRequest(url=_URL))
    after_first_run = list(downloader.urls)
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert (tmp_path / book_id / "casting" / "alice" / "preview_sv1.mp3").exists()
    assert downloader.urls == after_first_run  # second run downloads nothing again


def test_recorded_assignment_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store, book_id = _save_book(tmp_path, voice_assignments={_ALICE_ID: "chosen_v"})
    _patch_resolver(monkeypatch, book_id)
    provider = _StubCharacterProvider([_candidate("sv1")])
    workflow = _make_workflow(tmp_path, store, provider, _RecordingDownloader())

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    assert _ALICE_ID not in provider.asked
    assert not (tmp_path / book_id / "casting" / "alice").exists()


def test_failed_preview_does_not_abort_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store, book_id = _save_book(tmp_path)
    _patch_resolver(monkeypatch, book_id)
    provider = _StubCharacterProvider([_candidate("dead"), _candidate("sv2")])
    downloader = _RecordingDownloader(failing_url="https://cdn.example.com/dead.mp3")
    workflow = _make_workflow(tmp_path, store, provider, downloader)

    # Act
    workflow.run(WorkflowRequest(url=_URL))

    # Assert
    alice = _read_candidates(tmp_path, book_id, "alice")
    assert [c["voice_id"] for c in alice["candidates"]] == ["sv2"]


def test_missing_book_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _patch_resolver(monkeypatch, "absent:book")
    store = FileBookRepository(base_dir=str(tmp_path))
    provider = _StubCharacterProvider([])
    workflow = _make_workflow(tmp_path, store, provider, _RecordingDownloader())

    # Act / Assert
    with pytest.raises(ValueError, match="Run the 'ai' workflow first"):
        workflow.run(WorkflowRequest(url=_URL))
