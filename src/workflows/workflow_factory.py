"""Workflow factory: builds fully-wired Workflow instances by CLI name."""
from pathlib import Path
from typing import Callable, Optional

from src.ai.ai_provider import AIProvider
from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.audio.tts.audio_trimmer.audio_trimmer_pipeline import AudioTrimmerPipeline
from src.audio.tts.audio_trimmer.peak_level_trimmer import PeakLevelTrimmer
from src.audio.tts.audio_trimmer.start_and_end_beat_silence_trimmer import (
    StartAndEndBeatSilenceTrimmer,
)
from src.audio.tts.tts_provider import TTSProvider
from src.characters.character_provider import CharacterProvider
from src.config.config import Config
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader,
)
from src.parsers.project_gutenberg_book_source import ProjectGutenbergBookSource
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)
from src.prompts.chapter_parser.chapter_parser_prompt_builder import (
    ChapterParserPromptBuilder,
)
from src.repository.ai_artifact_store import FileAIArtifactStore
from src.repository.api_artifact_store import FileAPIArtifactStore
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.trimmers.audibility_trimmer import AudibilityTrimmer
from src.trimmers.beat_trimmer import BeatTrimmer
from src.trimmers.capitalization_trimmer import CapitalizationTrimmer
from src.trimmers.em_dash_trimmer import EmDashTrimmer
from src.trimmers.parenthetical_trimmer import ParentheticalTrimmer
from src.trimmers.quoted_punctuation_trimmer import QuotedPunctuationTrimmer
from src.trimmers.sentence_ending_trimmer import SentenceEndingTrimmer

from .ai_workflow import AIWorkflow
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


_TTS_PROVIDER_CHOICES = "elevenlabs, elevenlabs-dialogue, fish"


def _make_tts_provider_name(provider: Optional[str]) -> str:
    """Return the on-disk subdir name for the chosen TTS provider."""
    if provider == "elevenlabs":
        return "elevenlabs_v2"
    if provider == "elevenlabs-dialogue":
        return "elevenlabs_dialogue"
    if provider == "fish":
        return "fish_audio"
    raise ValueError(
        f"Unknown tts provider {provider!r}; choose one of: {_TTS_PROVIDER_CHOICES}"
    )


def _make_tts_provider(
    provider: Optional[str], config: Config, books_dir: Path,
) -> TTSProvider:
    if provider == "elevenlabs":
        from src.audio.tts.elevenlabs_v2_provider import ElevenLabsV2Provider
        return ElevenLabsV2Provider(
            api_key=config.require_elevenlabs_api_key(),
            books_dir=books_dir,
            artifact_store=FileAPIArtifactStore(),
        )
    if provider == "elevenlabs-dialogue":
        from src.audio.tts.elevenlabs_dialogue_provider import (
            ElevenLabsDialogueProvider,
        )
        return ElevenLabsDialogueProvider(
            api_key=config.require_elevenlabs_api_key(),
            books_dir=books_dir,
            artifact_store=FileAPIArtifactStore(),
        )
    if provider == "fish":
        from src.audio.tts.fish_audio_tts_provider import FishAudioTTSProvider
        return FishAudioTTSProvider(
            api_key=config.require_fish_audio_api_key(),
            books_dir=books_dir,
            artifact_store=FileAPIArtifactStore(),
        )
    raise ValueError(
        f"Unknown tts provider {provider!r}; choose one of: {_TTS_PROVIDER_CHOICES}"
    )


_CHARACTERS_PROVIDER_CHOICES = "elevenlabs, elevenlabs-dialogue, fish"


def _make_character_provider(
    provider: Optional[str], config: Config, books_dir: Path,
    book_language: str = "en",
) -> CharacterProvider:
    if provider in ("elevenlabs", "elevenlabs-dialogue"):
        from elevenlabs.client import ElevenLabs

        from src.characters.elevenlabs_library_character_provider import (
            ElevenLabsLibraryCharacterProvider,
        )
        api_key = config.require_elevenlabs_api_key()
        client = ElevenLabs(api_key=api_key)
        return ElevenLabsLibraryCharacterProvider(
            client=client,
            books_dir=books_dir,
            book_language=book_language,
            api_key=api_key,
            artifact_store=FileAPIArtifactStore(),
        )
    if provider == "fish":
        from src.characters.fish_audio_character_provider import (
            FishAudioCharacterProvider,
        )
        return FishAudioCharacterProvider()
    raise ValueError(
        f"Unknown characters provider {provider!r}; "
        f"choose one of: {_CHARACTERS_PROVIDER_CHOICES}"
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


def _build_repositories(books_dir: Path, config: Config) -> list[BookRepository]:
    """Return the repositories every workflow reads from index 0 and writes to in order."""
    del config
    return [FileBookRepository(base_dir=str(books_dir))]


_DEFAULT_BEAT_TRIMMERS: list[BeatTrimmer] = [
    AudibilityTrimmer(),
    ParentheticalTrimmer(),
    EmDashTrimmer(),
    QuotedPunctuationTrimmer(),
    SentenceEndingTrimmer(),
    CapitalizationTrimmer(),
]


def _build_ai(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    repositories = _build_repositories(books_dir, config)
    book_source = ProjectGutenbergBookSource(
        downloader=ProjectGutenbergHTMLBookDownloader(books_dir=str(books_dir)),
        metadata_parser=StaticProjectGutenbergHTMLMetadataParser(),
        content_parser=StaticProjectGutenbergHTMLContentParser(),
        repository=repositories[0],
        books_dir=str(books_dir),
    )
    ai_provider = _make_ai_provider(provider, config)
    return AIWorkflow(
        book_source=book_source,
        prompt_builder=ChapterParserPromptBuilder(),
        ai_provider=ai_provider,
        repositories=repositories,
        beat_trimmers=_DEFAULT_BEAT_TRIMMERS,
        artifact_store=FileAIArtifactStore(base_dir=str(books_dir)),
    )


def _build_tts(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return TTSWorkflow(
        repositories=_build_repositories(books_dir, config),
        tts_provider=_make_tts_provider(provider, config, books_dir),
        character_provider=_make_character_provider(provider, config, books_dir),
        books_dir=books_dir,
    )


def _build_characters(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return CharactersWorkflow(
        repositories=_build_repositories(books_dir, config),
        character_provider=_make_character_provider(provider, config, books_dir),
    )


def _build_sfx(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return SfxWorkflow(
        repositories=_build_repositories(books_dir, config),
        provider=_make_sfx_provider(provider, config, books_dir),
        books_dir=books_dir,
    )


def _build_music(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return MusicWorkflow(
        repositories=_build_repositories(books_dir, config),
        books_dir=books_dir,
    )


def _build_mix(books_dir: Path, provider: Optional[str]) -> Workflow:
    config = Config.from_env()
    return MixWorkflow(
        repositories=_build_repositories(books_dir, config),
        provider_name=_make_tts_provider_name(provider),
        books_dir=books_dir,
        trimmer_pipeline=AudioTrimmerPipeline([
            StartAndEndBeatSilenceTrimmer(),
            PeakLevelTrimmer(),
        ]),
    )


WorkflowBuilder = Callable[[Path, Optional[str]], Workflow]

_WORKFLOW_BUILDERS: dict[str, WorkflowBuilder] = {
    "ai": _build_ai,
    "characters": _build_characters,
    "tts": _build_tts,
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
