#!/usr/bin/env python3
"""Test CharacterRegistry AI integration on a small sample."""
import sys
from src.parsers.text_parser import TextBookParser
from src.character_registry import CharacterRegistry
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config import get_config

# Sample text from Pride and Prejudice Chapter 1
SAMPLE_TEXT = """Chapter I.

It is a truth universally acknowledged, that a single man in possession of
a good fortune, must be in want of a wife.

However little known the feelings or views of such a man may be on his
first entering a neighbourhood, this truth is so well fixed in the minds
of the surrounding families, that he is considered the rightful property
of some one or other of their daughters.

"My dear Mr. Bennet," said his lady to him one day, "have you heard that
Netherfield Park is let at last?"

Mr. Bennet replied that he had not.

"But it is," returned she; "for Mrs. Long has just been here, and she
told me all about it."

Mr. Bennet made no answer.

"Do you not want to know who has taken it?" cried his wife impatiently.

"_You_ want to tell me, and I have no objection to hearing it."

This was invitation enough.

"Why, my dear, you must know, Mrs. Long says that Netherfield Park is
taken by a young man of large fortune from the north of England; that he
came down on Monday in a chaise and four to see the place, and was so
much delighted with it, that he agreed with Mr. Morris immediately; that
he is to take possession before Michaelmas, and some of his servants are
to be in the house by the end of next week."
"""

def main():
    print("=" * 80)
    print("Testing CharacterRegistry AI Integration (Small Sample)")
    print("=" * 80)

    # Test 1: WITHOUT AI (baseline)
    print("\n1. WITHOUT AI (baseline - simple normalization)")
    print("-" * 80)

    parser_no_ai = TextBookParser()

    # Write sample to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(SAMPLE_TEXT)
        temp_file = f.name

    book = parser_no_ai.parse(temp_file)
    chapter = book.chapters[0]

    dialogue = [s for s in chapter.segments if s.is_dialogue()]
    print(f"Dialogue segments found: {len(dialogue)}")

    print("\nDialogue (WITHOUT AI):")
    for i, seg in enumerate(dialogue, 1):
        print(f"  {i}. [{seg.speaker}] {seg.text[:60]}...")

    unique_speakers_no_ai = set(s.speaker for s in dialogue if s.speaker)
    print(f"\nUnique speakers: {sorted(unique_speakers_no_ai)}")

    # Test 2: WITH AI
    print("\n\n2. WITH AI (CharacterRegistry)")
    print("-" * 80)

    try:
        config = get_config()
        print(f"AWS Region: {config.aws.region}")
        print(f"Model: {config.aws.bedrock_model_id}")

        # Create AI provider
        ai_provider = AWSBedrockProvider(config)

        # Create registry with AI
        registry = CharacterRegistry(ai_provider=ai_provider)

        # Create parser with registry
        parser_with_ai = TextBookParser(character_registry=registry)

        print("\nParsing with AI (may take 10-20 seconds for AI calls)...")
        sys.stdout.flush()

        book_ai = parser_with_ai.parse(temp_file)
        chapter_ai = book_ai.chapters[0]

        dialogue_ai = [s for s in chapter_ai.segments if s.is_dialogue()]
        print(f"\nDialogue (WITH AI):")
        for i, seg in enumerate(dialogue_ai, 1):
            print(f"  {i}. [{seg.speaker}] {seg.text[:60]}...")

        unique_speakers_ai = set(s.speaker for s in dialogue_ai if s.speaker)

        # Show character registry
        print("\n\nCharacter Registry:")
        print("-" * 80)
        characters = registry.get_all_characters()
        print(f"Total characters: {len(characters)}")

        for name, char in characters.items():
            print(f"\n{name}:")
            print(f"  Aliases: {', '.join(char.aliases)}")
            print(f"  Context: {char.context[:100]}...")

        print("\n\nComparison:")
        print("-" * 80)
        print(f"WITHOUT AI: {len(unique_speakers_no_ai)} unique speakers -> {sorted(unique_speakers_no_ai)}")
        print(f"WITH AI:    {len(unique_speakers_ai)} unique speakers -> {sorted(unique_speakers_ai)}")
        print(f"\nImprovement: {len(unique_speakers_no_ai) - len(unique_speakers_ai)} fewer speaker labels")
        print("(AI consolidates aliases like 'lady', 'his wife', 'she' into canonical names)")

    except Exception as e:
        print(f"\nAI test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        import os
        os.unlink(temp_file)

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
