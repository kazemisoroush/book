"""Tests verifying that ai_section_parser uses structlog for logging."""
from unittest.mock import Mock, patch
import pytest

from src.domain.models import Section, CharacterRegistry


class TestAISectionParserLogging:
    """AISectionParser must use structlog for retry and error events."""

    def test_module_has_structlog_logger(self):
        """ai_section_parser module must have a module-level structlog logger."""
        import src.parsers.ai_section_parser as mod
        assert hasattr(mod, 'logger')

    def test_successful_parse_logs_event(self):
        """A successful parse() call must emit at least one structlog log event."""
        from src.parsers.ai_section_parser import AISectionParser

        mock_ai = Mock()
        mock_ai.generate.return_value = (
            '{"segments": [{"type": "narration", "text": "Hello"}], "new_characters": []}'
        )

        parser = AISectionParser(ai_provider=mock_ai)
        section = Section(text="Hello")
        registry = CharacterRegistry.with_default_narrator()

        with patch('src.parsers.ai_section_parser.logger') as mock_logger:
            parser.parse(section, registry)

        assert mock_logger.info.called or mock_logger.debug.called, \
            "Expected at least one info/debug log event during successful parse()"

    def test_failed_parse_after_retries_logs_error(self):
        """After exhausting retries, an error-level log event must be emitted."""
        from src.parsers.ai_section_parser import AISectionParser

        mock_ai = Mock()
        mock_ai.generate.return_value = "invalid json {"

        parser = AISectionParser(ai_provider=mock_ai)
        section = Section(text="Some text")
        registry = CharacterRegistry.with_default_narrator()

        with patch('src.parsers.ai_section_parser.logger') as mock_logger, \
             patch('time.sleep'):
            with pytest.raises(ValueError):
                parser.parse(section, registry)

        assert mock_logger.error.called or mock_logger.warning.called, \
            "Expected at least one error/warning log event after parse() failure"
