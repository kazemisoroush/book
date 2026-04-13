"""Unit tests for AIProjectGutenbergWorkflow — US-014 AC3 + US-018 caching."""
from typing import Optional
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.parsers.book_source import BookSource
from src.parsers.book_section_parser import BookSectionParser
from src.repository.book_repository import BookRepository
from src.domain.models import (
    Book, Section, Segment, SegmentType, CharacterRegistry, Character,
    Chapter, BookContent, BookMetadata, Scene, SceneRegistry,
    BookParseContext,
)


def _default_metadata() -> BookMetadata:
    return BookMetadata(
        title="Test Book",
        author="Test Author",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )


class _FakeBookSource(BookSource):
    """Stub BookSource that returns pre-configured books and contexts."""

    def __init__(
        self,
        book: Optional[Book] = None,
        chapters_to_parse: Optional[list[Chapter]] = None,
        content: Optional[BookContent] = None,
    ) -> None:
        metadata = _default_metadata()
        self._book = book or Book(
            metadata=metadata,
            content=BookContent(chapters=[]),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )
        all_chapters = chapters_to_parse or []
        self._content = content or BookContent(chapters=all_chapters)
        self._chapters_to_parse = chapters_to_parse or []

    def get_book(self, url: str) -> Book:
        return self._book

    def get_book_for_segmentation(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        reparse: bool = False,
    ) -> BookParseContext:
        return BookParseContext(
            book=self._book,
            chapters_to_parse=self._chapters_to_parse,
            content=self._content,
        )


