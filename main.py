"""Command-line interface for audiobook generator."""
import argparse
import sys
from pathlib import Path

from src.parsers.text_parser import TextBookParser
from src.tts.elevenlabs_provider import ElevenLabsProvider
from src.tts.local_provider import LocalTTSProvider
from src.voice_assignment import VoiceAssigner
from src.audio_generator import AudioGenerator
from src.audio_combiner import SimpleConcatStrategy, CrossfadeStrategy


def main():
    """Main entry point - single entry for the entire application."""
    parser = argparse.ArgumentParser(
        description="Generate full-cast audiobooks from text files"
    )

    parser.add_argument(
        "book_path",
        type=Path,
        help="Path to the book file to convert"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("output"),
        help="Output directory for audio files (default: output)"
    )

    parser.add_argument(
        "--provider",
        choices=["elevenlabs", "local"],
        default="local",
        help="TTS provider to use (default: local)"
    )

    parser.add_argument(
        "--elevenlabs-api-key",
        type=str,
        help="ElevenLabs API key (required if using elevenlabs provider)"
    )

    parser.add_argument(
        "--no-grouping",
        action="store_true",
        help="Disable segment grouping (creates more, smaller segments)"
    )

    parser.add_argument(
        "--no-combine",
        action="store_true",
        help="Keep separate audio files instead of combining into one per chapter"
    )

    parser.add_argument(
        "--crossfade",
        type=float,
        metavar="SECONDS",
        help="Use crossfade between segments (slower, requires re-encoding). Specify duration in seconds."
    )

    parser.add_argument(
        "--discover-characters",
        action="store_true",
        help="Discover and print characters without generating audio"
    )

    parser.add_argument(
        "--no-announce",
        action="store_true",
        help="Skip chapter/preface title announcements at the beginning of each section"
    )

    parser.add_argument(
        "--no-transcripts",
        action="store_true",
        help="Skip generating transcript text files alongside audio files"
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.book_path.exists():
        print(f"Error: Book file not found: {args.book_path}", file=sys.stderr)
        sys.exit(1)

    # Parse the book
    print(f"Parsing book: {args.book_path}")
    book_parser = TextBookParser()
    book = book_parser.parse(str(args.book_path))

    print(f"Parsed: {book.title}")
    if book.author:
        print(f"Author: {book.author}")
    print(f"Chapters: {len(book.chapters)}")

    # Setup voice assigner
    voice_assigner = VoiceAssigner(narrator_voice="narrator")

    # Setup TTS provider
    if args.provider == "elevenlabs":
        if not args.elevenlabs_api_key:
            print("Error: --elevenlabs-api-key required for elevenlabs provider", file=sys.stderr)
            sys.exit(1)

        print("Using ElevenLabs TTS provider")
        tts_provider = ElevenLabsProvider(api_key=args.elevenlabs_api_key)
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

    if args.discover_characters:
        print("\nCharacters:")
        for char in characters:
            print(f"  - {char}")
        return

    # Setup audio generator with options
    use_grouping = not args.no_grouping
    combine_files = not args.no_combine
    announce_chapters = not args.no_announce
    write_transcripts = not args.no_transcripts

    print("\nConfiguration:")
    print(f"  Segment grouping: {'enabled' if use_grouping else 'disabled'}")
    print(f"  Combine to single file: {'yes' if combine_files else 'no'}")
    print(f"  Chapter announcements: {'enabled' if announce_chapters else 'disabled'}")
    print(f"  Transcript files: {'enabled' if write_transcripts else 'disabled'}")

    if args.crossfade:
        print(f"  Crossfade: {args.crossfade}s between segments")
        combiner_strategy = CrossfadeStrategy(crossfade_duration=args.crossfade)
    else:
        print("  Combining method: simple concat (fast, lossless)")
        combiner_strategy = SimpleConcatStrategy()

    generator = AudioGenerator(
        tts_provider,
        voice_assigner,
        use_grouping=use_grouping,
        combine_to_single_file=combine_files,
        announce_chapters=announce_chapters,
        write_transcripts=write_transcripts
    )

    if combine_files:
        generator.combiner.set_strategy(combiner_strategy)

    # Generate audiobook
    print(f"\nGenerating audiobook to: {args.output}")
    print("This may take a while...\n")

    def progress_callback(current, total):
        print(f"Chapter {current}/{total} complete")

    try:
        generator.generate_audiobook(book, args.output, progress_callback)
        print("\n✅ Audiobook generation complete!")
        print(f"📁 Output: {args.output}/")

        if combine_files:
            chapter_files = sorted(args.output.glob("*.wav"))
            total_size = sum(f.stat().st_size for f in chapter_files) / 1024 / 1024
            print(f"📊 Generated {len(chapter_files)} chapter files ({total_size:.1f} MB)")

    except Exception as e:
        print(f"\n❌ Error generating audiobook: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
