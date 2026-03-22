"""Project Gutenberg workflow for downloading and parsing books."""
import os
from typing import Optional
from src.workflows.workflow import Workflow
from src.domain.models import Book
from src.downloader.project_gutenberg_html_book_downloader import (
    ProjectGutenbergHTMLBookDownloader
)
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser
)


class ProjectGutenbergWorkflow(Workflow):
    """Workflow for processing Project Gutenberg HTML books.

    This workflow orchestrates:
    1. Downloading the book zip file
    2. Finding the HTML file
    3. Parsing metadata
    4. Parsing content
    5. Assembling the Book object

    Follows SOLID principles:
    - Single Responsibility: Orchestrates book processing pipeline
    - Dependency Inversion: Depends on parser/downloader abstractions
    """

    def __init__(self, downloader, metadata_parser, content_parser, section_parser=None):  # noqa: E501
        """Initialize the workflow with dependencies.

        Args:
            downloader: BookDownloader instance
            metadata_parser: BookMetadataParser instance
            content_parser: BookContentParser instance
            section_parser: Optional BookSectionParser for AI segmentation
        """
        self.downloader = downloader
        self.metadata_parser = metadata_parser
        self.content_parser = content_parser
        self.section_parser = section_parser

    @classmethod
    def create(cls, with_section_parser: bool = False) -> "ProjectGutenbergWorkflow":
        """Factory method to create workflow with default dependencies.

        Args:
            with_section_parser: If True, includes AI section parser (default: False)
                AI section parsing is expensive; disabled by default.

        Returns:
            ProjectGutenbergWorkflow instance with wired dependencies
        """
        downloader = ProjectGutenbergHTMLBookDownloader()
        metadata_parser = StaticProjectGutenbergHTMLMetadataParser()
        content_parser = StaticProjectGutenbergHTMLContentParser()

        section_parser = None
        # AI section parser is commented out — enable only when needed (it is expensive)
        # if with_section_parser:
        #     from src.parsers.ai_section_parser import AISectionParser
        #     from src.ai.aws_bedrock_provider import AWSBedrockProvider
        #     from src.config import Config
        #     config = Config.from_env()
        #     ai_provider = AWSBedrockProvider(config)
        #     section_parser = AISectionParser(ai_provider)

        return cls(downloader, metadata_parser, content_parser, section_parser)

    def run(self, input: str) -> Book:
        """Run the workflow to download and parse a book.

        Args:
            input: Project Gutenberg book URL (e.g.,
                   https://www.gutenberg.org/files/123/123-h.zip)

        Returns:
            Parsed Book object

        Raises:
            RuntimeError: If download fails or HTML file not found
        """
        # Step 1: Download the book
        if not self.downloader.parse(input):
            raise RuntimeError(f"Failed to download book from {input}")

        # Step 2: Find the downloaded HTML file
        book_id = self.downloader._extract_book_id(input)
        download_dir = f"books/{book_id}"

        html_file = self._find_html_file(download_dir)
        if not html_file:
            raise RuntimeError(f"No HTML file found in {download_dir}")

        # Step 3: Read HTML content
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Step 4: Parse metadata and content
        metadata = self.metadata_parser.parse(html_content)
        content = self.content_parser.parse(html_content)

        # Step 5: Segment sections if section parser provided
        if self.section_parser:
            for chapter in content.chapters:
                for section in chapter.sections:
                    section.segments = self.section_parser.parse(section)

        # Step 6: Assemble and return Book
        return Book(metadata=metadata, content=content)

    def _find_html_file(self, directory: str) -> Optional[str]:
        """Find the first HTML file in the directory recursively.

        Args:
            directory: Directory to search

        Returns:
            Path to HTML file, or None if not found
        """
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.html', '.htm')):
                    return os.path.join(root, filename)
        return None
