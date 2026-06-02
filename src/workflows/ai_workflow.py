"""AI workflow: parse each chapter of a book through the chapter_parser prompt."""
import json
from bisect import insort

import structlog

from src.ai.ai_provider import AIProvider
from src.domain.beat import Beat, BeatType
from src.domain.character import Character
from src.domain.character_id import build_character_id
from src.domain.models import Book, BookMetadata, Chapter, Section
from src.parsers.book_source import BookSource
from src.prompts.chapter_parser.chapter_parser_prompt_builder import (
    ChapterParserPromptBuilder,
)
from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputMetadata,
    PromptInputSection,
)
from src.prompts.chapter_parser.output import PromptOutput
from src.repository.book_repository import BookRepository
from src.trimmers.beat_trimmer import BeatTrimmer
from src.trimmers.beat_trimmer_pipeline import apply_beat_trimmers
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)

_MAX_TOKENS = 16000


class AIWorkflow(Workflow):
    """Parse a book chapter-by-chapter via the chapter_parser prompt."""

    def __init__(
        self,
        book_source: BookSource,
        prompt_builder: ChapterParserPromptBuilder,
        ai_provider: AIProvider,
        repository: BookRepository,
        beat_trimmers: list[BeatTrimmer] | None = None,
    ) -> None:
        self._book_source = book_source
        self._prompt_builder = prompt_builder
        self._ai_provider = ai_provider
        self._repository = repository
        self._beat_trimmers: list[BeatTrimmer] = (
            list(beat_trimmers) if beat_trimmers is not None else []
        )

    def run(self, request: WorkflowRequest) -> Book:
        logger.info("ai_workflow_started", url=request.url)

        ctx = self._book_source.get_book(
            request.url,
            request.start_chapter,
            request.end_chapter,
            request.refresh,
        )
        book = ctx.book

        logger.info(
            "ai_beatation_started",
            title=book.metadata.title,
            total_chapters=len(ctx.content.chapters),
            chapters_to_parse=len(ctx.chapters_to_parse),
        )

        for chapter_to_parse in ctx.chapters_to_parse:
            chapter_input = self._build_prompt_input(book.metadata, chapter_to_parse)
            prompt = self._prompt_builder.with_chapter(chapter_input).build()
            raw = self._ai_provider.generate(prompt, max_tokens=_MAX_TOKENS)
            prompt_output = PromptOutput.from_dict(json.loads(raw))
            prompt_output = apply_beat_trimmers(prompt_output, self._beat_trimmers)

            self._apply_prompt_output(book, chapter_to_parse, prompt_output)
            self._repository.save(book)

            logger.info(
                "chapter_parsed_and_flushed",
                book_id=book.book_id,
                chapter_number=chapter_to_parse.number,
                total_chapters_in_book=len(book.content.chapters),
            )

        logger.info(
            "ai_workflow_complete",
            title=book.metadata.title,
            character_count=len(book.character_registry.characters),
        )
        return book

    @staticmethod
    def _build_prompt_input(
        metadata: BookMetadata, chapter: Chapter,
    ) -> PromptInput:
        """Build the typed chapter_parser prompt input for one chapter."""
        sections: list[PromptInputSection] = []

        if chapter.is_first:
            title_text = (
                f"{metadata.title}, by {metadata.author}."
                if metadata.author
                else f"{metadata.title}."
            )
            sections.append(PromptInputSection(
                id=len(sections) + 1,
                text=title_text,
                type="book_title_announcement",
            ))

        chapter_text = (
            f"Chapter {chapter.number}. {chapter.title}."
            if chapter.title
            else f"Chapter {chapter.number}."
        )
        sections.append(PromptInputSection(
            id=len(sections) + 1,
            text=chapter_text,
            type="chapter_announcement",
        ))

        for sec in chapter.sections:
            sections.append(PromptInputSection(
                id=len(sections) + 1,
                text=sec.text,
                type=sec.section_type or "text",
            ))

        return PromptInput(
            metadata=PromptInputMetadata(
                title=metadata.title,
                author=metadata.author or "",
            ),
            chapters=[PromptInputChapter(id=chapter.number, sections=sections)],
        )

    @staticmethod
    def _apply_prompt_output(
        book: Book, chapter: Chapter, response: PromptOutput,
    ) -> None:
        """Map the prompt response onto the chapter and book registry."""
        numeric_to_character_id: dict[int, str] = {}
        for out_char in response.characters:
            character_id = build_character_id(book.book_id, out_char.name)
            numeric_to_character_id[out_char.id] = character_id
            book.character_registry.upsert(Character(
                character_id=character_id,
                name=out_char.name,
                sex=out_char.sex,
                age=out_char.age,
                is_narrator=(out_char.id == 1),
            ))

        beats: list[Beat] = []
        for out_beat in response.chapters[0].beats:
            beats.append(Beat(
                text=out_beat.text,
                beat_type=BeatType.from_string(out_beat.type),
                character_id=numeric_to_character_id.get(out_beat.character_id),
                emotion=out_beat.emotion,
            ))
        chapter.sections = [Section(text="", beats=beats)]

        for idx, existing in enumerate(book.content.chapters):
            if existing.number == chapter.number:
                book.content.chapters[idx] = chapter
                return
        insort(book.content.chapters, chapter, key=lambda c: c.number)
