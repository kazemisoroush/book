"""Tests verifying that workflow modules use structlog for logging."""
from unittest.mock import Mock, patch


class TestProjectGutenbergWorkflowLogging:
    """ProjectGutenbergWorkflow must use structlog."""

    def test_module_has_structlog_logger(self):
        """project_gutenberg_workflow module must have a module-level logger."""
        import src.workflows.project_gutenberg_workflow as mod
        assert hasattr(mod, 'logger')

    def test_run_logs_progress_events(self):
        """run() must emit at least one structlog log event on success."""
        from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
        from src.domain.models import BookMetadata, BookContent

        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "123"

        mock_metadata_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Test", author="Author",
            releaseDate=None, language=None,
            originalPublication=None, credits=None
        )
        mock_content_parser = Mock()
        mock_content_parser.parse.return_value = BookContent(chapters=[])

        workflow = ProjectGutenbergWorkflow(
            downloader=mock_downloader,
            metadata_parser=mock_metadata_parser,
            content_parser=mock_content_parser,
        )

        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open, \
             patch('src.workflows.project_gutenberg_workflow.logger') as mock_logger:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            workflow.run("https://www.gutenberg.org/files/123/123-h.zip")

        assert (mock_logger.info.called or mock_logger.debug.called), \
            "Expected at least one info/debug log event during run()"


class TestAIProjectGutenbergWorkflowLogging:
    """AIProjectGutenbergWorkflow must use structlog."""

    def test_module_has_structlog_logger(self):
        """ai_project_gutenberg_workflow module must have a module-level logger."""
        import src.workflows.ai_project_gutenberg_workflow as mod
        assert hasattr(mod, 'logger')

    def test_run_logs_progress_events(self):
        """run() must emit at least one structlog log event on success."""
        from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
        from src.domain.models import (
            BookMetadata, BookContent, Chapter, Section,
            Segment, SegmentType, CharacterRegistry
        )

        mock_downloader = Mock()
        mock_downloader.parse.return_value = True
        mock_downloader._extract_book_id.return_value = "123"

        mock_metadata_parser = Mock()
        mock_metadata_parser.parse.return_value = BookMetadata(
            title="Test", author="Author",
            releaseDate=None, language=None,
            originalPublication=None, credits=None
        )
        mock_section_parser = Mock()
        mock_section_parser.parse.return_value = (
            [Segment(text="x", segment_type=SegmentType.NARRATION)],
            CharacterRegistry.with_default_narrator(),
        )
        mock_content_parser = Mock()
        mock_content_parser.parse.return_value = BookContent(
            chapters=[Chapter(number=1, title="Ch1", sections=[Section(text="x")])]
        )

        workflow = AIProjectGutenbergWorkflow(
            downloader=mock_downloader,
            metadata_parser=mock_metadata_parser,
            content_parser=mock_content_parser,
            section_parser=mock_section_parser,
        )

        with patch('os.walk') as mock_walk, \
             patch('builtins.open', create=True) as mock_open, \
             patch('src.workflows.ai_project_gutenberg_workflow.logger') as mock_logger:
            mock_walk.return_value = [('books/123', [], ['123-h.html'])]
            mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"
            workflow.run("https://www.gutenberg.org/files/123/123-h.zip")

        assert (mock_logger.info.called or mock_logger.debug.called), \
            "Expected at least one info/debug log event during run()"
