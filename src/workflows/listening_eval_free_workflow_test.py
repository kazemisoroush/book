"""Tests for ListeningEvalFreeWorkflow."""
from pathlib import Path
from unittest.mock import MagicMock

from src.audio.ambient.audiogen_ambient_provider import AudioGenAmbientProvider
from src.audio.music.musicgen_music_provider import MusicGenMusicProvider
from src.audio.sound_effect.audiogen_sound_effect_provider import AudioGenSoundEffectProvider
from src.workflows.listening_eval_free_workflow import ListeningEvalFreeWorkflow


class TestListeningEvalFreeWorkflowInit:
    """Tests for ListeningEvalFreeWorkflow construction."""

    def test_workflow_stores_audiogen_providers(self, tmp_path: Path) -> None:
        # Arrange
        ai_provider = MagicMock()
        tts_provider = MagicMock()
        sfx_provider = AudioGenSoundEffectProvider(device="cpu")
        ambient_provider = AudioGenAmbientProvider(device="cpu")
        music_provider = MusicGenMusicProvider(device="cpu")

        # Act
        workflow = ListeningEvalFreeWorkflow(
            ai_provider=ai_provider,
            tts_provider=tts_provider,
            sound_effect_provider=sfx_provider,
            ambient_provider=ambient_provider,
            music_provider=music_provider,
            books_dir=tmp_path,
        )

        # Assert — providers are stored and are the correct types
        assert isinstance(workflow._sound_effect_provider, AudioGenSoundEffectProvider)
        assert isinstance(workflow._ambient_provider, AudioGenAmbientProvider)
        assert isinstance(workflow._music_provider, MusicGenMusicProvider)
