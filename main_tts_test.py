"""Tests for main.py --tts flag integration.

AC7: `audiobook <url> --tts` runs the full pipeline and prints the output path.
AC8: `audiobook <url> --tts` without ELEVENLABS_API_KEY set exits non-zero with
     a clear error.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

import main as main_module


class TestMainTTSFlag:
    """AC7: --tts runs the pipeline and prints output path."""

    def test_tts_flag_runs_pipeline_and_prints_path(
        self, tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With --tts, main() should print the path to chapter_01.mp3."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")

        mock_book = Mock()
        mock_book.character_registry = Mock()
        mock_book.character_registry.characters = []

        with patch("main.AIProjectGutenbergWorkflow") as mock_wf_cls, \
             patch("main.ElevenLabsProvider") as mock_provider_cls, \
             patch("main.TTSOrchestrator") as mock_orch_cls, \
             patch("main.VoiceAssigner") as mock_assigner_cls:

            mock_wf = Mock()
            mock_wf.run.return_value = mock_book
            mock_wf_cls.create.return_value = mock_wf

            mock_provider = Mock()
            mock_provider_cls.return_value = mock_provider

            # Provider returns a list of mock voice entries
            from src.tts.voice_assigner import VoiceEntry
            mock_provider.get_available_voices.return_value = {"Alice": "v1"}

            mock_assigner = Mock()
            mock_assigner.assign.return_value = {"narrator": "v1"}
            mock_assigner_cls.return_value = mock_assigner

            mock_orch = Mock()
            expected_path = tmp_path / "chapter_01.mp3"
            mock_orch.synthesize_chapter.return_value = expected_path
            mock_orch_cls.return_value = mock_orch

            with patch("sys.argv", ["audiobook", "http://example.com/book.zip", "--tts"]):
                main_module.main()

        captured = capsys.readouterr()
        assert str(expected_path) in captured.out

    def test_tts_flag_calls_workflow_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With --tts, the AI workflow must be called with the URL."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")

        mock_book = Mock()
        mock_book.character_registry = Mock()
        mock_book.character_registry.characters = []

        with patch("main.AIProjectGutenbergWorkflow") as mock_wf_cls, \
             patch("main.ElevenLabsProvider"), \
             patch("main.TTSOrchestrator") as mock_orch_cls, \
             patch("main.VoiceAssigner") as mock_assigner_cls:

            mock_wf = Mock()
            mock_wf.run.return_value = mock_book
            mock_wf_cls.create.return_value = mock_wf

            mock_assigner = Mock()
            mock_assigner.assign.return_value = {"narrator": "v1"}
            mock_assigner_cls.return_value = mock_assigner

            mock_orch = Mock()
            mock_orch.synthesize_chapter.return_value = tmp_path / "chapter_01.mp3"
            mock_orch_cls.return_value = mock_orch

            url = "http://example.com/book.zip"
            with patch("sys.argv", ["audiobook", url, "--tts"]):
                main_module.main()

        mock_wf.run.assert_called_once_with(url)

    def test_tts_flag_calls_synthesize_chapter_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With --tts, synthesize_chapter must be called with chapter_number=1."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")

        mock_book = Mock()
        mock_book.character_registry = Mock()
        mock_book.character_registry.characters = []

        with patch("main.AIProjectGutenbergWorkflow") as mock_wf_cls, \
             patch("main.ElevenLabsProvider"), \
             patch("main.TTSOrchestrator") as mock_orch_cls, \
             patch("main.VoiceAssigner") as mock_assigner_cls:

            mock_wf = Mock()
            mock_wf.run.return_value = mock_book
            mock_wf_cls.create.return_value = mock_wf

            mock_assigner = Mock()
            mock_assigner.assign.return_value = {"narrator": "v1"}
            mock_assigner_cls.return_value = mock_assigner

            mock_orch = Mock()
            mock_orch.synthesize_chapter.return_value = tmp_path / "chapter_01.mp3"
            mock_orch_cls.return_value = mock_orch

            with patch("sys.argv", ["audiobook", "http://x.com/b.zip", "--tts"]):
                main_module.main()

        call_args = mock_orch.synthesize_chapter.call_args
        assert call_args.args[1] == 1 or call_args.kwargs.get("chapter_number") == 1


class TestMainTTSMissingApiKey:
    """AC8: --tts without ELEVENLABS_API_KEY exits non-zero with clear error."""

    def test_missing_api_key_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without ELEVENLABS_API_KEY, main() must sys.exit with non-zero code."""
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

        with patch("sys.argv", ["audiobook", "http://example.com/book.zip", "--tts"]):
            with pytest.raises(SystemExit) as exc_info:
                main_module.main()

        assert exc_info.value.code != 0

    def test_missing_api_key_prints_clear_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Without ELEVENLABS_API_KEY, a human-readable error message is output."""
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

        with patch("sys.argv", ["audiobook", "http://example.com/book.zip", "--tts"]):
            with pytest.raises(SystemExit):
                main_module.main()

        # Either stderr or stdout should contain an error indicator
        captured = capsys.readouterr()
        # The error message should mention the key or elevenlabs
        combined = (captured.out + captured.err).lower()
        assert "elevenlabs_api_key" in combined or "api_key" in combined or "api key" in combined


class TestMainNoTTSFlag:
    """Without --tts, the existing JSON output behaviour is preserved."""

    def test_no_tts_flag_outputs_json(
        self, capsys, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without --tts, main() still outputs the book JSON."""
        mock_book = Mock()
        mock_book.to_dict.return_value = {"metadata": {"title": "Test"}, "content": {}, "character_registry": []}

        with patch("main.ProjectGutenbergWorkflow") as mock_wf_cls:
            mock_wf = Mock()
            mock_wf.run.return_value = mock_book
            mock_wf_cls.create.return_value = mock_wf

            with patch("sys.argv", ["audiobook", "http://example.com/book.zip"]):
                main_module.main()

        captured = capsys.readouterr()
        import json
        parsed = json.loads(captured.out)
        assert "metadata" in parsed

    def test_no_tts_flag_does_not_require_api_key(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Without --tts, ELEVENLABS_API_KEY is not required."""
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

        mock_book = Mock()
        mock_book.to_dict.return_value = {"metadata": {}, "content": {}, "character_registry": []}

        with patch("main.ProjectGutenbergWorkflow") as mock_wf_cls:
            mock_wf = Mock()
            mock_wf.run.return_value = mock_book
            mock_wf_cls.create.return_value = mock_wf

            with patch("sys.argv", ["audiobook", "http://example.com/book.zip"]):
                main_module.main()  # Should not raise
