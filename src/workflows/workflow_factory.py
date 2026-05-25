"""Workflow factory: builds fully-wired Workflow instances by CLI name.

All production dependency wiring lives here. Workflow classes themselves
only declare what they need via ``__init__``; the factory decides which
concrete components to inject.
"""
from pathlib import Path
from typing import Callable, Optional

from src.ai.ai_provider import AIProvider
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.ambient.elevenlabs_ambient_provider import ElevenLabsAmbientProvider
from src.audio.sound_effect.elevenlabs_sound_effect_provider import (
    ElevenLabsSoundEffectProvider,
)
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
from src.audio.tts.tts_provider import TTSProvider
from src.characters.character_provider import CharacterProvider
from src.characters.fish_audio_character_provider import FishAudioCharacterProvider
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


def _build_ai(books_dir: Path, provider: Optional[str]) -> Workflow:
    repository = FileBookRepository(base_dir=str(books_dir))
    book_source = ProjectGutenbergBookSource(
        downloader=ProjectGutenbergHTMLBookDownloader(),
        metadata_parser=StaticProjectGutenbergHTMLMetadataParser(),
        content_parser=StaticProjectGutenbergHTMLContentParser(),
        repository=repository,
    )

    config = Config.from_env()
    ai_provider: AIProvider
    if provider == "anthropic":
        from src.ai.anthropic_provider import AnthropicProvider
        ai_provider = AnthropicProvider(config)
    elif provider == "claude-code":
        from src.ai.claude_code_provider import ClaudeCodeProvider
        ai_provider = ClaudeCodeProvider(config)
    else:
        ai_provider = AWSBedrockProvider(config)

    return AIWorkflow(
        book_source=book_source,
        section_parser=AISectionParser(ai_provider),
        announcement_formatter=AnnouncementFormatter(ai_provider),
        repository=repository,
    )


def _build_tts(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    tts_provider: TTSProvider
    if provider == "elevenlabs":
        from src.audio.tts.elevenlabs_tts_provider import ElevenLabsTTSProvider
        tts_provider = ElevenLabsTTSProvider(
            api_key=config.require_elevenlabs_api_key(),
            books_dir=books_dir,
        )
    else:
        tts_provider = FishAudioTTSProvider(
            api_key=config.require_fish_audio_api_key(),
            books_dir=books_dir,
        )
    return TTSWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        tts_provider=tts_provider,
        character_provider=_make_character_provider(provider, config),
        books_dir=books_dir,
    )


def _build_characters(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return CharactersWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        character_provider=_make_character_provider(provider, config),
    )


def _make_character_provider(provider: Optional[str], config: Config) -> CharacterProvider:
    if provider == "elevenlabs":
        from elevenlabs.client import ElevenLabs

        from src.characters.elevenlabs_character_provider import (
            ElevenLabsCharacterProvider,
        )
        client = ElevenLabs(api_key=config.require_elevenlabs_api_key())
        return ElevenLabsCharacterProvider(client=client)
    return FishAudioCharacterProvider()


def _build_ambient(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    ambient_provider: AmbientProvider
    if provider == "audiogen":
        from src.audio.ambient.audiogen_ambient_provider import (
            AudioGenAmbientProvider,
        )
        ambient_provider = AudioGenAmbientProvider(books_dir=books_dir)
    else:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=config.elevenlabs_api_key or "")
        ambient_provider = ElevenLabsAmbientProvider(
            client=client,
            books_dir=books_dir,
        )
    return AmbientWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        provider=ambient_provider,
        books_dir=books_dir,
    )


def _build_sfx(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    sfx_provider: SoundEffectProvider
    if provider == "audiogen":
        from src.audio.sound_effect.audiogen_sound_effect_provider import (
            AudioGenSoundEffectProvider,
        )
        sfx_provider = AudioGenSoundEffectProvider(books_dir=books_dir)
    else:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=config.elevenlabs_api_key or "")
        sfx_provider = ElevenLabsSoundEffectProvider(
            client=client,
            books_dir=books_dir,
        )
    return SfxWorkflow(
        repository=FileBookRepository(base_dir=str(books_dir)),
        provider=sfx_provider,
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

# Registry of workflow builders keyed by CLI name. To add a new workflow,
# register its builder here; create_workflow() stays closed for modification
# (open/closed principle).
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
