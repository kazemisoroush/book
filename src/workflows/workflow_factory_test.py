"""Tests for workflow factory provider wiring."""
import pytest

from src.ai.anthropic_provider import AnthropicProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.audio.ambient.audiogen_ambient_provider import AudioGenAmbientProvider
from src.audio.ambient.elevenlabs_ambient_provider import ElevenLabsAmbientProvider
from src.audio.sound_effect.audiogen_sound_effect_provider import (
    AudioGenSoundEffectProvider,
)
from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)
from src.audio.tts.elevenlabs_tts_provider import ElevenLabsTTSProvider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.workflows.ai_workflow import AIWorkflow
from src.workflows.ambient_workflow import AmbientWorkflow
from src.workflows.sfx_workflow import SfxWorkflow
from src.workflows.tts_workflow import TTSWorkflow
from src.workflows.workflow_factory import create_workflow


def test_ai_defaults_to_bedrock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVIDER", raising=False)
    workflow = create_workflow("ai")
    assert isinstance(workflow, AIWorkflow)
    assert isinstance(workflow._section_parser.ai_provider, AWSBedrockProvider)


def test_ai_selects_anthropic_when_provider_is_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROVIDER", "anthropic")
    workflow = create_workflow("ai")
    assert isinstance(workflow, AIWorkflow)
    assert isinstance(workflow._section_parser.ai_provider, AnthropicProvider)


def test_tts_defaults_to_fish(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVIDER", raising=False)
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "fish-key")
    monkeypatch.setattr(FishAudioTTSProvider, "get_voices", lambda self: [{"voice_id": "v1", "name": "narrator", "labels": {}}])
    workflow = create_workflow("tts")
    assert isinstance(workflow, TTSWorkflow)
    assert isinstance(workflow._tts_provider, FishAudioTTSProvider)


def test_tts_selects_elevenlabs_when_provider_is_elevenlabs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(ElevenLabsTTSProvider, "get_voices", lambda self: [{"voice_id": "v1", "name": "narrator", "labels": {}}])
    workflow = create_workflow("tts")
    assert isinstance(workflow, TTSWorkflow)
    assert isinstance(workflow._tts_provider, ElevenLabsTTSProvider)


def test_tts_fish_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROVIDER", raising=False)
    monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)
    with pytest.raises(ValueError, match="FISH_AUDIO_API_KEY"):
        create_workflow("tts")


def test_tts_elevenlabs_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROVIDER", "elevenlabs")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        create_workflow("tts")


def test_ambient_defaults_to_elevenlabs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVIDER", raising=False)
    workflow = create_workflow("ambient")
    assert isinstance(workflow, AmbientWorkflow)
    assert isinstance(workflow._provider, ElevenLabsAmbientProvider)


def test_ambient_selects_audiogen_when_provider_is_audiogen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROVIDER", "audiogen")
    workflow = create_workflow("ambient")
    assert isinstance(workflow, AmbientWorkflow)
    assert isinstance(workflow._provider, AudioGenAmbientProvider)


def test_sfx_defaults_to_elevenlabs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVIDER", raising=False)
    workflow = create_workflow("sfx")
    assert isinstance(workflow, SfxWorkflow)
    assert isinstance(workflow._provider, ElevenLabsSoundEffectProvider)


def test_sfx_selects_audiogen_when_provider_is_audiogen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROVIDER", "audiogen")
    workflow = create_workflow("sfx")
    assert isinstance(workflow, SfxWorkflow)
    assert isinstance(workflow._provider, AudioGenSoundEffectProvider)
