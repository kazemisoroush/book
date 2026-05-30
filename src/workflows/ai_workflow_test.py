"""Unit tests for AIWorkflow.

The workflow takes an AISectionParser and AnnouncementFormatter as
injected dependencies. Tests stub a single underlying AIProvider with
canned responses keyed off prompt shape, and wire it through both
collaborators via the _make_workflow helper.
"""
import json
from copy import deepcopy
from typing import Optional

from src.ai.ai_provider import AIProvider
from src.config.feature_flags import FeatureFlags
from src.domain.beat import BeatType
from src.domain.character import Character, make_default_narrator
from src.domain.character_registry import CharacterRegistry
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    BookParseContext,
    Chapter,
    SceneRegistry,
    Section,
)
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.book_source import BookSource
from src.prompts.models.ai_prompt import AIPrompt
from src.prompts.models.book_title_prompt import BookTitleAnnouncementPrompt
from src.prompts.models.chapter_announcement_prompt import ChapterAnnouncementPrompt
from src.prompts.runners.announcement_formatter import AnnouncementFormatter
from src.repository.book_repository import BookRepository
from src.workflows.ai_workflow import AIWorkflow
from src.workflows.workflow import WorkflowRequest

_URL = "http://example.com/test"
_NO_ANNOUNCER = FeatureFlags(chapter_announcer_enabled=False)


def _default_metadata() -> BookMetadata:
    return BookMetadata(
        title="Test Book",
        author="Test Author",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )


def _section_response(
    text: str,
    *,
    new_characters: Optional[list[Character]] = None,
) -> str:
    """Build a JSON response that AISectionParser will consume into a single narration beat."""
    payload: dict = {
        "beats": [{"type": "narration", "text": text, "speaker": "narrator"}],
        "new_characters": [
            {
                "character_id": c.character_id,
                "name": c.name,
                "description": c.description,
                "sex": c.sex,
                "age": c.age,
            }
            for c in (new_characters or [])
        ],
        "character_description_updates": [],
    }
    return json.dumps(payload)


class _FakeAIProvider(AIProvider):
    """Stub provider that dispatches by prompt type.

    Announcement prompts (BookTitleAnnouncementPrompt / ChapterAnnouncementPrompt)
    return a short string echo. Anything else is treated as a section-parse
    request and consumes the next entry from ``section_responses``.
    """

    def __init__(self, section_responses: Optional[list[str]] = None) -> None:
        self._section_responses = list(section_responses or [])
        self._section_call_index = 0
        self.section_calls = 0
        self.announcement_calls = 0

    def generate(self, prompt: AIPrompt, max_tokens: int = 1000) -> str:
        if isinstance(prompt, BookTitleAnnouncementPrompt):
            self.announcement_calls += 1
            return "Spoken book title"
        if isinstance(prompt, ChapterAnnouncementPrompt):
            self.announcement_calls += 1
            return "Spoken chapter announcement"
        self.section_calls += 1
        response = self._section_responses[self._section_call_index]
        self._section_call_index += 1
        return response