class _CapturingSectionParser(BookSectionParser):
    """Records prompts received from the workflow and returns pre-baked responses."""

    def __init__(self, responses: list[tuple[list[Segment], CharacterRegistry]]) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.registries_seen: list[CharacterRegistry] = []

    def parse(  # type: ignore[override]
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> tuple[list[Segment], CharacterRegistry]:
        self.registries_seen.append(registry)
        segments, updated_registry = self._responses[self._call_count]
        self._call_count += 1
        return segments, updated_registry


# ── AC3: workflow applies description updates between sections ─────────────────


class TestWorkflowAppliesDescriptionUpdatesBetweenSections:
    """Workflow applies character_description_updates immediately after each section (US-014 AC3)."""

    def test_description_update_in_first_section_is_visible_to_second_section_parser(
        self,
    ) -> None:
        """After section 1 is parsed and a description update is applied, section 2's
        parser call receives the registry with the updated description."""
        # Arrange
        section_1 = Section(text="Hagrid arrived.")
        section_2 = Section(text="Hagrid spoke again.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1, section_2])

        registry_after_section_1 = CharacterRegistry.with_default_narrator()
        registry_after_section_1.upsert(Character(
            character_id="hagrid",
            name="Rubeus Hagrid",
            sex="male",
            age="adult",
            description="booming bass voice, thick West Country accent; voice trembles when distressed",
        ))

        seg1 = Segment(text="Hagrid arrived.", segment_type=SegmentType.NARRATION, character_id="narrator")
        seg2 = Segment(text="Hagrid spoke again.", segment_type=SegmentType.NARRATION, character_id="narrator")

        capturing_parser = _CapturingSectionParser(
            responses=[
                ([seg1], registry_after_section_1),
                ([seg2], registry_after_section_1),
            ]
        )

        book_source = _FakeBookSource(chapters_to_parse=[chapter])
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
        )

        # Act
        workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert
        assert len(capturing_parser.registries_seen) == 2
        registry_for_section_2 = capturing_parser.registries_seen[1]
        hagrid_in_section_2 = registry_for_section_2.get("hagrid")
        assert hagrid_in_section_2 is not None
        assert hagrid_in_section_2.description == (
            "booming bass voice, thick West Country accent; voice trembles when distressed"
        )


# ── US-018: workflow uses cached book when repository returns one ─────────────


class _FakeRepository(BookRepository):
    """In-memory repository stub that records calls."""

    def __init__(self, stored: Optional[Book] = None) -> None:
        self._store: dict[str, Book] = {}
        self.save_calls: list[str] = []
        self.load_calls: list[str] = []
        self._default: Optional[Book] = stored

    def save(self, book: Book, book_id: str) -> None:
        self._store[book_id] = book
        self.save_calls.append(book_id)

    def load(self, book_id: str) -> Optional[Book]:
        self.load_calls.append(book_id)
        if book_id in self._store:
            return self._store[book_id]
        return self._default

    def exists(self, book_id: str) -> bool:
        if book_id in self._store:
            return True
        return self._default is not None


def _make_cached_book() -> Book:
    """Build a minimal cached Book."""
    metadata = _default_metadata()
    section = Section(
        text="Cached text.",
        segments=[
            Segment(
                text="Cached text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            ),
        ],
    )
    chapter = Chapter(number=1, title="Chapter 1", sections=[section])
    content = BookContent(chapters=[chapter])
    registry = CharacterRegistry.with_default_narrator()
    return Book(metadata=metadata, content=content, character_registry=registry)


class TestWorkflowUsesCachedBook:
    """Workflow returns cached book when repository has one (US-018 AC3)."""

    def test_cached_book_skips_ai_parser(self) -> None:
        """When BookSource returns no chapters_to_parse, section_parser.parse is never called."""
        # Arrange
        cached_book = _make_cached_book()

        seg1 = Segment(text="Some text.", segment_type=SegmentType.NARRATION, character_id="narrator")
        registry = CharacterRegistry.with_default_narrator()
        capturing_parser = _CapturingSectionParser(responses=[([seg1], registry)])

        # BookSource returns the cached book with no chapters to parse
        book_source = _FakeBookSource(book=cached_book, chapters_to_parse=[])
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
        )

        # Act
        book = workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert — section parser was never called
        assert capturing_parser._call_count == 0
        assert book.to_dict() == cached_book.to_dict()


class TestWorkflowReparsesWhenFlagSet:
    """Workflow calls AI parser when BookSource returns chapters to parse (US-018 AC5)."""

    def test_reparse_bypasses_cache(self) -> None:
        """When BookSource returns chapters to parse, the workflow runs AI and saves."""
        # Arrange
        section_1 = Section(text="Fresh text.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        seg1 = Segment(text="Fresh text.", segment_type=SegmentType.NARRATION, character_id="narrator")
        fresh_registry = CharacterRegistry.with_default_narrator()
        capturing_parser = _CapturingSectionParser(responses=[([seg1], fresh_registry)])

        repo = _FakeRepository()
        book_source = _FakeBookSource(chapters_to_parse=[chapter])
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        workflow.run(url="http://example.com/test", end_chapter=1, reparse=True)

        # Assert
        assert capturing_parser._call_count == 1
        assert len(repo.save_calls) == 1


# ── US-020: workflow threads SceneRegistry ────────────────────────────────────


class _SceneAwareSectionParser(BookSectionParser):
    """Section parser stub that upserts scenes into the SceneRegistry and stamps scene_id."""

    def __init__(
        self,
        responses: list[tuple[list[Segment], CharacterRegistry]],
        scenes: list["Scene | None"],
    ) -> None:
        self._responses = list(responses)
        self._scenes = list(scenes)
        self._call_count = 0
        self.last_detected_scene: "Scene | None" = None
        self.scene_registries_seen: list[SceneRegistry | None] = []

    def parse(  # type: ignore[override]
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
        *,
        scene_registry: Optional[SceneRegistry] = None,
    ) -> tuple[list[Segment], CharacterRegistry]:
        self.scene_registries_seen.append(scene_registry)
        segments, updated_registry = self._responses[self._call_count]
        detected = self._scenes[self._call_count]
        self.last_detected_scene = detected
        if detected is not None and scene_registry is not None:
            scene_registry.upsert(detected)
            for seg in segments:
                seg.scene_id = detected.scene_id
        self._call_count += 1
        return segments, updated_registry


class TestWorkflowThreadsSceneRegistry:
    """Workflow creates a SceneRegistry, threads it through parsing, and attaches to Book."""

    def test_workflow_passes_scene_registry_to_parser(self) -> None:
        """The workflow passes a SceneRegistry to every parser.parse() call."""
        # Arrange
        section_1 = Section(text="In the cave.")
        section_2 = Section(text="More cave text.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1, section_2])

        registry = CharacterRegistry.with_default_narrator()
        seg = Segment(text="In the cave.", segment_type=SegmentType.NARRATION, character_id="narrator")

        parser = _SceneAwareSectionParser(
            responses=[([seg], registry), ([seg], registry)],
            scenes=[None, None],
        )

        book_source = _FakeBookSource(chapters_to_parse=[chapter])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=parser)

        # Act
        workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert
        assert len(parser.scene_registries_seen) == 2
        for sr in parser.scene_registries_seen:
            assert isinstance(sr, SceneRegistry)

    def test_detected_scene_ends_up_in_book_scene_registry(self) -> None:
        """When parser detects a scene, it ends up in Book.scene_registry."""
        # Arrange
        section_1 = Section(text="In the cave.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        cave_scene = Scene(scene_id="scene_cave", environment="cave", acoustic_hints=["echo"])
        registry = CharacterRegistry.with_default_narrator()
        seg = Segment(text="In the cave.", segment_type=SegmentType.NARRATION, character_id="narrator")

        parser = _SceneAwareSectionParser(responses=[([seg], registry)], scenes=[cave_scene])
        book_source = _FakeBookSource(chapters_to_parse=[chapter])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=parser)

        # Act
        book = workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert
        cave = book.scene_registry.get("scene_cave")
        assert cave is not None
        assert cave.environment == "cave"

    def test_segments_get_scene_id_assigned(self) -> None:
        """Segments parsed with a detected scene carry the scene_id."""
        # Arrange
        section_1 = Section(text="In the cave.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        cave_scene = Scene(scene_id="scene_cave", environment="cave")
        registry = CharacterRegistry.with_default_narrator()
        seg = Segment(text="In the cave.", segment_type=SegmentType.NARRATION, character_id="narrator")

        parser = _SceneAwareSectionParser(responses=[([seg], registry)], scenes=[cave_scene])
        book_source = _FakeBookSource(chapters_to_parse=[chapter])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=parser)

        # Act
        book = workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert — index 1 because index 0 is the synthetic book_title section
        segments = book.content.chapters[0].sections[1].segments
        assert segments is not None
        assert segments[0].scene_id == "scene_cave"

    def test_no_scene_detected_means_empty_registry(self) -> None:
        """When parser detects no scenes, Book.scene_registry is empty."""
        # Arrange
        section_1 = Section(text="Some text.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        registry = CharacterRegistry.with_default_narrator()
        seg = Segment(text="Some text.", segment_type=SegmentType.NARRATION, character_id="narrator")

        parser = _SceneAwareSectionParser(responses=[([seg], registry)], scenes=[None])
        book_source = _FakeBookSource(chapters_to_parse=[chapter])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=parser)

        # Act
        book = workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert
        assert len(book.scene_registry.all()) == 0


# ── TD-005: Chapter-by-chapter flush and auto-resume ────────────────────────


class _FlushTrackingRepository(BookRepository):
    """Repository that records each save() call with a snapshot of the book at that moment."""

    def __init__(self, initial_book: Optional[Book] = None) -> None:
        self._store: dict[str, Book] = {}
        self.save_calls: list[tuple[str, Book]] = []
        self._default: Optional[Book] = initial_book

    def save(self, book: Book, book_id: str) -> None:
        from copy import deepcopy
        snapshot = deepcopy(book)
        self._store[book_id] = snapshot
        self.save_calls.append((book_id, snapshot))

    def load(self, book_id: str) -> Optional[Book]:
        if book_id in self._store:
            return self._store[book_id]
        return self._default

    def exists(self, book_id: str) -> bool:
        if book_id in self._store:
            return True
        return self._default is not None


def _make_chapters_to_parse(count: int, start: int = 1) -> list[Chapter]:
    """Create a list of chapters with one section each."""
    chapters = []
    for i in range(start, start + count):
        section = Section(text=f"Chapter {i} text.")
        chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
        chapters.append(chapter)
    return chapters


def _make_seg_responses(count: int) -> list[tuple[list[Segment], CharacterRegistry]]:
    """Create section parser responses for *count* sections."""
    responses = []
    for i in range(count):
        seg = Segment(
            text=f"Chapter {i + 1} text.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )
        registry = CharacterRegistry.with_default_narrator()
        responses.append(([seg], registry))
    return responses


class TestWorkflowAutoResumesFromCache:
    """Workflow processes only the chapters_to_parse from BookSource (auto-resume)."""

    def test_auto_resume_when_cache_exists(self) -> None:
        """When BookSource returns only uncached chapters, parser is called only for those."""
        # Arrange — BookSource says chapters 3-5 need parsing (1-2 cached)
        cached_chapters = _make_chapters_to_parse(2, start=1)
        chapters_to_parse = _make_chapters_to_parse(3, start=3)
        all_chapters = cached_chapters + chapters_to_parse

        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=list(cached_chapters)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(3))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=all_chapters),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=5)

        # Assert
        assert capturing_parser._call_count == 3
        assert len(book.content.chapters) == 5
        assert len(repo.save_calls) == 3

    def test_no_resume_when_reparse_is_true(self) -> None:
        """When BookSource returns all chapters (reparse), all are parsed."""
        # Arrange — BookSource returns all 5 chapters to parse
        chapters_to_parse = _make_chapters_to_parse(5)
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(5))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(chapters_to_parse=chapters_to_parse)
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=5, reparse=True)

        # Assert
        assert capturing_parser._call_count == 5
        assert len(book.content.chapters) == 5
        assert len(repo.save_calls) == 5


