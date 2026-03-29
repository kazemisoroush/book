"""Tests for structured logging configuration module."""
import logging
import structlog


class TestConfigureLogging:
    """Tests for the configure() function in logging_config."""

    def test_configure_is_callable(self):
        """configure() must be importable and callable."""
        from src.logging_config import configure
        assert callable(configure)

    def test_configure_runs_without_error(self):
        """configure() must not raise on default call."""
        from src.logging_config import configure
        configure()  # Should not raise

    def test_configure_accepts_log_level_param(self):
        """configure() must accept an optional log_level parameter."""
        from src.logging_config import configure
        configure(log_level="DEBUG")   # Should not raise
        configure(log_level="WARNING") # Should not raise

    def test_configure_sets_up_structlog_processors(self):
        """After configure(), structlog.get_logger() must return a bound logger."""
        from src.logging_config import configure
        configure()
        logger = structlog.get_logger("test")
        # A bound logger has .info, .debug, .error, .warning methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")

    def test_configure_sets_stdlib_log_level(self):
        """configure() must set the root stdlib logging level."""
        from src.logging_config import configure
        configure(log_level="WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_configure_default_log_level_is_info(self):
        """configure() default log_level must be INFO."""
        from src.logging_config import configure
        configure()  # no args
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_configure_respects_log_level_env_var(self, monkeypatch):
        """configure() must respect LOG_LEVEL env var when no explicit level given."""
        from src.logging_config import configure
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure()
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_explicit_level_overrides_env_var(self, monkeypatch):
        """Explicit log_level= argument must take priority over LOG_LEVEL env var."""
        from src.logging_config import configure
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure(log_level="ERROR")
        root = logging.getLogger()
        assert root.level == logging.ERROR
