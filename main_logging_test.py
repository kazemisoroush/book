"""Tests verifying that main.py uses structlog instead of bare print() for errors."""
import sys
import json
from unittest.mock import patch, MagicMock
import pytest


class TestMainLogging:
    """main() must use structlog for error messages and preserve JSON stdout output."""

    def test_main_error_does_not_print_to_stderr(self, capsys):
        """When workflow raises, main() must NOT use print() to write to stderr."""
        import main as main_module

        mock_workflow = MagicMock()
        mock_workflow.run.side_effect = RuntimeError("Test error")

        with patch.object(main_module, "ProjectGutenbergWorkflow") as MockWF:
            MockWF.create.return_value = mock_workflow
            with pytest.raises(SystemExit):
                main_module.main.__wrapped__ if hasattr(main_module.main, '__wrapped__') else None
                # Simulate argv
                with patch.object(sys, 'argv', ['main.py', 'http://example.com/book.zip']):
                    main_module.main()

        captured = capsys.readouterr()
        # The raw "Error: " prefix must NOT appear on stderr from a print() call
        assert not captured.err.startswith("Error:")

    def test_main_json_output_still_goes_to_stdout(self, capsys):
        """JSON output must still appear on stdout (it is data, not a log)."""
        import main as main_module
        from src.domain.models import Book, BookMetadata, BookContent, CharacterRegistry

        mock_book = MagicMock()
        mock_book.to_dict.return_value = {"title": "Test Book"}

        mock_workflow = MagicMock()
        mock_workflow.run.return_value = mock_book

        with patch.object(main_module, "ProjectGutenbergWorkflow") as MockWF:
            MockWF.create.return_value = mock_workflow
            with patch.object(sys, 'argv', ['main.py', 'http://example.com/book.zip']):
                main_module.main()

        captured = capsys.readouterr()
        # JSON must appear on stdout
        assert captured.out.strip() != ""
        parsed = json.loads(captured.out)
        assert parsed == {"title": "Test Book"}

    def test_main_calls_logging_configure(self):
        """main() must call logging_config.configure() at startup."""
        import main as main_module

        mock_workflow = MagicMock()
        mock_workflow.run.return_value = MagicMock(to_dict=lambda: {"title": "x"})

        # Patch configure in the main module's namespace (where the name is bound)
        with patch.object(main_module, "ProjectGutenbergWorkflow") as MockWF, \
             patch.object(main_module, "configure") as mock_configure:
            MockWF.create.return_value = mock_workflow
            with patch.object(sys, 'argv', ['main.py', 'http://example.com/book.zip']):
                main_module.main()

        mock_configure.assert_called_once()