class TestWorkflowCacheWithNonOneStartChapter:
    """Workflow correctly handles chapter ranges where BookSource skips cached chapters."""

    def test_cache_is_loaded_even_when_start_chapter_gt_1(self) -> None:
        """Cached chapters 1-10 are in the book; only chapters 15-20 are to parse."""
        # Arrange
        cached_chapters = _make_chapters_to_parse(10, start=1)
        chapters_to_parse = _make_chapters_to_parse(6, start=15)
        all_chapters = _make_chapters_to_parse(25)

        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=list(cached_chapters)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(6))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=all_chapters),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=15, end_chapter=20)

        # Assert
        assert capturing_parser._call_count == 6
        assert len(book.content.chapters) == 16
        assert len(repo.save_calls) == 6
        assert book.content.chapters[0].number == 1
        assert book.content.chapters[9].number == 10
        assert book.content.chapters[10].number == 15
        assert book.content.chapters[15].number == 20

    def test_cache_load_respects_end_chapter_boundary(self) -> None:
        """Cached chapters 1-10; requesting end_chapter=5 means nothing to parse."""
        # Arrange
        cached_chapters = _make_chapters_to_parse(10, start=1)
        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=list(cached_chapters)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(10))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=[],
            content=BookContent(chapters=_make_chapters_to_parse(20)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=5)

        # Assert
        assert capturing_parser._call_count == 0
        assert len(book.content.chapters) == 10
        assert len(repo.save_calls) == 0
        assert book.content.chapters[0].number == 1
        assert book.content.chapters[9].number == 10

    def test_arbitrary_range_with_partial_cache(self) -> None:
        """Cached chapters 1-5; requesting 3-10 parses only 6-10."""
        # Arrange
        cached_chapters = _make_chapters_to_parse(5, start=1)
        chapters_to_parse = _make_chapters_to_parse(5, start=6)
        all_chapters = _make_chapters_to_parse(15)

        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=list(cached_chapters)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(5))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=all_chapters),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=3, end_chapter=10)

        # Assert
        assert capturing_parser._call_count == 5
        assert len(book.content.chapters) == 10
        assert len(repo.save_calls) == 5
        assert book.content.chapters[0].number == 1
        assert book.content.chapters[4].number == 5
        assert book.content.chapters[5].number == 6
        assert book.content.chapters[9].number == 10


