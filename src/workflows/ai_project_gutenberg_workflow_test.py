"""Tests for AI-powered Project Gutenberg workflow."""
from unittest.mock import Mock, patch
import pytest
from src.workflows.ai_project_gutenberg_workflow import (
    AIProjectGutenbergWorkflow
)
from src.domain.models import (
    Book, BookMetadata, BookContent, Chapter, Section, Segment, SegmentType,
    CharacterRegistry, Character,
)
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser
)
from src.parsers.ai_section_parser import AISectionParser


def _make_parser_return(
    segments: list[Segment],
    registry: CharacterRegistry | None = None,
) -> tuple[list[Segment], CharacterRegistry]:
    """Helper: wrap segments and optional registry into the expected tuple."""
    if registry is None:
        registry = CharacterRegistry.with_default_narrator()
    return (segments, registry)


class TestAIProjectGutenbergWorkflowFactory:
    """Tests for the factory method."""

    def test_create_returns_workflow_instance(self):
        # When
        with patch('src.workflows.ai_project_gutenberg_workflow.AWSBedrockProvider'), \
             patch('src.workflows.ai_project_gutenberg_workflow.Config'):
            workflow = AIProjectGutenbergWorkflow.create()

        # Then
        assert isinstance(workflow, AIProjectGutenbergWorkflow)

    def test_create_wires_all_dependencies(self):
        # When
        with patch('src.workflows.ai_project_gutenberg_workflow.AWSBedrockProvider'), \
             patch('src.workflows.ai_project_gutenberg_workflow.Config'):
            workflow = AIProjectGutenbergWorkflow.create()

        # Then
        assert isinstance(workflow.downloader, ProjectGutenbergHTMLBookDownloader)
        assert isinstance(workflow.metadata_parser, StaticProjectGutenbergHTMLMetadataParser)
        assert isinstance(workflow.content_parser, StaticProjectGutenbergHTMLContentParser)
        assert isinstance(workflow.section_parser, AISectionParser)

    def test_create_stores_chapter_limit(self):
        # When
        with patch('src.workflows.ai_project_gutenberg_workflow.AWSBedrockProvider'), \
             patch('src.workflows.ai_project_gutenberg_workflow.Config'):
            workflow = AIProjectGutenbergWorkflow.create(chapter_limit=3)

        # Then
        assert workflow.chapter_limit == 3

    def test_create_chapter_limit_defaults_to_none(self):
        # When
        with patch('src.workflows.ai_project_gutenberg_workflow.AWSBedrockProvider'), \
             patch('src.workflows.ai_project_gutenberg_workflow.Config'):
            workflow = AIProjectGutenbergWorkflow.create()

        # Then
        assert workflow.chapter_limit is None


