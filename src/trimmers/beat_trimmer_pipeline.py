"""Runs a sequence of BeatTrimmers and renumbers beat ids per chapter."""
from dataclasses import replace

from src.prompts.chapter_parser.output import PromptOutput, PromptOutputChapter
from src.trimmers.beat_trimmer import BeatTrimmer


def apply_beat_trimmers(
    output: PromptOutput, trimmers: list[BeatTrimmer],
) -> PromptOutput:
    """Apply each trimmer in order to every chapter, renumbering ids after drops."""
    new_chapters = [_trim_chapter(ch, trimmers) for ch in output.chapters]
    return replace(output, chapters=new_chapters)


def _trim_chapter(
    chapter: PromptOutputChapter, trimmers: list[BeatTrimmer],
) -> PromptOutputChapter:
    beats = chapter.beats
    for trimmer in trimmers:
        beats = trimmer.trim(beats)
    renumbered = [replace(b, id=i + 1) for i, b in enumerate(beats)]
    return replace(chapter, beats=renumbered)