class TestWorkflowChapterByChapterFlush:
    """Workflow saves partial book snapshot after each chapter completes."""

    def test_workflow_saves_partial_book_after_each_chapter(self) -> None:
        """Repository.save is called once per chapter, with increasing chapter counts."""
        # Arrange — 5 chapters, no cache
        chapters_to_parse = _make_chapters_to_parse(5)
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(5))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(chapters_to_parse=chapters_to_parse)
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=5, reparse=True)

        # Assert
        assert len(repo.save_calls) == 5
        for i, (_book_id, saved_book) in enumerate(repo.save_calls, start=1):
            assert len(saved_book.content.chapters) == i

    def test_partial_book_snapshot_has_metadata_and_registries(self) -> None:
        """Each saved partial book has metadata, character_registry, and scene_registry."""
        # Arrange
        chapters_to_parse = _make_chapters_to_parse(3)
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(3))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(chapters_to_parse=chapters_to_parse)
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=3, reparse=True)

        # Assert
        assert len(repo.save_calls) == 3
        for _book_id, saved_book in repo.save_calls:
            assert saved_book.metadata is not None
            assert saved_book.character_registry is not None
            assert saved_book.scene_registry is not None


class TestWorkflowFlushesRegistriesWithChapter:
    """Each per-chapter flush includes the up-to-date character and scene registries."""

    def test_flushed_snapshot_contains_characters_discovered_during_parsing(self) -> None:
        """After ch1 parse discovers 'Alice', the flushed snapshot's registry contains Alice."""
        # Arrange
        chapters_to_parse = _make_chapters_to_parse(2)

        alice = Character(character_id="alice", name="Alice")
        registry_with_alice = CharacterRegistry.with_default_narrator()
        registry_with_alice.upsert(alice)

        seg_responses = [
            (
                [Segment(text="Ch1 text.", segment_type=SegmentType.NARRATION, character_id="narrator")],
                registry_with_alice,
            ),
            (
                [Segment(text="Ch2 text.", segment_type=SegmentType.NARRATION, character_id="narrator")],
                registry_with_alice,
            ),
        ]
        capturing_parser = _CapturingSectionParser(responses=seg_responses)
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(chapters_to_parse=chapters_to_parse)
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=2, reparse=True)

        # Assert
        assert len(repo.save_calls) == 2
        for _book_id, saved_book in repo.save_calls:
            found = saved_book.character_registry.get("alice")
            assert found is not None
            assert found.name == "Alice"


