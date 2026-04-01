"""Unit tests for AIProjectGutenbergWorkflow — US-014 AC3 + US-018 caching."""
import os
import tempfile
from typing import Optional
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.parsers.book_section_parser import BookSectionParser
from src.repository.book_repository import BookRepository
from src.domain.models import (
    Book, Section, Segment, SegmentType, CharacterRegistry, Character,
    Chapter, BookContent, BookMetadata,
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

    def parse(
        self,
        section: Section,
        registry: CharacterRegistry,
        context_window: Optional[list[Section]] = None,
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
            workflow.run(url="http://example.com/test", chapter_limit=1)
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
            book = workflow.run(url="http://example.com/test", chapter_limit=1)
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
            book = workflow.run(url="http://example.com/test", chapter_limit=1)
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
            book = workflow.run(url="http://example.com/test", chapter_limit=1)
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
            book = workflow.run(url="http://example.com/test", chapter_limit=1)
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
            book = workflow.run(url="http://example.com/test", chapter_limit=1)
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
            workflow.run(url="http://example.com/test", chapter_limit=1, reparse=True)
        finally:
            os.unlink(html_path)

        # Assert — section parser WAS called (reparse forces fresh AI parse)
        assert capturing_parser._call_count == 1
        # And the result was saved to the repository
        assert len(repo.save_calls) == 1
