"""Tests for :class:`StudioBookRepository`."""
from dataclasses import dataclass, field
from typing import Optional

from src.domain.beat import Beat, BeatType
from src.domain.character import make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
)
from src.repository.studio_book_repository import StudioBookRepository

_DEFAULT_VOICE = "voice-default"


@dataclass
class _StubProject:
    project_id: str
    name: str


@dataclass
class _StubChapter:
    chapter_id: str
    name: str


@dataclass
class _StubProjectsList:
    projects: list[_StubProject]


@dataclass
class _StubChaptersList:
    chapters: list[_StubChapter]


@dataclass
class _StubAddProjectResponse:
    project: _StubProject


@dataclass
class _StubAddChapterResponse:
    chapter: _StubChapter


@dataclass
class _RecordedCreateProject:
    name: str
    default_paragraph_voice_id: Optional[str]
    title: Optional[str]
    author: Optional[str]
    source_type: Optional[str]


@dataclass
class _RecordedCreateChapter:
    project_id: str
    name: str


@dataclass
class _RecordedUpdateChapter:
    project_id: str
    chapter_id: str
    content: dict


@dataclass
class _FakeChaptersClient:
    list_calls: list[str] = field(default_factory=list)
    create_calls: list[_RecordedCreateChapter] = field(default_factory=list)
    update_calls: list[_RecordedUpdateChapter] = field(default_factory=list)
    existing: dict[str, list[_StubChapter]] = field(default_factory=dict)
    next_chapter_id: int = 1

    def list(self, project_id: str) -> _StubChaptersList:
        self.list_calls.append(project_id)
        return _StubChaptersList(chapters=list(self.existing.get(project_id, [])))

    def create(self, project_id: str, *, name: str) -> _StubAddChapterResponse:
        chapter_id = f"chapter-{self.next_chapter_id}"
        self.next_chapter_id += 1
        self.create_calls.append(_RecordedCreateChapter(project_id, name))
        chapter = _StubChapter(chapter_id=chapter_id, name=name)
        self.existing.setdefault(project_id, []).append(chapter)
        return _StubAddChapterResponse(chapter=chapter)

    def update(self, project_id: str, chapter_id: str, *, content: dict) -> None:
        self.update_calls.append(_RecordedUpdateChapter(project_id, chapter_id, content))


@dataclass
class _FakeProjectsClient:
    chapters: _FakeChaptersClient
    list_calls: int = 0
    create_calls: list[_RecordedCreateProject] = field(default_factory=list)
    existing: list[_StubProject] = field(default_factory=list)
    next_project_id: int = 1

    def list(self) -> _StubProjectsList:
        self.list_calls += 1
        return _StubProjectsList(projects=list(self.existing))

    def create(
        self,
        *,
        name: str,
        default_paragraph_voice_id: Optional[str] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> _StubAddProjectResponse:
        project_id = f"project-{self.next_project_id}"
        self.next_project_id += 1
        self.create_calls.append(_RecordedCreateProject(
            name=name,
            default_paragraph_voice_id=default_paragraph_voice_id,
            title=title,
            author=author,
            source_type=source_type,
        ))
        project = _StubProject(project_id=project_id, name=name)
        self.existing.append(project)
        return _StubAddProjectResponse(project=project)


@dataclass
class _FakeStudio:
    projects: _FakeProjectsClient


@dataclass
class _FakeClient:
    studio: _FakeStudio


def _make_client() -> tuple[_FakeClient, _FakeProjectsClient, _FakeChaptersClient]:
    chapters = _FakeChaptersClient()
    projects = _FakeProjectsClient(chapters=chapters)
    studio = _FakeStudio(projects=projects)
    return _FakeClient(studio=studio), projects, chapters


def _book(
    chapters: list[Chapter],
    voice_assignments: Optional[dict[int, str]] = None,
) -> Book:
    metadata = BookMetadata(
        title="Pride and Prejudice",
        author="Jane Austen",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )
    registry = CharacterRegistry(characters=[make_default_narrator()])
    return Book(
        metadata=metadata,
        content=BookContent(chapters=chapters),
        character_registry=registry,
        voice_assignments=voice_assignments or {},
    )


def _narration_chapter(number: int = 1) -> Chapter:
    return Chapter(
        number=number,
        title="",
        beats=[
            Beat(text="It is a truth.", beat_type=BeatType.NARRATION, character_id=1),
            Beat(text="My dear Mr. Bennet.", beat_type=BeatType.DIALOGUE, character_id=2),
        ],
    )


def test_save_chapter_creates_project_and_chapter_when_neither_exists() -> None:
    # Arrange
    client, projects, chapters = _make_client()
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)
    book = _book([_narration_chapter()])

    # Act
    repo.save_chapter(book, book.content.chapters[0])

    # Assert
    assert [c.name for c in projects.create_calls] == [book.book_id]
    assert chapters.create_calls == [_RecordedCreateChapter("project-1", "Chapter 1")]
    assert len(chapters.update_calls) == 1
    update = chapters.update_calls[0]
    assert update.project_id == "project-1"
    assert update.chapter_id == "chapter-1"