class TestWorkflowSubsetParsing:
    """Workflow processes only the chapters provided by BookSource."""

    def test_subset_range_with_no_cache(self) -> None:
        """Parsing chapters 5-8 from BookSource processes only those 4 chapters."""
        # Arrange
        chapters_to_parse = _make_chapters_to_parse(4, start=5)
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(4))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=_make_chapters_to_parse(10)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=5, end_chapter=8, reparse=True)

        # Assert
        assert capturing_parser._call_count == 4
        assert len(book.content.chapters) == 4
        assert book.content.chapters[0].number == 5
        assert book.content.chapters[3].number == 8
        assert len(repo.save_calls) == 4

    def test_subset_range_with_partial_cache(self) -> None:
        """With cached chapters 1-4, BookSource returns 5-10 to parse."""
        # Arrange
        cached_chapters = _make_chapters_to_parse(4, start=1)
        chapters_to_parse = _make_chapters_to_parse(6, start=5)

        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=list(cached_chapters)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(6))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=_make_chapters_to_parse(10)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=10)

        # Assert
        assert capturing_parser._call_count == 6
        assert len(book.content.chapters) == 10
        assert len(repo.save_calls) == 6


class TestWorkflowCharacterAndSceneRegistryPreservedAcrossResume:
    """Character and scene registries are preserved when resuming from cache."""

    def test_character_registry_preserved_across_resume(self) -> None:
        """Character from cache is preserved; new characters added during resume."""
        # Arrange — cached book with alice
        cached_chapters = _make_chapters_to_parse(2, start=1)
        alice = Character(
            character_id="alice", name="Alice", sex="female", age="adult",
            description="A curious young woman.",
        )
        cached_registry = CharacterRegistry.with_default_narrator()
        cached_registry.upsert(alice)

        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=list(cached_chapters)),
            character_registry=cached_registry,
            scene_registry=SceneRegistry(),
        )

        chapters_to_parse = _make_chapters_to_parse(3, start=3)

        # Section parser returns registry with alice + bob
        bob = Character(
            character_id="bob", name="Bob", sex="male", age="adult",
            description="A mysterious stranger.",
        )
        seg_responses = []
        for _ in range(3):
            seg = Segment(text="text", segment_type=SegmentType.NARRATION, character_id="narrator")
            reg = CharacterRegistry.with_default_narrator()
            reg.upsert(alice)
            reg.upsert(bob)
            seg_responses.append(([seg], reg))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=_make_chapters_to_parse(5)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=5)

        # Assert
        alice_found = book.character_registry.get("alice")
        bob_found = book.character_registry.get("bob")
        assert alice_found is not None
        assert alice_found.name == "Alice"
        assert bob_found is not None
        assert bob_found.name == "Bob"

    def test_scene_registry_preserved_across_resume(self) -> None:
        """Scene from cache is preserved; new scenes added during resume."""
        # Arrange — cached book with scene_cave
        cached_chapters = _make_chapters_to_parse(2, start=1)
        cave_scene = Scene(scene_id="scene_cave", environment="cave", acoustic_hints=["echo"])
        cached_scene_registry = SceneRegistry()
        cached_scene_registry.upsert(cave_scene)

        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=list(cached_chapters)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=cached_scene_registry,
        )

        chapters_to_parse = _make_chapters_to_parse(3, start=3)

        seg_responses = _make_seg_responses(3)
        parser = _SceneAwareSectionParser(
            responses=seg_responses,
            scenes=[
                Scene(scene_id="scene_forest", environment="forest", acoustic_hints=["rustling"]),
                None,
                None,
            ],
        )

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=_make_chapters_to_parse(5)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=parser,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=5)

        # Assert
        cave = book.scene_registry.get("scene_cave")
        forest = book.scene_registry.get("scene_forest")
        assert cave is not None
        assert cave.environment == "cave"
        assert forest is not None
        assert forest.environment == "forest"


