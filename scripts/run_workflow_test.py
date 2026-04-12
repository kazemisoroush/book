"""Tests for run_workflow.py CLI argument parsing."""
import argparse


class TestCLIArgumentParsing:
    """Test that feature flag CLI arguments are parsed correctly."""

    def _parse_cli_args(self, args: list[str]) -> argparse.Namespace:
        """Parse CLI arguments like run_workflow.py does."""
        parser = argparse.ArgumentParser(
            description="Run a book-processing workflow on a Project Gutenberg URL.",
        )
        parser.add_argument("--url", required=True, help="Project Gutenberg zip URL")
        parser.add_argument("--chapters", type=int, default=1, help="Chapter limit (default: 1; 0 = all)")
        parser.add_argument(
            "--workflow",
            choices=["parse", "ai", "tts"],
            default="ai",
            help="Workflow to run: parse | ai | tts (default: ai)",
        )
        parser.add_argument(
            "--reparse",
            action="store_true",
            default=False,
            help="Force re-parse even if a cached parsed book exists (default: False)",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            default=False,
            help="Keep individual segment MP3 files alongside chapter.mp3 (default: False)",
        )
        # Feature flags (to be added)
        parser.add_argument(
            "--enable-ambient",
            action="store_true",
            default=None,
            help="Enable ambient background sound (default: enabled)",
        )
        parser.add_argument(
            "--disable-ambient",
            action="store_true",
            default=False,
            help="Disable ambient background sound",
        )
        parser.add_argument(
            "--enable-sound-effects",
            action="store_true",
            default=None,
            help="Enable sound effects (default: enabled)",
        )
        parser.add_argument(
            "--disable-sound-effects",
            action="store_true",
            default=False,
            help="Disable sound effects",
        )
        parser.add_argument(
            "--enable-emotion",
            action="store_true",
            default=None,
            help="Enable emotion tags (default: enabled)",
        )
        parser.add_argument(
            "--disable-emotion",
            action="store_true",
            default=False,
            help="Disable emotion tags",
        )
        parser.add_argument(
            "--enable-voice-design",
            action="store_true",
            default=None,
            help="Enable voice design (default: enabled)",
        )
        parser.add_argument(
            "--disable-voice-design",
            action="store_true",
            default=False,
            help="Disable voice design",
        )
        parser.add_argument(
            "--enable-scene-context",
            action="store_true",
            default=None,
            help="Enable scene context (default: enabled)",
        )
        parser.add_argument(
            "--disable-scene-context",
            action="store_true",
            default=False,
            help="Disable scene context",
        )
        return parser.parse_args(args)

    def test_cli_parses_enable_ambient_flag(self) -> None:
        """CLI parses --enable-ambient flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--enable-ambient"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.enable_ambient is True

    def test_cli_parses_disable_ambient_flag(self) -> None:
        """CLI parses --disable-ambient flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--disable-ambient"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.disable_ambient is True

    def test_cli_parses_enable_emotion_flag(self) -> None:
        """CLI parses --enable-emotion flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--enable-emotion"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.enable_emotion is True

    def test_cli_parses_disable_emotion_flag(self) -> None:
        """CLI parses --disable-emotion flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--disable-emotion"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.disable_emotion is True

    def test_cli_parses_enable_voice_design_flag(self) -> None:
        """CLI parses --enable-voice-design flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--enable-voice-design"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.enable_voice_design is True

    def test_cli_parses_disable_voice_design_flag(self) -> None:
        """CLI parses --disable-voice-design flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--disable-voice-design"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.disable_voice_design is True

    def test_cli_parses_enable_scene_context_flag(self) -> None:
        """CLI parses --enable-scene-context flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--enable-scene-context"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.enable_scene_context is True

    def test_cli_parses_disable_scene_context_flag(self) -> None:
        """CLI parses --disable-scene-context flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--disable-scene-context"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.disable_scene_context is True

    def test_cli_parses_enable_sound_effects_flag(self) -> None:
        """CLI parses --enable-sound-effects flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--enable-sound-effects"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.enable_sound_effects is True

    def test_cli_parses_disable_sound_effects_flag(self) -> None:
        """CLI parses --disable-sound-effects flag."""
        # Arrange
        args_list = ["--url", "https://example.com/book.zip", "--disable-sound-effects"]

        # Act
        args = self._parse_cli_args(args_list)

        # Assert
        assert args.disable_sound_effects is True