class TestAIProjectGutenbergWorkflow:
    """Tests for the run() method."""

    def _make_workflow(self, chapters=None, chapter_limit=None):
        """Helper to build a workflow with mocked dependencies."""
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "123"

        mock_metadata_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate="2020-01-01",
            language="en",
            originalPublication=None,
            credits=None
        )

        if chapters is None:
            chapters = [
                Chapter(
                    number=1,
                    title="Chapter 1",
                    sections=[Section(text="Test paragraph")]
                )
            ]

        mock_content_parser = Mock()
        mock_content_parser.parse.return_value = BookContent(chapters=chapters)

        mock_section_parser = Mock()

        workflow = AIProjectGutenbergWorkflow(
            downloader=mock_downloader,
            metadata_parser=mock_metadata_parser,
            content_parser=mock_content_parser,
            section_parser=mock_section_parser,
            chapter_limit=chapter_limit,
        )

        return workflow, mock_downloader, mock_metadata_parser, mock_content_parser, mock_section_parser

    def test_run_returns_book_with_character_registry(self):
        """run() must return a Book with a character_registry field."""
        # Given
        workflow, _, _, _, mock_section_parser = self._make_workflow()
        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="Test paragraph", segment_type=SegmentType.NARRATION)]
        )
        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html>test</html>"
            result = workflow.run(url)

        # Then
        assert isinstance(result, Book)
        assert hasattr(result, "character_registry")
        assert isinstance(result.character_registry, CharacterRegistry)

    def test_run_downloads_and_parses_book(self):
        # Given
        workflow, mock_downloader, _, _, mock_section_parser = self._make_workflow()
        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="Test paragraph", segment_type=SegmentType.NARRATION)]
        )
        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html>test</html>"
            book = workflow.run(url)

        # Then
        assert book.metadata.title == "Test Book"
        assert book.metadata.author == "Test Author"
        assert len(book.content.chapters) == 1
        mock_downloader.parse.assert_called_once_with(url)

    def test_run_segments_all_chapters_when_no_limit(self):
        # Given
        section1 = Section(text='"Hello," said Tom.')
        section2 = Section(text='It was a sunny day.')
        section3 = Section(text='"Goodbye," said Mary.')
        chapters = [
            Chapter(number=1, title="Chapter 1", sections=[section1, section2]),
            Chapter(number=2, title="Chapter 2", sections=[section3]),
        ]

        workflow, _, _, _, mock_section_parser = self._make_workflow(
            chapters=chapters,
            chapter_limit=None
        )

        mock_section_parser.parse.side_effect = [
            _make_parser_return([
                Segment(text="Hello", segment_type=SegmentType.DIALOGUE, character_id="tom"),
                Segment(text="said Tom.", segment_type=SegmentType.NARRATION),
            ]),
            _make_parser_return([
                Segment(text="It was a sunny day.", segment_type=SegmentType.NARRATION),
            ]),
            _make_parser_return([
                Segment(text="Goodbye", segment_type=SegmentType.DIALOGUE, character_id="mary"),
                Segment(text="said Mary.", segment_type=SegmentType.NARRATION),
            ]),
        ]

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            book = workflow.run(url)

        # Then — all 3 sections across 2 chapters got segmented
        assert mock_section_parser.parse.call_count == 3
        assert len(book.content.chapters[0].sections[0].segments) == 2
        assert len(book.content.chapters[0].sections[1].segments) == 1
        assert len(book.content.chapters[1].sections[0].segments) == 2

    def test_run_segments_only_limited_chapters_when_chapter_limit_set(self):
        # Given — 3 chapters but chapter_limit=2
        section1 = Section(text='Chapter 1 text.')
        section2 = Section(text='Chapter 2 text.')
        section3 = Section(text='Chapter 3 text.')
        chapters = [
            Chapter(number=1, title="Chapter 1", sections=[section1]),
            Chapter(number=2, title="Chapter 2", sections=[section2]),
            Chapter(number=3, title="Chapter 3", sections=[section3]),
        ]

        workflow, _, _, _, mock_section_parser = self._make_workflow(
            chapters=chapters,
            chapter_limit=2
        )

        mock_section_parser.parse.side_effect = [
            _make_parser_return([Segment(text="Chapter 1 text.", segment_type=SegmentType.NARRATION)]),
            _make_parser_return([Segment(text="Chapter 2 text.", segment_type=SegmentType.NARRATION)]),
        ]

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            book = workflow.run(url)

        # Then — only 2 sections got segmented (chapters 1 and 2)
        assert mock_section_parser.parse.call_count == 2
        assert book.content.chapters[0].sections[0].segments is not None
        assert book.content.chapters[1].sections[0].segments is not None

    def test_run_skips_segmentation_for_chapters_beyond_limit(self):
        # Given — 3 chapters but chapter_limit=1
        section1 = Section(text='Chapter 1 text.')
        section2 = Section(text='Chapter 2 text.')
        chapters = [
            Chapter(number=1, title="Chapter 1", sections=[section1]),
            Chapter(number=2, title="Chapter 2", sections=[section2]),
        ]

        workflow, _, _, _, mock_section_parser = self._make_workflow(
            chapters=chapters,
            chapter_limit=1
        )

        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="Chapter 1 text.", segment_type=SegmentType.NARRATION)]
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            book = workflow.run(url)

        # Then — only chapter 1 is segmented; chapter 2 sections have segments=None
        assert mock_section_parser.parse.call_count == 1
        assert book.content.chapters[0].sections[0].segments is not None
        assert book.content.chapters[1].sections[0].segments is None

    def test_run_raises_error_on_download_failure(self):
        # Given
        mock_downloader = Mock()
        mock_downloader.parse.return_value = False

        workflow = AIProjectGutenbergWorkflow(
            downloader=mock_downloader,
            metadata_parser=Mock(),
            content_parser=Mock(),
            section_parser=Mock(),
        )

        url = "https://invalid.url/bad.zip"

        # When/Then
        with pytest.raises(RuntimeError, match="Failed to download"):
            workflow.run(url)

    def test_run_raises_error_when_html_file_not_found(self):
        # Given
        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "123"

        workflow = AIProjectGutenbergWorkflow(
            downloader=mock_downloader,
            metadata_parser=Mock(),
            content_parser=Mock(),
            section_parser=Mock(),
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When/Then
        with patch('os.walk') as mock_walk:
            mock_walk.return_value = [('books/123', [], ['images', 'styles.css'])]
            with pytest.raises(RuntimeError, match="No HTML file found"):
                workflow.run(url)

    def test_run_registry_is_passed_to_each_parser_call(self):
        """The registry must be passed to the section parser on each call."""
        # Given — a workflow with 1 chapter, 1 section
        workflow, _, _, _, mock_section_parser = self._make_workflow()
        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="Test.", segment_type=SegmentType.NARRATION)]
        )
        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html>test</html>"
            workflow.run(url)

        # Then — parser was called with (section, registry) signature
        assert mock_section_parser.parse.call_count == 1
        call_args = mock_section_parser.parse.call_args
        # Second positional argument must be a CharacterRegistry
        assert isinstance(call_args.args[1], CharacterRegistry)

    def test_run_book_character_registry_contains_narrator(self):
        """The book.character_registry in the return value must contain the narrator."""
        # Given
        workflow, _, _, _, mock_section_parser = self._make_workflow()
        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="Test.", segment_type=SegmentType.NARRATION)]
        )
        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html>test</html>"
            book = workflow.run(url)

        # Then
        assert book.character_registry.get("narrator") is not None

    def test_run_accumulates_new_characters_across_sections(self):
        """Characters added by parser in section 1 are visible in section 2 call."""
        # Given — 1 chapter, 2 sections
        section1 = Section(text='Section 1.')
        section2 = Section(text='Section 2.')
        chapters = [
            Chapter(number=1, title="Ch1", sections=[section1, section2]),
        ]
        workflow, _, _, _, mock_section_parser = self._make_workflow(chapters=chapters)

        new_char = Character(character_id="harry", name="Harry Potter")
        registry_after_sec1 = CharacterRegistry.with_default_narrator()
        registry_after_sec1.add(new_char)

        mock_section_parser.parse.side_effect = [
            # Section 1: parser returns a registry with Harry added
            (
                [Segment(text="Section 1.", segment_type=SegmentType.NARRATION)],
                registry_after_sec1,
            ),
            # Section 2: returns same registry unchanged
            (
                [Segment(text="Section 2.", segment_type=SegmentType.NARRATION)],
                registry_after_sec1,
            ),
        ]

        url = "https://www.gutenberg.org/files/123/123-h.zip"

        # When
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html>test</html>"
            book = workflow.run(url)

        # Then — Harry is in the book's character registry
        assert book.character_registry.get("harry") is not None
        assert book.character_registry.get("harry").name == "Harry Potter"

    def test_run_passes_context_window_to_section_parser(self):
        """For each section, the workflow must pass the 3 preceding sections as context_window."""
        # Given — 1 chapter with 4 sections
        s1 = Section(text='Section 1.')
        s2 = Section(text='Section 2.')
        s3 = Section(text='Section 3.')
        s4 = Section(text='Section 4.')
        chapters = [Chapter(number=1, title="Ch1", sections=[s1, s2, s3, s4])]

        workflow, _, _, _, mock_section_parser = self._make_workflow(chapters=chapters)
        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="x", segment_type=SegmentType.NARRATION)]
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            workflow.run(url)

        # Then — each call received context_window kwarg
        assert mock_section_parser.parse.call_count == 4
        calls = mock_section_parser.parse.call_args_list

        def _get_cw(call):
            """Extract context_window from a call, handling empty list correctly."""
            if 'context_window' in call.kwargs:
                return call.kwargs['context_window']
            if len(call.args) > 2:
                return call.args[2]
            return None

        # Section 1 (index 0): no preceding sections → context_window=[]
        assert _get_cw(calls[0]) == []
        # Section 2 (index 1): 1 preceding → context_window=[s1]
        assert _get_cw(calls[1]) == [s1]
        # Section 3 (index 2): 2 preceding → context_window=[s1, s2]
        assert _get_cw(calls[2]) == [s1, s2]
        # Section 4 (index 3): 3 preceding → context_window=[s1, s2, s3]
        assert _get_cw(calls[3]) == [s1, s2, s3]

    def test_run_context_window_capped_at_3(self):
        """Context window must be capped at 3 preceding sections even for later sections."""
        # Given — 1 chapter with 5 sections
        sections = [Section(text=f'Section {i}.') for i in range(1, 6)]
        chapters = [Chapter(number=1, title="Ch1", sections=sections)]

        workflow, _, _, _, mock_section_parser = self._make_workflow(chapters=chapters)
        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="x", segment_type=SegmentType.NARRATION)]
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            workflow.run(url)

        # Then — section 5 (index 4) gets context_window=[s2, s3, s4] (3 preceding)
        calls = mock_section_parser.parse.call_args_list
        call4 = calls[4]
        if 'context_window' in call4.kwargs:
            cw4 = call4.kwargs['context_window']
        elif len(call4.args) > 2:
            cw4 = call4.args[2]
        else:
            cw4 = None
        assert cw4 == [sections[1], sections[2], sections[3]]
        assert len(cw4) == 3

    def test_run_context_window_resets_at_chapter_boundary(self):
        """Context window must not carry sections across chapter boundaries."""
        # Given — 2 chapters, chapter 2 starts fresh
        ch1_sections = [Section(text=f'Ch1 S{i}.') for i in range(1, 4)]
        ch2_s1 = Section(text='Ch2 S1.')
        chapters = [
            Chapter(number=1, title="Ch1", sections=ch1_sections),
            Chapter(number=2, title="Ch2", sections=[ch2_s1]),
        ]

        workflow, _, _, _, mock_section_parser = self._make_workflow(chapters=chapters)
        mock_section_parser.parse.return_value = _make_parser_return(
            [Segment(text="x", segment_type=SegmentType.NARRATION)]
        )

        url = "https://www.gutenberg.org/files/123/123-h.zip"
        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            workflow.run(url)

        # Then — chapter 2, section 1 (call index 3) must have context_window=[]
        calls = mock_section_parser.parse.call_args_list
        call3 = calls[3]
        if 'context_window' in call3.kwargs:
            cw_ch2 = call3.kwargs['context_window']
        elif len(call3.args) > 2:
            cw_ch2 = call3.args[2]
        else:
            cw_ch2 = None
        assert cw_ch2 == []
