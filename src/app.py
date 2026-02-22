"""Audiobook generator application logic."""
from src.config import Config
from src.parsers.text_parser import TextBookParser
from src.tts.elevenlabs_provider import ElevenLabsProvider
from src.tts.local_provider import LocalTTSProvider
from src.voice_assignment import VoiceAssigner
from src.audio_generator import AudioGenerator
from src.audio_combiner import SimpleConcatStrategy, CrossfadeStrategy


def run_audiobook_generator(config: Config) -> None:
    """Run the audiobook generator with the given configuration.

    Args:
        config: Configuration object with all settings
    """
    # Parse the book
    print(f"Parsing book: {config.book_path}")
    book_parser = TextBookParser()
    book = book_parser.parse(str(config.book_path))

    print(f"Parsed: {book.title}")
    if book.author:
        print(f"Author: {book.author}")
    print(f"Chapters: {len(book.chapters)}")

    # Setup voice assigner
    voice_assigner = VoiceAssigner(narrator_voice="narrator")

    # Setup TTS provider
    if config.tts_provider == "elevenlabs":
        print("Using ElevenLabs TTS provider")
        tts_provider = ElevenLabsProvider(api_key=config.elevenlabs_api_key)
        available_voices = tts_provider.get_available_voices()
        print(f"Available voices: {len(available_voices)}")
        character_voices = list(available_voices.values())[:10]
        voice_assigner.set_available_voices(character_voices)
    else:  # local
        print("Using local TTS provider (espeak)")
        tts_provider = LocalTTSProvider()
        available_voices = tts_provider.get_available_voices()
        print(f"Available voices: {list(available_voices.keys())}")
        character_voices = [v for k, v in available_voices.items() if k != "narrator"]
        voice_assigner.set_available_voices(character_voices)

    # Discover characters
    characters = voice_assigner.discover_characters(book)
    print(f"\nDiscovered {len(characters)} unique characters")

    if config.discover_characters_only:
        print("\nCharacters:")
        for char in characters:
            print(f"  - {char}")
        return

    # Setup audio generator with options
    print("\nConfiguration:")
    print(f"  Segment grouping: {'enabled' if config.use_grouping else 'disabled'}")
    print(f"  Combine to single file: {'yes' if config.combine_files else 'no'}")
    print(f"  Chapter announcements: {'enabled' if config.announce_chapters else 'disabled'}")
    print(f"  Transcript files: {'enabled' if config.write_transcripts else 'disabled'}")

    if config.crossfade_duration:
        print(f"  Crossfade: {config.crossfade_duration}s between segments")
        combiner_strategy = CrossfadeStrategy(crossfade_duration=config.crossfade_duration)
    else:
        print("  Combining method: simple concat (fast, lossless)")
        combiner_strategy = SimpleConcatStrategy()

    generator = AudioGenerator(
        tts_provider,
        voice_assigner,
        use_grouping=config.use_grouping,
        combine_to_single_file=config.combine_files,
        announce_chapters=config.announce_chapters,
        write_transcripts=config.write_transcripts
    )

    if config.combine_files:
        generator.combiner.set_strategy(combiner_strategy)

    # Generate audiobook
    print(f"\nGenerating audiobook to: {config.output_dir}")
    print("This may take a while...\n")

    def progress_callback(current, total):
        print(f"Chapter {current}/{total} complete")

    try:
        generator.generate_audiobook(book, config.output_dir, progress_callback)
        print("\n✅ Audiobook generation complete!")
        print(f"📁 Output: {config.output_dir}/")

        if config.combine_files:
            chapter_files = sorted(config.output_dir.glob("*.wav"))
            total_size = sum(f.stat().st_size for f in chapter_files) / 1024 / 1024
            print(f"📊 Generated {len(chapter_files)} chapter files ({total_size:.1f} MB)")

    except Exception as e:
        import sys
        import traceback
        print(f"\n❌ Error generating audiobook: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
