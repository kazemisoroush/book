"""Main entry point for audiobook generator."""
import argparse
from datetime import datetime
from src.cli.download_command import DownloadCommand
from src.cli.parse_command import ParseCommand
from src.downloader.project_gutenberg_html_book_downloader import ProjectGutenbergHTMLBookDownloader
from src.parsers.static_project_gutenberg_html_metadata_parser import StaticProjectGutenbergHTMLMetadataParser
from src.parsers.static_project_gutenberg_html_content_parser import StaticProjectGutenbergHTMLContentParser


def main():
    """Main entry point - parse CLI arguments and execute commands."""
    parser = argparse.ArgumentParser(prog='book', description='Book processing CLI tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    subparsers.add_parser('download', help='Download books from Project Gutenberg')

    parse_parser = subparsers.add_parser('parse', help='Parse a downloaded book')
    parse_parser.add_argument('book_id', type=int, help='Book ID to parse')

    args = parser.parse_args()

    if args.command == 'download':
        downloader = ProjectGutenbergHTMLBookDownloader()
        command = DownloadCommand(downloader)
        success = command.execute(start_id=1, end_id=5)
        exit(0 if success else 1)
    elif args.command == 'parse':
        metadata_parser = StaticProjectGutenbergHTMLMetadataParser()
        content_parser = StaticProjectGutenbergHTMLContentParser()
        command = ParseCommand(metadata_parser, content_parser)
        book = command.execute(book_id=args.book_id)
        if book:
            release_date = book.metadata.releaseDate
            if release_date:
                try:
                    parsed_date = datetime.strptime(release_date, "%Y-%m-%d")
                    release_date = parsed_date.strftime("%B %d, %Y")
                except ValueError:
                    pass

            print("=" * 80)
            print(f"Title: {book.metadata.title}")
            print(f"Author: {book.metadata.author}")
            print(f"Language: {book.metadata.language}")
            print(f"Release Date: {release_date}")
            print("=" * 80)
            print(f"\nTotal chapters: {len(book.content.chapters)}")

            for chapter in book.content.chapters:
                print(f"\nChapter {chapter.number}: {chapter.title}")
                print(f"  Sections: {len(chapter.sections)}")
                if chapter.sections:
                    preview = chapter.sections[0].text[:100]
                    print(f"  Preview: {preview}...")

            exit(0)
        else:
            print(f"Failed to parse book {args.book_id}")
            exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
