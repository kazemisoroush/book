"""Tests for run_e2e_listening_eval CLI argument parsing and env var validation.

These tests cover the logic that CAN be tested without real API calls:
- Argument parser accepts --passage flag (required, no --url/--start-chapter/--end-chapter)
- --passage flag resolves to the correct GoldenE2EPassage
- Unknown --passage name raises a clear error
- validate_env_vars raises with a clear message when a required var is missing
- validate_env_vars checks FISH_AUDIO_API_KEY (not ELEVENLABS_API_KEY)
- format_checklist returns the expected structure (all 10 feature lines present)
- build_output_dir returns a timestamped directory path
"""

import argparse
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.evals.run_e2e_listening_eval import (
    build_arg_parser,
    resolve_passage,
    validate_env_vars,
    format_checklist,
    build_output_dir,
)
from src.evals.book.fixtures.golden_e2e_passage import dracula_arrival


class TestArgParser:
    """Validate CLI argument parser accepts --passage and output flags."""

    def _parser(self) -> argparse.ArgumentParser:
        return build_arg_parser()

    def test_passage_flag_accepted(self) -> None:
        args = self._parser().parse_args(["--passage", "dracula_arrival"])
        assert args.passage == "dracula_arrival"

    def test_passage_flag_default_is_none(self) -> None:
        args = self._parser().parse_args([])
        assert args.passage is None

    def test_output_dir_default_is_evals_output(self) -> None:
        args = self._parser().parse_args(["--passage", "dracula_arrival"])
        assert args.output_dir == "evals_output"

    def test_output_dir_custom(self) -> None:
        args = self._parser().parse_args(
            ["--passage", "dracula_arrival", "--output-dir", "/tmp/my_evals"]
        )
        assert args.output_dir == "/tmp/my_evals"

    def test_music_flag_default_is_false(self) -> None:
        args = self._parser().parse_args(["--passage", "dracula_arrival"])
        assert args.music is False

    def test_music_flag_accepted(self) -> None:
        args = self._parser().parse_args(["--passage", "dracula_arrival", "--music"])
        assert args.music is True

    def test_debug_flag_default_is_false(self) -> None:
        args = self._parser().parse_args(["--passage", "dracula_arrival"])
        assert args.debug is False

    def test_url_arg_not_present(self) -> None:
        """--url should no longer be a recognised argument."""
        with pytest.raises(SystemExit):
            self._parser().parse_args(["--url", "http://example.com"])

    def test_start_chapter_arg_not_present(self) -> None:
        """--start-chapter should no longer be a recognised argument."""
        with pytest.raises(SystemExit):
            self._parser().parse_args(["--start-chapter", "1"])

    def test_end_chapter_arg_not_present(self) -> None:
        """--end-chapter should no longer be a recognised argument."""
        with pytest.raises(SystemExit):
            self._parser().parse_args(["--end-chapter", "1"])


class TestResolvePassage:
    """Validate passage resolution by name."""

    def test_dracula_arrival_resolves(self) -> None:
        passage = resolve_passage("dracula_arrival")
        assert passage.name == "dracula_arrival"
        assert passage.book_title == dracula_arrival.book_title

    def test_unknown_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unknown passage"):
            resolve_passage("nonexistent_passage_xyz")


class TestValidateEnvVars:
    """Validate env var checking exits with clear message when vars missing."""

    def test_passes_when_required_vars_set(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "FISH_AUDIO_API_KEY": "fish_key",
        }
        with patch.dict("os.environ", env, clear=False):
            # Should not raise
            validate_env_vars(music_enabled=False)

    def test_raises_when_aws_key_missing(self) -> None:
        env = {
            "AWS_SECRET_ACCESS_KEY": "secret",
            "FISH_AUDIO_API_KEY": "fish_key",
        }
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("AWS_ACCESS_KEY_ID", None)
            with pytest.raises(SystemExit):
                validate_env_vars(music_enabled=False)

    def test_raises_when_fish_audio_missing(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
        }
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("FISH_AUDIO_API_KEY", None)
            with pytest.raises(SystemExit):
                validate_env_vars(music_enabled=False)

    def test_raises_when_suno_missing_and_music_enabled(self) -> None:
        env = {
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "FISH_AUDIO_API_KEY": "fish_key",
        }
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("SUNO_API_KEY", None)
            with pytest.raises(SystemExit):
                validate_env_vars(music_enabled=True)


class TestFormatChecklist:
    """Validate the printed checklist contains all 10 required feature lines."""

    EXPECTED_FEATURE_TAGS = [
        "NARRATION",
        "DIALOGUE",
        "EMOTION",
        "SOUND EFFECTS",
        "AMBIENT",
        "SCENE TRANSITION",
        "BACKGROUND MUSIC",
        "VOICE DESIGN",
        "INTER-SEGMENT SILENCE",
        "NO AUDIO ARTIFACTS",
    ]

    def test_checklist_contains_all_feature_tags(self) -> None:
        checklist = format_checklist(
            output_path=Path("/tmp/evals_output/chapter.mp3"),
            duration_seconds=154,
        )
        for tag in self.EXPECTED_FEATURE_TAGS:
            assert tag in checklist, f"Missing feature tag: {tag}"

    def test_checklist_contains_output_path(self) -> None:
        checklist = format_checklist(
            output_path=Path("/tmp/evals_output/chapter.mp3"),
            duration_seconds=60,
        )
        assert "/tmp/evals_output/chapter.mp3" in checklist

    def test_checklist_contains_duration(self) -> None:
        checklist = format_checklist(
            output_path=Path("/tmp/chapter.mp3"),
            duration_seconds=154,  # 2:34
        )
        assert "2:34" in checklist


class TestBuildOutputDir:
    """Validate output directory is timestamped correctly."""

    def test_output_dir_uses_provided_base(self) -> None:
        fixed_dt = datetime(2026, 4, 10, 14, 30, 22)
        result = build_output_dir(base_dir="evals_output", now=fixed_dt)
        assert result.parent == Path("evals_output")

    def test_output_dir_has_timestamp_format(self) -> None:
        fixed_dt = datetime(2026, 4, 10, 14, 30, 22)
        result = build_output_dir(base_dir="evals_output", now=fixed_dt)
        assert "2026-04-10" in result.name
        assert "143022" in result.name

    def test_output_dir_starts_with_e2e(self) -> None:
        fixed_dt = datetime(2026, 4, 10, 14, 30, 22)
        result = build_output_dir(base_dir="evals_output", now=fixed_dt)
        assert result.name.startswith("e2e-")
