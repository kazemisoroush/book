"""Main entry point for audiobook generator."""
import argparse
from src.cli.download_command import DownloadCommand
from src.cli.parse_metadata_command import ParseMetadataCommand
from src.cli.parse_content_command import ParseContentCommand
from src.downloader.project_gutenberg_html_book_downloader import ProjectGutenbergHTMLBookDownloader
from src.parsers.static_project_gutenberg_html_metadata_parser import StaticProjectGutenbergHTMLMetadataParser
from src.parsers.static_project_gutenberg_html_content_parser import StaticProjectGutenbergHTMLContentParser


def main():
    """Main entry point - parse CLI arguments and execute commands."""
    parser = argparse.ArgumentParser(prog='book', description='Book processing CLI tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    subparsers.add_parser('download', help='Download books from Project Gutenberg')

    parse_metadata_parser = subparsers.add_parser('parse-metadata', help='Parse metadata from a downloaded book')
    parse_metadata_parser.add_argument('book_id', type=int, help='Book ID to parse')

    parse_content_parser = subparsers.add_parser('parse-content', help='Parse content from a downloaded book')
    parse_content_parser.add_argument('book_id', type=int, help='Book ID to parse')

    args = parser.parse_args()

    if args.command == 'download':
        downloader = ProjectGutenbergHTMLBookDownloader()
        command = DownloadCommand(downloader)
        success = command.execute(start_id=1, end_id=5)
        exit(0 if success else 1)
    elif args.command == 'parse-metadata':
        from datetime import datetime
        metadata_parser = StaticProjectGutenbergHTMLMetadataParser()
        command = ParseMetadataCommand(metadata_parser)
        metadata = command.execute(book_id=args.book_id)
        if metadata:
            release_date = metadata.releaseDate
            if release_date:
                try:
                    parsed_date = datetime.strptime(release_date, "%Y-%m-%d")
                    release_date = parsed_date.strftime("%B %d, %Y")
                except ValueError:
                    pass
            print(f"Title: {metadata.title}")
            print(f"Author: {metadata.author}")
            print(f"Language: {metadata.language}")
            print(f"Release Date: {release_date}")
            print(f"Original Publication: {metadata.originalPublication}")
            print(f"Credits: {metadata.credits}")
            exit(0)
        else:
            print(f"Failed to parse metadata for book {args.book_id}")
            exit(1)
    elif args.command == 'parse-content':
        content_parser = StaticProjectGutenbergHTMLContentParser()
        command = ParseContentCommand(content_parser)
        content = command.execute(book_id=args.book_id)
        if content:
            print(f"Total chapters: {len(content.chapters)}")
            for chapter in content.chapters:
                print(f"\nChapter {chapter.number}: {chapter.title}")
                print(f"  Sections: {len(chapter.sections)}")
                if chapter.sections:
                    print(f"  First section preview: {chapter.sections[0].text[:100]}...")
            exit(0)
        else:
            print(f"Failed to parse content for book {args.book_id}")
            exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
