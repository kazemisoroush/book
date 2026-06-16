"""Tests for workflow factory provider wiring."""
import pytest

from src.ai.anthropic_provider import AnthropicProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.ai.claude_code_provider import ClaudeCodeProvider
from src.audio.sound_effect.audiogen_sound_effect_provider import (
    AudioGenSoundEffectProvider,
)
from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)
from src.audio.tts.elevenlabs_v2_provider import ElevenLabsV2Provider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.characters.elevenlabs_library_character_provider import (
    ElevenLabsLibraryCharacterProvider,
)
from src.characters.fish_audio_character_provider import FishAudioCharacterProvider
from src.workflows.ai_workflow import AIWorkflow
from src.workflows.characters_workflow import CharactersWorkflow
from src.workflows.sfx_workflow import SfxWorkflow
from src.workflows.tts_workflow import TTSWorkflow
from src.workflows.workflow_factory import create_workflow


class TestAiProviderSelection:
    """ai workflow requires an explicit, supported AI provider."""

    def test_selects_bedrock(self) -> None:
        workflow = create_workflow("ai", provider="bedrock")
        assert isinstance(workflow, AIWorkflow)
        assert isinstance(workflow._ai_provider, AWSBedrockProvider)

    def test_selects_anthropic(self) -> None:
        workflow = create_workflow("ai", provider="anthropic")
        assert isinstance(workflow, AIWorkflow)
        assert isinstance(workflow._ai_provider, AnthropicProvider)

    def test_selects_claude_code(self) -> None:
        workflow = create_workflow("ai", provider="claude-code")
        assert isinstance(workflow, AIWorkflow)
        assert isinstance(workflow._ai_provider, ClaudeCodeProvider)

    def test_missing_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown ai provider None"):
            create_workflow("ai")

    def test_unknown_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown ai provider 'mistral'"):
            create_workflow("ai", provider="mistral")


class TestTtsProviderSelection:
    """tts workflow requires an explicit, supported TTS provider."""

    def test_selects_fish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FISH_AUDIO_API_KEY", "fish-key")
        workflow = create_workflow("tts", provider="fish")
        assert isinstance(workflow, TTSWorkflow)
        assert isinstance(workflow._tts_provider, FishAudioTTSProvider)
        assert isinstance(workflow._character_provider, FishAudioCharacterProvider)

    def test_selects_elevenlabs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
        workflow = create_workflow("tts", provider="elevenlabs")
        assert isinstance(workflow, TTSWorkflow)
        assert isinstance(workflow._tts_provider, ElevenLabsV2Provider)
        assert isinstance(
            workflow._character_provider, ElevenLabsLibraryCharacterProvider,
        )

    def test_missing_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown tts provider None"):
            create_workflow("tts")

    def test_unknown_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown tts provider 'eleven_labs'"):
            create_workflow("tts", provider="eleven_labs")

    def test_fish_raises_when_api_key_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)
        with pytest.raises(ValueError, match="FISH_AUDIO_API_KEY"):
            create_workflow("tts", provider="fish")

    def test_elevenlabs_raises_when_api_key_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
            create_workflow("tts", provider="elevenlabs")


class TestCharactersProviderSelection:
    """characters workflow requires an explicit, supported character provider."""

    def test_selects_fish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FISH_AUDIO_API_KEY", "fish-key")
        workflow = create_workflow("characters", provider="fish")
        assert isinstance(workflow, CharactersWorkflow)
        assert isinstance(workflow._character_provider, FishAudioCharacterProvider)

    def test_selects_elevenlabs_defaults_to_library(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
        workflow = create_workflow("characters", provider="elevenlabs")
        assert isinstance(workflow, CharactersWorkflow)
        assert isinstance(
            workflow._character_provider, ElevenLabsLibraryCharacterProvider,
        )

    def test_missing_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown characters provider None"):
            create_workflow("characters")

    def test_unknown_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown characters provider 'fish_audio'"):
            create_workflow("characters", provider="fish_audio")


class TestSfxProviderSelection:
    def test_selects_elevenlabs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
        workflow = create_workflow("sfx", provider="elevenlabs")
        assert isinstance(workflow, SfxWorkflow)
        assert isinstance(workflow._provider, ElevenLabsSoundEffectProvider)

    def test_selects_audiogen(self) -> None:
        workflow = create_workflow("sfx", provider="audiogen")
        assert isinstance(workflow, SfxWorkflow)
        assert isinstance(workflow._provider, AudioGenSoundEffectProvider)

    def test_missing_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown sfx provider None"):
            create_workflow("sfx")

    def test_unknown_provider_raises_with_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown sfx provider 'bar'"):
            create_workflow("sfx", provider="bar")


class TestMixProviderSelection:
    """mix workflow names the on-disk subdir from the chosen provider."""

    def test_elevenlabs_maps_to_elevenlabs_v2(self) -> None:
        # Arrange / Act
        workflow = create_workflow("mix", provider="elevenlabs")

        # Assert
        from src.workflows.mix_workflow import MixWorkflow
        assert isinstance(workflow, MixWorkflow)
        assert workflow._provider_name == "elevenlabs_v2"

    def test_fish_maps_to_fish_audio(self) -> None:
        # Arrange / Act
        workflow = create_workflow("mix", provider="fish")

        # Assert
        from src.workflows.mix_workflow import MixWorkflow
        assert isinstance(workflow, MixWorkflow)
        assert workflow._provider_name == "fish_audio"

    def test_unknown_provider_raises_with_choices(self) -> None:
        # Act / Assert
        with pytest.raises(ValueError, match="Unknown tts provider 'bogus'"):
            create_workflow("mix", provider="bogus")