# ── Fix: Cache accumulates chapters across non-sequential runs ───────────────


class TestWorkflowCacheWithNonContiguousChapters:
    """Workflow correctly handles non-contiguous cached chapter numbers."""

    def test_cache_ch20_parse_19_to_21(self) -> None:
        """Cache has [ch20]; BookSource returns ch19 and ch21 to parse."""
        # Arrange
        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=_make_chapters_to_parse(1, start=20)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        chapters_to_parse = [
            Chapter(number=19, title="Chapter 19", sections=[Section(text="Ch 19.")]),
            Chapter(number=21, title="Chapter 21", sections=[Section(text="Ch 21.")]),
        ]

        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(2))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=_make_chapters_to_parse(24)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=19, end_chapter=21)

        # Assert
        assert capturing_parser._call_count == 2
        assert len(book.content.chapters) == 3
        assert [ch.number for ch in book.content.chapters] == [19, 20, 21]
        assert len(repo.save_calls) == 2

    def test_cache_ch1_to_3_parse_ch20(self) -> None:
        """Cache has [1, 2, 3]; BookSource returns ch20 to parse."""
        # Arrange
        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=_make_chapters_to_parse(3, start=1)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        chapters_to_parse = _make_chapters_to_parse(1, start=20)
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(1))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=_make_chapters_to_parse(24)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=20, end_chapter=20)

        # Assert
        assert capturing_parser._call_count == 1
        assert len(book.content.chapters) == 4
        assert [ch.number for ch in book.content.chapters] == [1, 2, 3, 20]
        assert len(repo.save_calls) == 1

    def test_cache_ch20_parse_1_to_3(self) -> None:
        """Cache has [ch20]; BookSource returns ch1-3 to parse."""
        # Arrange
        cached_book = Book(
            metadata=_default_metadata(),
            content=BookContent(chapters=_make_chapters_to_parse(1, start=20)),
            character_registry=CharacterRegistry.with_default_narrator(),
            scene_registry=SceneRegistry(),
        )

        chapters_to_parse = _make_chapters_to_parse(3, start=1)
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(3))
        repo = _FlushTrackingRepository()

        book_source = _FakeBookSource(
            book=cached_book,
            chapters_to_parse=chapters_to_parse,
            content=BookContent(chapters=_make_chapters_to_parse(24)),
        )
        workflow = AIProjectGutenbergWorkflow(
            book_source=book_source,
            section_parser=capturing_parser,
            repository=repo,
        )

        # Act
        book = workflow.run(url="http://example.com/test", start_chapter=1, end_chapter=3)

        # Assert
        assert capturing_parser._call_count == 3
        assert len(book.content.chapters) == 4
        assert [ch.number for ch in book.content.chapters] == [1, 2, 3, 20]
        assert len(repo.save_calls) == 3


# ── Deterministic book_title / chapter_announcement injection ─────────────────


