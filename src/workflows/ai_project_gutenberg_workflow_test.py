"""Unit tests for AIProjectGutenbergWorkflow — US-014 AC3 + US-018 caching."""
import os
import tempfile
from typing import Optional
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.parsers.book_section_parser import BookSectionParser
from src.repository.book_repository import BookRepository
from src.domain.models import (
    Book, Section, Segment, SegmentType, CharacterRegistry, Character,
    Chapter, BookContent, BookMetadata, Scene, SceneRegistry,
)


class _FakeDownloader:
    """Minimal stub downloader that records calls and always succeeds."""

    def parse(self, url: str) -> bool:
        return True

    def _extract_book_id(self, url: str) -> str:
        return "test"


class _FakeMetadataParser:
    def parse(self, html: str) -> BookMetadata:
        return BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )


class _FakeContentParser:
    def __init__(self, chapters: list[Chapter]) -> None:
        self._chapters = chapters

    def parse(self, html: str) -> BookContent:
        return BookContent(chapters=self._chapters)


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

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
        )

    def test_description_update_in_first_section_is_visible_to_second_section_parser(
        self,
    ) -> None:
        """After section 1 is parsed and a description update is applied, section 2's
        parser call receives the registry with the updated description."""
        # Arrange — two sections in one chapter.
        # Section 1 parse: returns hagrid with an initial description.
        # Section 2 parse: we capture what registry it receives.

        section_1 = Section(text="Hagrid arrived.")
        section_2 = Section(text="Hagrid spoke again.")

        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1, section_2])

        # After parsing section 1, the registry has hagrid with updated description
        registry_after_section_1 = CharacterRegistry.with_default_narrator()
        registry_after_section_1.upsert(Character(
            character_id="hagrid",
            name="Rubeus Hagrid",
            sex="male",
            age="adult",
            description="booming bass voice, thick West Country accent; voice trembles when distressed",
        ))

        # Section 1 returns: one narration segment, registry with updated hagrid
        seg1 = Segment(
            text="Hagrid arrived.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )
        # Section 2 returns: one narration segment, same registry unchanged
        seg2 = Segment(
            text="Hagrid spoke again.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )

        capturing_parser = _CapturingSectionParser(
            responses=[
                ([seg1], registry_after_section_1),
                ([seg2], registry_after_section_1),
            ]
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=capturing_parser)

        # The workflow needs an html file — write a temporary file and override _find_html_file
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        original_find = workflow._find_html_file
        captured_path: Optional[str] = html_path
        workflow._find_html_file = lambda directory: captured_path  # type: ignore[assignment]

        try:
            # Act
            workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            workflow._find_html_file = original_find  # type: ignore[assignment]
            os.unlink(html_path)

        # Assert — section 2's parser received a registry where hagrid has the updated description
        assert len(capturing_parser.registries_seen) == 2
        registry_for_section_2 = capturing_parser.registries_seen[1]
        hagrid_in_section_2 = registry_for_section_2.get("hagrid")
        assert hagrid_in_section_2 is not None
        assert hagrid_in_section_2.description == (
            "booming bass voice, thick West Country accent; voice trembles when distressed"
        )


# ── AC3: workflow builds voice_design_prompt from description ─────────────────


class TestWorkflowBuildsVoiceDesignPrompt:
    """Workflow composes voice_design_prompt for characters with long descriptions (US-014 AC3)."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
        )

    def test_long_description_character_gets_voice_design_prompt(self) -> None:
        """A character with >=10 word description gets voice_design_prompt = '{age} {sex}, {description}.'."""
        # Arrange
        section_1 = Section(text="Hagrid arrived.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        long_desc = "booming bass voice, thick West Country accent, warm and boisterous, giant of a man"
        registry_after = CharacterRegistry.with_default_narrator()
        registry_after.upsert(Character(
            character_id="hagrid",
            name="Rubeus Hagrid",
            sex="male",
            age="adult",
            description=long_desc,
        ))

        seg1 = Segment(
            text="Hagrid arrived.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )
        capturing_parser = _CapturingSectionParser(
            responses=[([seg1], registry_after)]
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=capturing_parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert
        hagrid = book.character_registry.get("hagrid")
        assert hagrid is not None
        assert hagrid.voice_design_prompt == f"adult male, {long_desc}."

    def test_description_with_trailing_period_does_not_double_period(self) -> None:
        """A description ending with '.' must not produce '..' in voice_design_prompt."""
        # Arrange
        section_1 = Section(text="Darcy stood.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        desc_with_period = "A proud, aloof voice with a cold, clipped delivery; speaks with haughty reserve."
        registry_after = CharacterRegistry.with_default_narrator()
        registry_after.upsert(Character(
            character_id="darcy",
            name="Mr. Darcy",
            sex="male",
            age="adult",
            description=desc_with_period,
        ))

        seg1 = Segment(
            text="Darcy stood.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )
        capturing_parser = _CapturingSectionParser(
            responses=[([seg1], registry_after)]
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=capturing_parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert
        darcy = book.character_registry.get("darcy")
        assert darcy is not None
        expected = "adult male, A proud, aloof voice with a cold, clipped delivery; speaks with haughty reserve."
        assert darcy.voice_design_prompt == expected

    def test_short_description_character_gets_no_voice_design_prompt(self) -> None:
        """A character with <10 word description gets voice_design_prompt = None."""
        # Arrange
        section_1 = Section(text="Bob spoke.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        short_desc = "male voice"
        registry_after = CharacterRegistry.with_default_narrator()
        registry_after.upsert(Character(
            character_id="bob",
            name="Bob",
            sex="male",
            age="adult",
            description=short_desc,
        ))

        seg1 = Segment(
            text="Bob spoke.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )
        capturing_parser = _CapturingSectionParser(
            responses=[([seg1], registry_after)]
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=capturing_parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert
        bob = book.character_registry.get("bob")
        assert bob is not None
        assert bob.voice_design_prompt is None

    def test_narrator_never_gets_voice_design_prompt(self) -> None:
        """The narrator must never receive a voice_design_prompt."""
        # Arrange
        section_1 = Section(text="Story begins.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        registry_after = CharacterRegistry.with_default_narrator()

        seg1 = Segment(
            text="Story begins.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
        )
        capturing_parser = _CapturingSectionParser(
            responses=[([seg1], registry_after)]
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=capturing_parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert
        narrator = book.character_registry.get("narrator")
        assert narrator is not None
        assert narrator.voice_design_prompt is None


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
    metadata = BookMetadata(
        title="Test Book",
        author="Test Author",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )
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
        """When repository has a cached book and reparse=False, section_parser.parse is never called."""
        # Arrange
        cached_book = _make_cached_book()
        repo = _FakeRepository(stored=cached_book)

        section_1 = Section(text="Some text.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        seg1 = Segment(text="Some text.", segment_type=SegmentType.NARRATION, character_id="narrator")
        registry = CharacterRegistry.with_default_narrator()
        capturing_parser = _CapturingSectionParser(responses=[([seg1], registry)])

        workflow = AIProjectGutenbergWorkflow(
            downloader=_FakeDownloader(),
            metadata_parser=_FakeMetadataParser(),
            content_parser=_FakeContentParser([chapter]),
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert — section parser was never called (0 AI calls)
        assert capturing_parser._call_count == 0
        # The returned book is the cached one
        assert book.to_dict() == cached_book.to_dict()


class TestWorkflowReparsesWhenFlagSet:
    """Workflow calls AI parser when reparse=True even if cache exists (US-018 AC5)."""

    def test_reparse_bypasses_cache(self) -> None:
        """When reparse=True, the workflow runs the full AI pipeline and saves the result."""
        # Arrange
        cached_book = _make_cached_book()
        repo = _FakeRepository(stored=cached_book)

        section_1 = Section(text="Fresh text.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        seg1 = Segment(text="Fresh text.", segment_type=SegmentType.NARRATION, character_id="narrator")
        fresh_registry = CharacterRegistry.with_default_narrator()
        capturing_parser = _CapturingSectionParser(responses=[([seg1], fresh_registry)])

        workflow = AIProjectGutenbergWorkflow(
            downloader=_FakeDownloader(),
            metadata_parser=_FakeMetadataParser(),
            content_parser=_FakeContentParser([chapter]),
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            workflow.run(url="http://example.com/test", end_chapter=1, reparse=True)
        finally:
            os.unlink(html_path)

        # Assert — section parser WAS called (reparse forces fresh AI parse)
        assert capturing_parser._call_count == 1
        # And the result was saved to the repository
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
        # Simulate real parser behavior: upsert and stamp scene_id
        if detected is not None and scene_registry is not None:
            scene_registry.upsert(detected)
            for seg in segments:
                seg.scene_id = detected.scene_id
        self._call_count += 1
        return segments, updated_registry


class TestWorkflowThreadsSceneRegistry:
    """Workflow creates a SceneRegistry, threads it through parsing, and attaches to Book."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
        )

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

        workflow = self._make_workflow(chapters=[chapter], section_parser=parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name
        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert -- both parse calls received a SceneRegistry
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

        parser = _SceneAwareSectionParser(
            responses=[([seg], registry)],
            scenes=[cave_scene],
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name
        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

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

        parser = _SceneAwareSectionParser(
            responses=[([seg], registry)],
            scenes=[cave_scene],
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name
        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert
        segments = book.content.chapters[0].sections[0].segments
        assert segments is not None
        assert segments[0].scene_id == "scene_cave"

    def test_no_scene_detected_means_empty_registry(self) -> None:
        """When parser detects no scenes, Book.scene_registry is empty."""
        # Arrange
        section_1 = Section(text="Some text.")
        chapter = Chapter(number=1, title="Chapter 1", sections=[section_1])

        registry = CharacterRegistry.with_default_narrator()
        seg = Segment(text="Some text.", segment_type=SegmentType.NARRATION, character_id="narrator")

        parser = _SceneAwareSectionParser(
            responses=[([seg], registry)],
            scenes=[None],
        )

        workflow = self._make_workflow(chapters=[chapter], section_parser=parser)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name
        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(url="http://example.com/test", end_chapter=1)
        finally:
            os.unlink(html_path)

        # Assert
        assert len(book.scene_registry.all()) == 0


# ── TD-005: Chapter-by-chapter flush and auto-resume ────────────────────────


class _FlushTrackingRepository(BookRepository):
    """Repository that records each save() call with a snapshot of the book at that moment."""

    def __init__(self, initial_book: Optional[Book] = None) -> None:
        self._store: dict[str, Book] = {}
        self.save_calls: list[tuple[str, Book]] = []  # (book_id, book snapshot)
        self._default: Optional[Book] = initial_book

    def save(self, book: Book, book_id: str) -> None:
        # Deep copy the book to capture snapshot at save time
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


def _make_partial_book_with_chapters(num_chapters: int) -> Book:
    """Create a partial book with num_chapters chapters."""
    metadata = BookMetadata(
        title="Test Book",
        author="Test Author",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )
    chapters = []
    for i in range(1, num_chapters + 1):
        section = Section(
            text=f"Chapter {i} text.",
            segments=[
                Segment(
                    text=f"Chapter {i} text.",
                    segment_type=SegmentType.NARRATION,
                    character_id="narrator",
                ),
            ],
        )
        chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
        chapters.append(chapter)
    content = BookContent(chapters=chapters)
    registry = CharacterRegistry.with_default_narrator()
    return Book(metadata=metadata, content=content, character_registry=registry)


class TestWorkflowAutoResumesFromCache:
    """Workflow auto-resumes from cached partial book when start_chapter=1 and cache exists."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
        repository: Optional[BookRepository] = None,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
            repository=repository,
        )

    def test_auto_resume_when_start_chapter_is_1_and_cache_exists(self) -> None:
        """When start_chapter=1 and cache exists with chapters 1-2, resume from chapter 3."""
        # Arrange — cached book has chapters 1-2
        cached_book = _make_partial_book_with_chapters(2)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 5 chapters total
        chapters_to_parse = []
        for i in range(1, 6):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Section parser returns responses for all 5 chapters
        # (but only chapters 3-5 will actually be called)
        seg_responses = []
        for i in range(1, 6):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act — call with start_chapter=1 (default), should auto-resume from chapter 3
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=5,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Section parser should have been called 3 times (chapters 3, 4, 5)
        assert capturing_parser._call_count == 3
        # Final book should have 5 chapters
        assert len(book.content.chapters) == 5
        # Repository should have saved 3 times (chapters 3, 4, 5)
        assert len(repo.save_calls) == 3

    def test_no_resume_when_reparse_is_true(self) -> None:
        """When reparse=True, cache is ignored and all chapters are parsed."""
        # Arrange — cached book has chapters 1-2
        cached_book = _make_partial_book_with_chapters(2)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 5 chapters
        chapters_to_parse = []
        for i in range(1, 6):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        seg_responses = []
        for i in range(1, 6):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act — reparse=True should ignore cache
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=5,
                reparse=True,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Section parser should have been called 5 times (all chapters)
        assert capturing_parser._call_count == 5
        # Final book should have 5 chapters
        assert len(book.content.chapters) == 5
        # Repository should have saved 5 times (one per chapter, overwriting cache)
        assert len(repo.save_calls) == 5


class TestWorkflowCacheWithNonOneStartChapter:
    """Workflow should load cache even when start_chapter != 1 (fix for caching bug)."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
        repository: Optional[BookRepository] = None,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
            repository=repository,
        )

    def test_cache_is_loaded_even_when_start_chapter_gt_1(self) -> None:
        """Cache with chapters 1-10 is loaded when requesting start_chapter=15, end_chapter=20.

        Expected:
        - Cache is loaded (book has 1-10)
        - effective_start_chapter = max(15, 10+1) = 15
        - Parser called 6 times (chapters 15-20)
        - Final book has 16 chapters (1-10 cached, 15-20 parsed)
        """
        # Arrange — cached book has chapters 1-10
        cached_book = _make_partial_book_with_chapters(10)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 25 chapters total
        chapters_to_parse = []
        for i in range(1, 26):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Section parser has responses for all 25 chapters
        seg_responses = []
        for i in range(1, 26):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act — request start_chapter=15, cache should be loaded and resumed from 15
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=15,
                end_chapter=20,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Section parser should have been called 6 times (chapters 15-20)
        assert capturing_parser._call_count == 6
        # Final book should have 16 chapters (1-10 from cache, 15-20 parsed)
        assert len(book.content.chapters) == 16
        # Repository should have saved 6 times (chapters 15-20 flushed)
        assert len(repo.save_calls) == 6
        # Verify chapter numbers are correct
        assert book.content.chapters[0].number == 1  # First cached chapter
        assert book.content.chapters[9].number == 10  # Last cached chapter
        assert book.content.chapters[10].number == 15  # First parsed chapter
        assert book.content.chapters[15].number == 20  # Last parsed chapter

    def test_cache_load_respects_end_chapter_boundary(self) -> None:
        """Cache with chapters 1-10 is loaded; requesting end_chapter=5 doesn't parse beyond 5.

        Expected:
        - Cache is loaded (book has 1-10)
        - effective_start_chapter = max(1, 10+1) = 11
        - Parser NOT called (no chapters >= 11 and <= 5)
        - Final book has 10 chapters from cache (all cached chapters kept)
        """
        # Arrange — cached book has chapters 1-10
        cached_book = _make_partial_book_with_chapters(10)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 20 chapters
        chapters_to_parse = []
        for i in range(1, 21):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Section parser has responses for all chapters (but won't be called)
        seg_responses = []
        for i in range(1, 21):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act — request start_chapter=1, end_chapter=5 with cache of 1-10
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=5,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Section parser should NOT have been called (cache satisfies request)
        assert capturing_parser._call_count == 0
        # Final book has all cached chapters (workflow doesn't filter by end_chapter for cached content)
        assert len(book.content.chapters) == 10
        # Repository should NOT have saved (no new chapters parsed)
        assert len(repo.save_calls) == 0
        # Verify first and last chapter numbers
        assert book.content.chapters[0].number == 1
        assert book.content.chapters[9].number == 10

    def test_arbitrary_range_with_partial_cache(self) -> None:
        """Cache with chapters 1-5; requesting start_chapter=3, end_chapter=10 loads cache, parses 6-10.

        Expected:
        - Cache is loaded (book has 1-5)
        - Chapters 1-2 skipped in loop (before effective_start_chapter=6)
        - effective_start_chapter = max(3, 5+1) = 6
        - Parser called 5 times (chapters 6-10)
        - Final book has 10 chapters (1-5 cached, 6-10 parsed)
        """
        # Arrange — cached book has chapters 1-5
        cached_book = _make_partial_book_with_chapters(5)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 15 chapters
        chapters_to_parse = []
        for i in range(1, 16):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Section parser has responses for all chapters
        seg_responses = []
        for i in range(1, 16):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act — request start_chapter=3, end_chapter=10 with cache of 1-5
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=3,
                end_chapter=10,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Section parser should have been called 5 times (chapters 6-10)
        assert capturing_parser._call_count == 5
        # Final book should have 10 chapters (1-5 from cache, 6-10 parsed)
        assert len(book.content.chapters) == 10
        # Repository should have saved 5 times (chapters 6-10 flushed)
        assert len(repo.save_calls) == 5
        # Verify chapter numbers
        assert book.content.chapters[0].number == 1  # First cached chapter
        assert book.content.chapters[4].number == 5  # Last cached chapter
        assert book.content.chapters[5].number == 6  # First parsed chapter
        assert book.content.chapters[9].number == 10  # Last parsed chapter


class TestWorkflowChapterByChapterFlush:
    """Workflow saves partial book snapshot after each chapter completes."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
        repository: Optional[BookRepository] = None,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
            repository=repository,
        )

    def test_workflow_saves_partial_book_after_each_chapter(self) -> None:
        """Repository.save is called once per chapter, with increasing chapter counts."""
        # Arrange — 5 chapters, no cache
        chapters_to_parse = []
        for i in range(1, 6):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        seg_responses = []
        for i in range(1, 6):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)
        repo = _FlushTrackingRepository()

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=5,
                reparse=True,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Save should be called 5 times
        assert len(repo.save_calls) == 5
        # Each save should have an increasing number of chapters
        for i, (_book_id, saved_book) in enumerate(repo.save_calls, start=1):
            assert len(saved_book.content.chapters) == i

    def test_partial_book_snapshot_has_metadata_and_registries(self) -> None:
        """Each saved partial book has metadata, character_registry, and scene_registry."""
        # Arrange
        chapters_to_parse = []
        for i in range(1, 4):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        seg_responses = []
        for i in range(1, 4):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)
        repo = _FlushTrackingRepository()

        workflow = AIProjectGutenbergWorkflow(
            downloader=_FakeDownloader(),
            metadata_parser=_FakeMetadataParser(),
            content_parser=_FakeContentParser(chapters_to_parse),
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=3,
                reparse=True,
            )
        finally:
            os.unlink(html_path)

        # Assert
        assert len(repo.save_calls) == 3
        for _book_id, saved_book in repo.save_calls:
            assert saved_book.metadata is not None
            assert saved_book.character_registry is not None
            assert saved_book.scene_registry is not None


class TestWorkflowSubsetParsing:
    """Workflow can parse a subset of chapters via start_chapter and end_chapter."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
        repository: Optional[BookRepository] = None,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
            repository=repository,
        )

    def test_subset_range_with_no_cache(self) -> None:
        """Parsing start_chapter=5 end_chapter=8 with no cache parses only chapters 5-8."""
        # Arrange — 10 chapters available, no cache
        chapters_to_parse = []
        for i in range(1, 11):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Prepare responses for chapters 5-8 (only these will be called)
        seg_responses = []
        for i in range(1, 11):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)
        repo = _FlushTrackingRepository()

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=5,
                end_chapter=8,
                reparse=True,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Section parser should be called only 4 times (chapters 5-8)
        assert capturing_parser._call_count == 4
        # Final book should have chapters 5-8
        assert len(book.content.chapters) == 4
        assert book.content.chapters[0].number == 5
        assert book.content.chapters[3].number == 8
        # Save should be called 4 times
        assert len(repo.save_calls) == 4

    def test_subset_range_with_partial_cache(self) -> None:
        """With cached chapters 1-4, parsing start_chapter=1 end_chapter=10 skips 1-4 and parses 5-10."""
        # Arrange — cached book has chapters 1-4
        cached_book = _make_partial_book_with_chapters(4)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 10 chapters
        chapters_to_parse = []
        for i in range(1, 11):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Responses needed for all 10 chapters (but only 6 will be called)
        seg_responses = []
        for i in range(1, 11):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=10,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Section parser should be called 6 times (chapters 5-10)
        assert capturing_parser._call_count == 6
        # Final book should have chapters 1-10
        assert len(book.content.chapters) == 10
        # Save should be called 6 times (chapters 5-10)
        assert len(repo.save_calls) == 6


class TestWorkflowCharacterAndSceneRegistryPreservedAcrossResume:
    """Character and scene registries are preserved when resuming from cache."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
        repository: Optional[BookRepository] = None,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
            repository=repository,
        )

    def test_character_registry_preserved_across_resume(self) -> None:
        """Character from cache is preserved; new characters added during resume."""
        # Arrange — cached book with alice
        cached_book = _make_partial_book_with_chapters(2)
        alice = Character(
            character_id="alice",
            name="Alice",
            sex="female",
            age="adult",
            description="A curious young woman.",
        )
        cached_book.character_registry.upsert(alice)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 5 chapters
        chapters_to_parse = []
        for i in range(1, 6):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Responses for chapters 3-5 (only these will be parsed during resume)
        # Each response includes alice (from cache) plus optionally bob (new)
        seg_responses = []
        # Dummy responses for chapters 1-2 (won't be called during resume)
        for i in range(1, 3):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        # Real responses for chapters 3-5 (will be called during resume)
        for i in range(3, 6):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            # Build registry with alice (from cache) plus new bob
            registry = CharacterRegistry.with_default_narrator()
            registry.upsert(alice)
            bob = Character(
                character_id="bob",
                name="Bob",
                sex="male",
                age="adult",
                description="A mysterious stranger.",
            )
            registry.upsert(bob)
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=5,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Final book should have both alice and bob
        alice_found = book.character_registry.get("alice")
        bob_found = book.character_registry.get("bob")
        assert alice_found is not None
        assert alice_found.name == "Alice"
        assert bob_found is not None
        assert bob_found.name == "Bob"

    def test_scene_registry_preserved_across_resume(self) -> None:
        """Scene from cache is preserved; new scenes added during resume."""
        # Arrange — cached book with scene_cave
        cached_book = _make_partial_book_with_chapters(2)
        cave_scene = Scene(scene_id="scene_cave", environment="cave", acoustic_hints=["echo"])
        cached_book.scene_registry.upsert(cave_scene)
        repo = _FlushTrackingRepository(initial_book=cached_book)

        # Fresh content provides 5 chapters
        chapters_to_parse = []
        for i in range(1, 6):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        # Responses for all 5 chapters
        seg_responses = []
        for i in range(1, 6):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        parser = _SceneAwareSectionParser(
            responses=seg_responses,
            scenes=[
                None,  # Chapters 1-2 (cached, so parser not called)
                None,
                Scene(
                    scene_id="scene_forest",
                    environment="forest",
                    acoustic_hints=["rustling"],
                ),  # Chapter 3
                None,  # Chapter 4
                None,  # Chapter 5
            ],
        )

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=5,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert
        # Final book should have both cave and forest scenes
        cave = book.scene_registry.get("scene_cave")
        forest = book.scene_registry.get("scene_forest")
        assert cave is not None
        assert cave.environment == "cave"
        assert forest is not None
        assert forest.environment == "forest"


# ── Fix: Cache accumulates chapters across non-sequential runs ───────────────


def _make_partial_book_with_specific_chapters(chapter_numbers: list[int]) -> Book:
    """Create a partial book with specific (possibly non-contiguous) chapter numbers."""
    metadata = BookMetadata(
        title="Test Book",
        author="Test Author",
        releaseDate=None,
        language=None,
        originalPublication=None,
        credits=None,
    )
    chapters = []
    for num in chapter_numbers:
        section = Section(
            text=f"Chapter {num} text.",
            segments=[
                Segment(
                    text=f"Chapter {num} text.",
                    segment_type=SegmentType.NARRATION,
                    character_id="narrator",
                ),
            ],
        )
        chapter = Chapter(number=num, title=f"Chapter {num}", sections=[section])
        chapters.append(chapter)
    content = BookContent(chapters=chapters)
    registry = CharacterRegistry.with_default_narrator()
    return Book(metadata=metadata, content=content, character_registry=registry)


class TestWorkflowCacheWithNonContiguousChapters:
    """Workflow correctly handles non-contiguous cached chapter numbers."""

    def _make_workflow(
        self,
        chapters: list[Chapter],
        section_parser: BookSectionParser,
        repository: Optional[BookRepository] = None,
    ) -> AIProjectGutenbergWorkflow:
        downloader = _FakeDownloader()
        metadata_parser = _FakeMetadataParser()
        content_parser = _FakeContentParser(chapters)
        return AIProjectGutenbergWorkflow(
            downloader=downloader,
            metadata_parser=metadata_parser,
            content_parser=content_parser,
            section_parser=section_parser,
            repository=repository,
        )

    def test_cache_ch20_parse_19_to_21(self) -> None:
        """Cache has [ch20]; requesting 19→21 parses ch19 and ch21, skips ch20.

        Verifies the set-based skip logic: only the exact cached chapter
        number is skipped, not a contiguous range.
        """
        # Arrange
        cached_book = _make_partial_book_with_specific_chapters([20])
        repo = _FlushTrackingRepository(initial_book=cached_book)

        chapters_to_parse = []
        for i in range(1, 25):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        seg_responses = []
        for i in range(1, 25):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=19,
                end_chapter=21,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert — parser called for ch19 and ch21 (ch20 cached)
        assert capturing_parser._call_count == 2
        # Final book has 3 chapters: [19, 20, 21] in sorted order
        assert len(book.content.chapters) == 3
        assert [ch.number for ch in book.content.chapters] == [19, 20, 21]
        assert len(repo.save_calls) == 2

    def test_cache_ch1_to_3_parse_ch20(self) -> None:
        """Cache has [1, 2, 3]; requesting start=20, end=20 parses only ch20.

        Verifies that contiguous low-numbered cache doesn't interfere with
        parsing a higher chapter range.
        """
        # Arrange
        cached_book = _make_partial_book_with_specific_chapters([1, 2, 3])
        repo = _FlushTrackingRepository(initial_book=cached_book)

        chapters_to_parse = []
        for i in range(1, 25):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        seg_responses = []
        for i in range(1, 25):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=20,
                end_chapter=20,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert — parser called once for ch20
        assert capturing_parser._call_count == 1
        # Final book has 4 chapters: [1, 2, 3, 20] in sorted order
        assert len(book.content.chapters) == 4
        assert [ch.number for ch in book.content.chapters] == [1, 2, 3, 20]
        assert len(repo.save_calls) == 1

    def test_cache_ch20_parse_1_to_3(self) -> None:
        """Cache has [ch20]; requesting start=1, end=3 parses ch1-3 and keeps ch20.

        Verifies that a high-numbered cached chapter is preserved and new
        lower-numbered chapters are inserted in sorted order.
        """
        # Arrange
        cached_book = _make_partial_book_with_specific_chapters([20])
        repo = _FlushTrackingRepository(initial_book=cached_book)

        chapters_to_parse = []
        for i in range(1, 25):
            section = Section(text=f"Chapter {i} text.")
            chapter = Chapter(number=i, title=f"Chapter {i}", sections=[section])
            chapters_to_parse.append(chapter)

        seg_responses = []
        for i in range(1, 25):
            seg = Segment(
                text=f"Chapter {i} text.",
                segment_type=SegmentType.NARRATION,
                character_id="narrator",
            )
            registry = CharacterRegistry.with_default_narrator()
            seg_responses.append(([seg], registry))

        capturing_parser = _CapturingSectionParser(responses=seg_responses)

        workflow = self._make_workflow(
            chapters=chapters_to_parse,
            section_parser=capturing_parser,
            repository=repo,
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html></html>")
            html_path = f.name

        workflow._find_html_file = lambda directory: html_path  # type: ignore[assignment]

        try:
            # Act
            book = workflow.run(
                url="http://example.com/test",
                start_chapter=1,
                end_chapter=3,
                reparse=False,
            )
        finally:
            os.unlink(html_path)

        # Assert — parser called 3 times for ch1, ch2, ch3
        assert capturing_parser._call_count == 3
        # Final book has 4 chapters: [1, 2, 3, 20] in sorted order
        assert len(book.content.chapters) == 4
        assert [ch.number for ch in book.content.chapters] == [1, 2, 3, 20]
        assert len(repo.save_calls) == 3
