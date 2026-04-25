"""Tests for main entry point."""
import pytest
from unittest.mock import Mock, patch
import main


class TestMain:
    """Tests for main function."""

    def test_main_configures_logging_and_runs_workflow(self, monkeypatch):
        """Test that main configures logging, parses CLI, creates workflow, and runs it."""
        # Arrange
        test_url = 'http://example.com/book.zip'
        monkeypatch.setattr('sys.argv', ['prog', '--workflow', 'parse', '--url', test_url])

        mock_workflow = Mock()
        mock_create_workflow = Mock(return_value=mock_workflow)

        # Act
        with patch('main.create_workflow', mock_create_workflow):
            with patch('main.configure') as mock_configure:
                main.main()

        # Assert
        mock_configure.assert_called_once()
        mock_create_workflow.assert_called_once_with('parse')
        mock_workflow.run.assert_called_once()
        # Verify URL was passed to run()
        call_args = mock_workflow.run.call_args
        assert call_args[0][0] == test_url
