"""Unit tests for AIProjectGutenbergWorkflow — US-014 AC3."""
import os
import tempfile
from typing import Optional
from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
from src.parsers.book_section_parser import BookSectionParser
from src.domain.models import (
    Section, Segment, SegmentType, CharacterRegistry, Character,
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
