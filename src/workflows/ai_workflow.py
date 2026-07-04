"""AI workflow: parse each chapter of a book through the chapter_parser prompt."""
import json
from bisect import insort
from typing import Optional

import structlog

from src.ai.ai_provider import AIProvider
from src.domain.beat import Beat, BeatType
from src.domain.character import Character
from src.domain.models import Book, BookContent, BookMetadata, Chapter
from src.parsers.book_source import BookSource
from src.prompts.chapter_parser.chapter_parser_prompt_builder import (
    ChapterParserPromptBuilder,
)
from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputCharacter,
    PromptInputMetadata,
    PromptInputSection,
)
from src.prompts.chapter_parser.output import PromptOutput
from src.repository.artifact_repository import ArtifactRepository
from src.repository.book_repository import BookRepository
from src.trimmers.beat_trimmer import BeatTrimmer
from src.trimmers.beat_trimmer_pipeline import apply_beat_trimmers
from src.validators.validation_gate_error import ValidationGateError
from src.validators.validator import Validator
from src.workflows.workflow import Workflow, WorkflowRequest

logger = structlog.get_logger(__name__)

_MAX_TOKENS = 16000


def _strip_code_fence(text: str) -> str:
    """Return *text* with a wrapping markdown code fence removed, if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


class AIWorkflow(Workflow):
    """Parse a book chapter-by-chapter via the chapter_parser prompt."""

    def __init__(
        self,
        book_source: BookSource,
        prompt_builder: ChapterParserPromptBuilder,
        ai_provider: AIProvider,
        repositories: list[BookRepository],
        beat_trimmers: list[BeatTrimmer] | None = None,
        artifact_repository: Optional[ArtifactRepository] = None,
        validators: list[Validator] | None = None,
    ) -> None:
        self._book_source = book_source
        self._prompt_builder = prompt_builder
        self._ai_provider = ai_provider
        self._repositories = repositories
        self._beat_trimmers: list[BeatTrimmer] = (
            list(beat_trimmers) if beat_trimmers is not None else []
        )
        self._artifact_repository = artifact_repository
        self._validators: list[Validator] = (
            list(validators) if validators is not None else []
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
            input_chapter = Chapter(
                number=chapter_to_parse.number,
                title=chapter_to_parse.title,
                label=chapter_to_parse.label,
                sections=chapter_to_parse.sections,
            )
            chapter_input = self._build_prompt_input(
                book.metadata,
                chapter_to_parse,
                known_characters=list(book.character_registry.characters),
            )
            prompt = self._prompt_builder.with_chapter(chapter_input).build()
            if self._artifact_repository is not None:
                self._artifact_repository.save_prompt(
                    book.book_id, chapter_to_parse, prompt,
                )
            raw = self._ai_provider.generate(prompt, max_tokens=_MAX_TOKENS)
            if self._artifact_repository is not None:
                self._artifact_repository.save_response(
                    book.book_id, chapter_to_parse, raw,
                )
            prompt_output = PromptOutput.from_dict(json.loads(_strip_code_fence(raw)))
            prompt_output = apply_beat_trimmers(prompt_output, self._beat_trimmers)

            self._apply_prompt_output(book, chapter_to_parse, prompt_output)
            self._validate_chapter(book, input_chapter, chapter_to_parse)
            for store in self._repositories:
                store.save_chapter(book, chapter_to_parse)

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

    def _validate_chapter(
        self, book: Book, input_chapter: Chapter, output_chapter: Chapter,
    ) -> None:
        """Run every validator on the chapter and raise if any rejects it."""
        if not self._validators:
            return

        input_book = Book(
            metadata=book.metadata,
            content=BookContent(chapters=[input_chapter]),
            character_registry=book.character_registry,
        )
        output_book = Book(
            metadata=book.metadata,
            content=BookContent(chapters=[output_chapter]),
            character_registry=book.character_registry,
        )

        failures: list[tuple[str, float, str]] = []
        for validator in self._validators:
            result = validator.validate(input_book, output_book)
            logger.info(
                "chapter_validated",
                book_id=book.book_id,
                chapter_number=output_chapter.number,
                validator=type(validator).__name__,
                deviation=result.deviation,
                detail=result.detail,
            )
            if not validator.passed(result):
                failures.append(
                    (type(validator).__name__, result.deviation, result.detail)
                )

        if failures:
            logger.error(
                "chapter_validation_failed",
                book_id=book.book_id,
                chapter_number=output_chapter.number,
                failures=failures,
            )
            raise ValidationGateError(
                book.book_id, output_chapter.number, failures,
            )

    @staticmethod
    def _build_prompt_input(
        metadata: BookMetadata,
        chapter: Chapter,
        known_characters: list[Character] | None = None,
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
            f"{chapter.display_name}. {chapter.title}."
            if chapter.title and chapter.title != chapter.display_name
            else f"{chapter.display_name}."
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

        characters = [
            PromptInputCharacter(
                id=c.id,
                name=c.name,
                gender=c.gender or "",
                age=c.age or "",
                accent=c.accent or "",
            )
            for c in (known_characters or [])
        ]

        return PromptInput(
            metadata=PromptInputMetadata(
                title=metadata.title,
                author=metadata.author or "",
            ),
            chapters=[PromptInputChapter(id=chapter.number, sections=sections)],
            characters=characters,
        )

    @staticmethod
    def _apply_prompt_output(
        book: Book, chapter: Chapter, response: PromptOutput,
    ) -> None:
        """Map the prompt response onto the chapter and book registry."""
        for out_char in response.characters:
            book.character_registry.upsert(Character(
                id=out_char.id,
                name=out_char.name,
                gender=out_char.gender,
                age=out_char.age,
                accent=out_char.accent,
            ))

        chapter.sections = []
        chapter.beats = [
            Beat(
                text=out_beat.text,
                beat_type=BeatType.from_string(out_beat.type),
                character_id=out_beat.char_id,
                emotion=out_beat.emotion,
                voice_settings=out_beat.voice_settings,
            )
            for out_beat in response.chapters[0].beats
        ]

        for idx, existing in enumerate(book.content.chapters):
            if existing.number == chapter.number:
                book.content.chapters[idx] = chapter
                return
        insort(book.content.chapters, chapter, key=lambda c: c.number)