def test_save_chapter_reuses_existing_project_matched_by_book_id() -> None:
    # Arrange
    client, projects, chapters = _make_client()
    projects.existing.append(_StubProject(project_id="cached", name="other-book"))
    book = _book([_narration_chapter()])
    projects.existing.append(_StubProject(project_id="found", name=book.book_id))
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)

    # Act
    repo.save_chapter(book, book.content.chapters[0])

    # Assert
    assert projects.create_calls == []
    assert chapters.create_calls[0].project_id == "found"
    assert chapters.update_calls[0].project_id == "found"


def test_save_chapter_reuses_existing_chapter_matched_by_name() -> None:
    # Arrange
    client, projects, chapters = _make_client()
    book = _book([_narration_chapter()])
    projects.existing.append(_StubProject(project_id="proj", name=book.book_id))
    chapters.existing["proj"] = [_StubChapter(chapter_id="cached-1", name="Chapter 1")]
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)

    # Act
    repo.save_chapter(book, book.content.chapters[0])

    # Assert
    assert chapters.create_calls == []
    assert chapters.update_calls[0].chapter_id == "cached-1"


def test_save_chapter_caches_project_id_across_calls() -> None:
    # Arrange
    client, projects, chapters = _make_client()
    book = _book([_narration_chapter(1), _narration_chapter(2)])
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)

    # Act
    repo.save_chapter(book, book.content.chapters[0])
    repo.save_chapter(book, book.content.chapters[1])

    # Assert
    assert projects.list_calls == 1
    assert len(projects.create_calls) == 1


def test_save_chapter_builds_one_block_per_narratable_beat_with_voice_mapping() -> None:
    # Arrange
    client, _, chapters = _make_client()
    book = _book(
        [_narration_chapter()],
        voice_assignments={1: "voice-narrator", 2: "voice-bennet"},
    )
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)

    # Act
    repo.save_chapter(book, book.content.chapters[0])

    # Assert
    blocks = chapters.update_calls[0].content["blocks"]
    assert len(blocks) == 2
    assert blocks[0] == {
        "sub_type": "p",
        "nodes": [{
            "type": "tts_node",
            "text": "It is a truth.",
            "voice_id": "voice-narrator",
        }],
    }
    assert blocks[1]["nodes"][0]["voice_id"] == "voice-bennet"


def test_save_chapter_falls_back_to_default_voice_when_unassigned() -> None:
    # Arrange
    client, _, chapters = _make_client()
    book = _book([_narration_chapter()])  # No voice assignments.
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)

    # Act
    repo.save_chapter(book, book.content.chapters[0])

    # Assert
    blocks = chapters.update_calls[0].content["blocks"]
    assert all(n["voice_id"] == _DEFAULT_VOICE for b in blocks for n in b["nodes"])


def test_save_chapter_skips_non_narratable_beats() -> None:
    # Arrange
    client, _, chapters = _make_client()
    chapter = Chapter(
        number=3, title="",
        beats=[
            Beat(text="ad copy", beat_type=BeatType.COPYRIGHT, character_id=1),
            Beat(text="boom", beat_type=BeatType.SOUND_EFFECT, character_id=None),
            Beat(text="hello", beat_type=BeatType.NARRATION, character_id=1),
        ],
    )
    book = _book([chapter])
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)

    # Act
    repo.save_chapter(book, chapter)

    # Assert
    blocks = chapters.update_calls[0].content["blocks"]
    assert len(blocks) == 1
    assert blocks[0]["nodes"][0]["text"] == "hello"


def test_save_chapter_skips_studio_when_chapter_has_no_narratable_beats() -> None:
    # Arrange
    client, projects, chapters = _make_client()
    chapter = Chapter(
        number=4, title="",
        beats=[Beat(text="bang", beat_type=BeatType.SOUND_EFFECT)],
    )
    book = _book([chapter])
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)

    # Act
    repo.save_chapter(book, chapter)

    # Assert
    assert projects.create_calls == []
    assert chapters.create_calls == []
    assert chapters.update_calls == []


def test_save_input_save_and_reads_are_no_ops() -> None:
    # Arrange
    client, projects, chapters = _make_client()
    repo = StudioBookRepository(client=client, default_voice_id=_DEFAULT_VOICE)
    book = _book([_narration_chapter()])

    # Act
    repo.save(book)
    repo.save_input(book)

    # Assert
    assert projects.create_calls == []
    assert chapters.create_calls == []
    assert repo.load(book.book_id) is None
    assert repo.load_input(book.book_id) is None
    assert repo.exists(book.book_id) is False
