"""Run the full AI parse pipeline on a locally-downloaded Project Gutenberg book.

Usage:
    python scripts/parse_book.py <book_id> [output_file]

Example:
    python scripts/parse_book.py 1342
    python scripts/parse_book.py 1342 out/pride.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.parsers.ai_section_parser import AISectionParser
from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config.config import Config
from src.domain.models import Book, CharacterRegistry


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    book_id = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else f"output_{book_id}.json"

    html_file = Path(f"books/{book_id}/pg{book_id}-images.html")
    if not html_file.exists():
        print(f"Error: {html_file} not found", file=sys.stderr)
        sys.exit(1)

    html = html_file.read_text(encoding="utf-8")

    metadata = StaticProjectGutenbergHTMLMetadataParser().parse(html)
    content = StaticProjectGutenbergHTMLContentParser().parse(html)

    ai_provider = AWSBedrockProvider(Config.from_env())
    section_parser = AISectionParser(ai_provider)
    registry = CharacterRegistry.with_default_narrator()

    total = len(content.chapters)
    for i, chapter in enumerate(content.chapters):
        print(f"Chapter {i + 1}/{total}: {chapter.title}", file=sys.stderr, flush=True)
        for idx, section in enumerate(chapter.sections):
            ctx = chapter.sections[max(0, idx - 3):idx]
            section.segments, registry = section_parser.parse(
                section, registry, context_window=ctx
            )

    book = Book(metadata=metadata, content=content, character_registry=registry)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(book.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Done → {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