class _FakeBookSource(BookSource):
    """BookSource stub that returns pre-configured books and parse contexts."""

    def __init__(
        self,
        book: Optional[Book] = None,
        chapters_to_parse: Optional[list[Chapter]] = None,
        content: Optional[BookContent] = None,
    ) -> None:
        self._book = book or Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=[]),
            character_registry=CharacterRegistry(characters=[make_default_narrator("book")]),
            scene_registry=SceneRegistry(),
        )
        self._chapters_to_parse = chapters_to_parse or []
        self._content = content or BookContent(chapters=self._chapters_to_parse)

    def get_book(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> BookParseContext:
        return BookParseContext(
            book=self._book,
            chapters_to_parse=self._chapters_to_parse,
            content=self._content,
        )


class _RecordingRepository(BookRepository):
    """In-memory repository that snapshots each save() call."""

    def __init__(self, initial: Optional[Book] = None) -> None:
        self._default = initial
        self._store: dict[str, Book] = {}
        self.save_calls: list[tuple[str, Book]] = []

    def save(self, book: Book, book_id: str) -> None:
        snapshot = deepcopy(book)
        self._store[book_id] = snapshot
        self.save_calls.append((book_id, snapshot))

    def load(self, book_id: str) -> Optional[Book]:
        return self._store.get(book_id, self._default)

    def exists(self, book_id: str) -> bool:
        return book_id in self._store or self._default is not None


def _chapter(number: int, text: Optional[str] = None) -> Chapter:
    return Chapter(
        number=number,
        title=f"Chapter {number}",
        sections=[Section(text=text or f"Chapter {number} text.")],
    )


def _make_workflow(
    provider: AIProvider,
    book_source: BookSource,
    repository: Optional[BookRepository] = None,
) -> AIWorkflow:
    return AIWorkflow(
        book_source=book_source,
        section_parser=AISectionParser(provider),
        announcement_formatter=AnnouncementFormatter(provider),
        repository=repository or _RecordingRepository(),
    )


def test_cached_book_skips_ai_provider() -> None:
    """When BookSource returns no chapters to parse, the provider is never called."""
    cached_book = Book(
        metadata=_default_metadata(),
        content=BookContent(chapters=[_chapter(1)]),
        character_registry=CharacterRegistry(characters=[make_default_narrator("book")]),
        scene_registry=SceneRegistry(),
    )
    provider = _FakeAIProvider()
    workflow = _make_workflow(
        provider,
        _FakeBookSource(book=cached_book, chapters_to_parse=[]),
    )

    book = workflow.run(WorkflowRequest(url=_URL, end_chapter=1, feature_flags=_NO_ANNOUNCER))

    assert provider.section_calls == 0
    assert provider.announcement_calls == 0
    assert book.to_dict() == cached_book.to_dict()


def test_workflow_saves_after_each_chapter() -> None:
    """Repository.save is called once per parsed chapter, with growing chapter counts."""
    chapters = [_chapter(i) for i in range(1, 4)]
    provider = _FakeAIProvider(
        section_responses=[_section_response(f"Ch {i}") for i in range(1, 4)],
    )
    repo = _RecordingRepository()
    workflow = _make_workflow(
        provider, _FakeBookSource(chapters_to_parse=chapters), repository=repo,
    )

    workflow.run(WorkflowRequest(
        url=_URL, end_chapter=3, refresh=True, feature_flags=_NO_ANNOUNCER,
    ))

    assert provider.section_calls == 3
    assert len(repo.save_calls) == 3
    for i, (_book_id, snapshot) in enumerate(repo.save_calls, start=1):
        assert len(snapshot.content.chapters) == i


def test_auto_resume_only_parses_uncached_chapters() -> None:
    """BookSource reporting only chapters 3-5 means the provider is called exactly three times."""
    cached_chapters = [_chapter(1), _chapter(2)]
    to_parse = [_chapter(3), _chapter(4), _chapter(5)]
    cached_book = Book(
        metadata=_default_metadata(),
        content=BookContent(chapters=list(cached_chapters)),
        character_registry=CharacterRegistry(characters=[make_default_narrator("book")]),
        scene_registry=SceneRegistry(),
    )

    provider = _FakeAIProvider(
        section_responses=[_section_response(f"Ch {i}") for i in range(3, 6)],
    )
    repo = _RecordingRepository()
    workflow = _make_workflow(
        provider,
        _FakeBookSource(
            book=cached_book,
            chapters_to_parse=to_parse,
            content=BookContent(chapters=cached_chapters + to_parse),
        ),
        repository=repo,
    )

    book = workflow.run(WorkflowRequest(
        url=_URL, start_chapter=1, end_chapter=5, feature_flags=_NO_ANNOUNCER,
    ))

    assert provider.section_calls == 3
    assert len(book.content.chapters) == 5
    assert len(repo.save_calls) == 3


def test_non_contiguous_chapters_are_merged_in_sorted_order() -> None:
    """Cached chapter 20 plus parsed 19 and 21 ends up as [19, 20, 21]."""
    cached_book = Book(
        metadata=_default_metadata(),
        content=BookContent(chapters=[_chapter(20)]),
        character_registry=CharacterRegistry(characters=[make_default_narrator("book")]),
        scene_registry=SceneRegistry(),
    )
    to_parse = [_chapter(19), _chapter(21)]
    provider = _FakeAIProvider(
        section_responses=[_section_response("Ch 19"), _section_response("Ch 21")],
    )
    workflow = _make_workflow(
        provider,
        _FakeBookSource(
            book=cached_book,
            chapters_to_parse=to_parse,
            content=BookContent(chapters=[_chapter(19), _chapter(20), _chapter(21)]),
        ),
    )

    book = workflow.run(WorkflowRequest(
        url=_URL, start_chapter=19, end_chapter=21, feature_flags=_NO_ANNOUNCER,
    ))

    assert [ch.number for ch in book.content.chapters] == [19, 20, 21]


def test_characters_emitted_by_ai_appear_in_saved_book() -> None:
    """New characters returned by the AI for any section persist into the saved book."""
    alice = Character(
        character_id="alice", name="Alice", description="A curious young woman.",
        sex="female", age="adult",
    )
    provider = _FakeAIProvider(
        section_responses=[_section_response("Alice arrived.", new_characters=[alice])],
    )
    repo = _RecordingRepository()
    workflow = _make_workflow(
        provider, _FakeBookSource(chapters_to_parse=[_chapter(1)]), repository=repo,
    )

    book = workflow.run(WorkflowRequest(
        url=_URL, end_chapter=1, refresh=True, feature_flags=_NO_ANNOUNCER,
    ))

    found = book.character_registry.get("Test Book - Test Author:alice")
    assert found is not None
    assert found.name == "Alice"
    assert repo.save_calls[-1][1].character_registry.get(
        "Test Book - Test Author:alice"
    ) is not None


def test_first_chapter_gets_book_title_and_chapter_announcement() -> None:
    """With the announcer flag on, chapter 1 is prefixed with both synthetic sections."""
    provider = _FakeAIProvider(section_responses=[_section_response("Opening.")])
    workflow = _make_workflow(
        provider, _FakeBookSource(chapters_to_parse=[_chapter(1, text="Opening.")]),
    )

    book = workflow.run(WorkflowRequest(url=_URL, end_chapter=1))

    sections = book.content.chapters[0].sections
    assert [s.section_type for s in sections[:2]] == ["book_title", "chapter_announcement"]
    assert "Test Book" in sections[0].text
    assert sections[0].beats is not None
    assert sections[0].beats[0].beat_type == BeatType.BOOK_TITLE
    assert sections[1].beats is not None
    assert sections[1].beats[0].beat_type == BeatType.CHAPTER_ANNOUNCEMENT
    assert provider.section_calls == 1
    assert provider.announcement_calls == 2


def test_subsequent_chapters_get_only_chapter_announcement() -> None:
    """Chapters after the first receive a single chapter_announcement prefix."""
    provider = _FakeAIProvider(
        section_responses=[_section_response("Ch1."), _section_response("Ch2.")],
    )
    workflow = _make_workflow(
        provider,
        _FakeBookSource(
            chapters_to_parse=[_chapter(1, text="Ch1."), _chapter(2, text="Ch2.")],
        ),
    )

    book = workflow.run(WorkflowRequest(url=_URL, end_chapter=2))

    ch2_sections = book.content.chapters[1].sections
    assert len(ch2_sections) == 2
    assert ch2_sections[0].section_type == "chapter_announcement"


def test_announcer_disabled_means_no_synthetic_sections() -> None:
    """With the announcer flag off, no synthetic sections are inserted and no formatter calls are made."""
    provider = _FakeAIProvider(section_responses=[_section_response("Opening.")])
    workflow = _make_workflow(
        provider, _FakeBookSource(chapters_to_parse=[_chapter(1, text="Opening.")]),
    )

    book = workflow.run(WorkflowRequest(url=_URL, end_chapter=1, feature_flags=_NO_ANNOUNCER))

    assert len(book.content.chapters[0].sections) == 1
    assert provider.announcement_calls == 0
