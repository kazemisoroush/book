"""Workflow factory: builds fully-wired Workflow instances by CLI name."""
from pathlib import Path
from typing import Callable, Optional

from src.ai.ai_provider import AIProvider
from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.tts.tts_provider import TTSProvider
from src.characters.character_provider import CharacterProvider
from src.config.config import Config
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader,
)
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.project_gutenberg_book_source import ProjectGutenbergBookSource
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)
from src.prompts.builder.announcement_formatter import AnnouncementFormatter
from src.repository.file_book_repository import FileBookRepository

from .ai_workflow import AIWorkflow
from .ambient_workflow import AmbientWorkflow
from .characters_workflow import CharactersWorkflow
from .mix_workflow import MixWorkflow
from .music_workflow import MusicWorkflow
from .sfx_workflow import SfxWorkflow
from .tts_workflow import TTSWorkflow
from .workflow import Workflow


def _make_ai_provider(provider: Optional[str], config: Config) -> AIProvider:
    if provider == "anthropic":
        from src.ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(config)
    if provider == "bedrock":
        from src.ai.aws_bedrock_provider import AWSBedrockProvider
        return AWSBedrockProvider(config)
    if provider == "claude-code":
        from src.ai.claude_code_provider import ClaudeCodeProvider
        return ClaudeCodeProvider(config)
    raise ValueError(
        f"Unknown ai provider {provider!r}; choose one of: anthropic, bedrock, claude-code"
    )


def _make_tts_provider(
    provider: Optional[str], config: Config, books_dir: Path,
) -> TTSProvider:
    if provider == "elevenlabs":
        from src.audio.tts.elevenlabs_tts_provider import ElevenLabsTTSProvider
        return ElevenLabsTTSProvider(
            api_key=config.require_elevenlabs_api_key(),
            books_dir=books_dir,
        )
    if provider == "fish":
        from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
        return FishAudioTTSProvider(
            api_key=config.require_fish_audio_api_key(),
            books_dir=books_dir,
        )
    raise ValueError(
        f"Unknown tts provider {provider!r}; choose one of: elevenlabs, fish"
    )


def _make_character_provider(
    provider: Optional[str], config: Config,
) -> CharacterProvider:
    if provider == "elevenlabs":
        from elevenlabs.client import ElevenLabs

        from src.characters.elevenlabs_character_provider import (
            ElevenLabsCharacterProvider,
        )
        client = ElevenLabs(api_key=config.require_elevenlabs_api_key())
        return ElevenLabsCharacterProvider(client=client)
    if provider == "fish":
        from src.characters.fish_audio_character_provider import (
            FishAudioCharacterProvider,
        )
        return FishAudioCharacterProvider()
    raise ValueError(
        f"Unknown characters provider {provider!r}; choose one of: elevenlabs, fish"
    )


def _make_ambient_provider(
    provider: Optional[str], config: Config, books_dir: Path,
) -> AmbientProvider:
    if provider == "audiogen":
        from src.audio.ambient.audiogen_ambient_provider import (
            AudioGenAmbientProvider,
        )
        return AudioGenAmbientProvider(books_dir=books_dir)
    if provider == "elevenlabs":
        from elevenlabs.client import ElevenLabs

        from src.audio.ambient.elevenlabs_ambient_provider import (
            ElevenLabsAmbientProvider,
        )
        client = ElevenLabs(api_key=config.require_elevenlabs_api_key())
        return ElevenLabsAmbientProvider(client=client, books_dir=books_dir)
    raise ValueError(
        f"Unknown ambient provider {provider!r}; choose one of: audiogen, elevenlabs"
    )


def _make_sfx_provider(
    provider: Optional[str], config: Config, books_dir: Path,
) -> SoundEffectProvider:
    if provider == "audiogen":
        from src.audio.sound_effect.audiogen_sound_effect_provider import (
            AudioGenSoundEffectProvider,
        )
        return AudioGenSoundEffectProvider(books_dir=books_dir)
    if provider == "elevenlabs":
        from elevenlabs.client import ElevenLabs

        from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
            ElevenLabsSoundEffectProvider,
        )
        client = ElevenLabs(api_key=config.require_elevenlabs_api_key())
        return ElevenLabsSoundEffectProvider(client=client, books_dir=books_dir)
    raise ValueError(
        f"Unknown sfx provider {provider!r}; choose one of: audiogen, elevenlabs"
    )


def _build_ai(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    repository = FileBookRepository(base_dir=str(books_dir))
    book_source = ProjectGutenbergBookSource(
        downloader=ProjectGutenbergHTMLBookDownloader(),
        metadata_parser=StaticProjectGutenbergHTMLMetadataParser(),
        content_parser=StaticProjectGutenbergHTMLContentParser(),
        repository=repository,
    )
    ai_provider = _make_ai_provider(provider, config)
    return AIWorkflow(
        book_source=book_source,
        section_parser=AISectionParser(ai_provider),
        announcement_formatter=AnnouncementFormatter(ai_provider),
        repository=repository,
    )


def _build_tts(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return TTSWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        tts_provider=_make_tts_provider(provider, config, books_dir),
        character_provider=_make_character_provider(provider, config),
        books_dir=books_dir,
    )


def _build_characters(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return CharactersWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        character_provider=_make_character_provider(provider, config),
    )


def _build_ambient(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return AmbientWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        provider=_make_ambient_provider(provider, config, books_dir),
        books_dir=books_dir,
    )


def _build_sfx(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return SfxWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        provider=_make_sfx_provider(provider, config, books_dir),
        books_dir=books_dir,
    )


def _build_music(books_dir: Path, provider: Optional[str]) -> Workflow:
    return MusicWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        books_dir=books_dir,
    )


def _build_mix(books_dir: Path, provider: Optional[str]) -> Workflow:
    return MixWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        books_dir=books_dir,
    )


WorkflowBuilder = Callable[[Path, Optional[str]], Workflow]

_WORKFLOW_BUILDERS: dict[str, WorkflowBuilder] = {
    "ai": _build_ai,
    "characters": _build_characters,
    "tts": _build_tts,
    "ambient": _build_ambient,
    "sfx": _build_sfx,
    "music": _build_music,
    "mix": _build_mix,
}


def create_workflow(
    workflow_name: str,
    books_dir: Path = Path("books"),
    provider: Optional[str] = None,
) -> Workflow:
    """Return a fully-wired :class:`Workflow` for *workflow_name*."""
    builder = _WORKFLOW_BUILDERS[workflow_name]
    return builder(books_dir, provider)