class TestWorkflowInjectsSyntheticSections:
    """Workflow prepends synthetic book_title / chapter_announcement sections."""

    def test_first_chapter_gets_book_title_section_prepended(self) -> None:
        """Chapter 1 should have a synthetic book_title section as its first section."""
        # Arrange
        ch1 = Chapter(number=1, title="Chapter 1", sections=[
            Section(text="Opening line."),
        ])
        # Parser will be called for the synthetic section + the real section
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(2))
        book_source = _FakeBookSource(chapters_to_parse=[ch1])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=capturing_parser)

        # Act
        book = workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert — first section of chapter 1 has a book_title segment
        sections = book.content.chapters[0].sections
        first_seg = sections[0].segments
        assert first_seg is not None
        assert len(first_seg) == 1
        assert first_seg[0].segment_type == SegmentType.BOOK_TITLE
        assert first_seg[0].character_id == "narrator"
        assert "Test Book" in first_seg[0].text

    def test_subsequent_chapters_get_chapter_announcement_prepended(self) -> None:
        """Chapters after the first should have a chapter_announcement section prepended."""
        # Arrange
        ch1 = Chapter(number=1, title="Chapter 1", sections=[Section(text="Ch1.")])
        ch2 = Chapter(number=2, title="The Journey", sections=[Section(text="Ch2.")])
        # 2 synthetic + 2 real = 4 parser calls
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(4))
        book_source = _FakeBookSource(chapters_to_parse=[ch1, ch2])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=capturing_parser)

        # Act
        book = workflow.run(url="http://example.com/test", end_chapter=2)

        # Assert — chapter 2's first section is a chapter_announcement
        ch2_sections = book.content.chapters[1].sections
        first_seg = ch2_sections[0].segments
        assert first_seg is not None
        assert len(first_seg) == 1
        assert first_seg[0].segment_type == SegmentType.CHAPTER_ANNOUNCEMENT
        assert first_seg[0].character_id == "narrator"
        assert "The Journey" in first_seg[0].text

    def test_synthetic_sections_appear_in_context_window_for_subsequent_sections(self) -> None:
        """The synthetic section should be visible in the context_window of the next real section."""
        # Arrange
        ch1 = Chapter(number=1, title="Chapter 1", sections=[Section(text="Opening.")])

        class _ContextCapturingParser(BookSectionParser):
            def __init__(self) -> None:
                self.context_windows: list[list[Section] | None] = []
                self._call_count = 0

            def parse(
                self,
                section: Section,
                registry: CharacterRegistry,
                context_window: Optional[list[Section]] = None,
                *,
                scene_registry: Optional[SceneRegistry] = None,
            ) -> tuple[list[Segment], CharacterRegistry]:
                self.context_windows.append(context_window)
                seg = Segment(text=section.text, segment_type=SegmentType.NARRATION, character_id="narrator")
                self._call_count += 1
                return [seg], registry

        parser = _ContextCapturingParser()
        book_source = _FakeBookSource(chapters_to_parse=[ch1])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=parser)

        # Act
        workflow.run(url="http://example.com/test", end_chapter=1)

        # Assert — only one parse call (real section); synthetic section was skipped
        assert len(parser.context_windows) == 1
        # The real section's context window contains the synthetic section
        assert len(parser.context_windows[0]) == 1
        assert parser.context_windows[0][0].section_type == "book_title"

    def test_no_synthetic_sections_when_chapter_announcer_disabled(self) -> None:
        """When chapter_announcer_enabled=False, no synthetic sections are injected."""
        # Arrange
        from src.config.feature_flags import FeatureFlags
        ch1 = Chapter(number=1, title="Chapter 1", sections=[Section(text="Opening.")])
        capturing_parser = _CapturingSectionParser(responses=_make_seg_responses(1))
        book_source = _FakeBookSource(chapters_to_parse=[ch1])
        workflow = AIProjectGutenbergWorkflow(book_source=book_source, section_parser=capturing_parser)

        # Act
        book = workflow.run(
            url="http://example.com/test", end_chapter=1,
            feature_flags=FeatureFlags(chapter_announcer_enabled=False),
        )

        # Assert — only the original section, no synthetic one
        assert capturing_parser._call_count == 1
        sections = book.content.chapters[0].sections
        assert len(sections) == 1


