"""Tests for structured logging configuration module."""
import logging
import structlog


class TestConfigureLogging:
    """Tests for the configure() function in logging_config."""

    def test_configure_is_callable(self):
        """configure() must be importable and callable."""
        # Arrange
        from src.logging_config import configure

        # Assert
        assert callable(configure)

    def test_configure_runs_without_error(self):
        """configure() must not raise on default call."""
        # Arrange
        from src.logging_config import configure

        # Act / Assert
        configure()  # Should not raise

    def test_configure_accepts_log_level_param(self):
        """configure() must accept an optional log_level parameter."""
        # Arrange
        from src.logging_config import configure

        # Act / Assert
        configure(log_level="DEBUG")    # Should not raise
        configure(log_level="WARNING")  # Should not raise

    def test_configure_sets_up_structlog_processors(self):
        """After configure(), structlog.get_logger() must return a bound logger."""
        # Arrange
        from src.logging_config import configure
        configure()

        # Act
        logger = structlog.get_logger("test")

        # Assert
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")

    def test_configure_sets_stdlib_log_level(self):
        """configure() must set the root stdlib logging level."""
        # Arrange
        from src.logging_config import configure

        # Act
        configure(log_level="WARNING")

        # Assert
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_configure_default_log_level_is_info(self):
        """configure() default log_level must be INFO."""
        # Arrange
        from src.logging_config import configure

        # Act
        configure()  # no args

        # Assert
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_configure_respects_log_level_env_var(self, monkeypatch):
        """configure() must respect LOG_LEVEL env var when no explicit level given."""
        # Arrange
        from src.logging_config import configure
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        # Act
        configure()

        # Assert
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_explicit_level_overrides_env_var(self, monkeypatch):
        """Explicit log_level= argument must take priority over LOG_LEVEL env var."""
        # Arrange
        from src.logging_config import configure
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        # Act
        configure(log_level="ERROR")

        # Assert
        root = logging.getLogger()
        assert root.level == logging.ERROR
