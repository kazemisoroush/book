"""Mood tracker — owns the story-mood state machine during book parsing.

The section parser emits a :class:`MoodAction` per chunk. The tracker
applies those actions to a :class:`MoodRegistry`, keeping track of the
currently-open mood, synthesising stable ``mood_id``s, and running the
post-parse passes defined by the US-034 spec:

1. **Close pass** — close any mood still open at end-of-chapter.
2. **Merge pass** — merge moods shorter than two sections into the
   nearest neighbour to prevent per-paragraph mood churn.
3. **Back-fill pass** — populate :attr:`Section.mood_id` from the
   registry so consumers can look up moods in O(1).

The tracker is a workflow-layer concern: it does not know how the parser
produced the action, only what to do with it.
"""
from dataclasses import replace as dc_replace
from typing import Optional

import structlog

from src.domain.models import Book, Mood, MoodRegistry, SectionRef
from src.parsers.ai_section_parser import MoodAction

logger = structlog.get_logger(__name__)


class MoodTracker:
    """Applies :class:`MoodAction`s to a :class:`MoodRegistry` during parsing.

    One tracker instance owns the mood state for a single book. Callers
    advance it per section via :meth:`apply` and close each chapter via
    :meth:`close_chapter`. After the whole book is parsed, call
    :meth:`finalize` to run the merge + back-fill passes.
    """

    def __init__(self, registry: MoodRegistry) -> None:
        self._registry = registry
        self._open_mood_id: Optional[str] = None
        self._chapter_mood_count: dict[int, int] = {}

    @property
    def open_mood_id(self) -> Optional[str]:
        """Return the currently-open mood_id, or ``None`` if no mood is open."""
        return self._open_mood_id

    def apply(
        self, action: Optional[MoodAction], position: SectionRef,
    ) -> None:
        """Apply a parser-emitted mood action at *position*.

        Unknown action shapes are ignored (the parser already logs warnings
        for malformed actions). When no action is supplied, the tracker
        extends the currently-open mood if one exists, otherwise does nothing.
        """
        if action is None:
            self._extend_open_mood(position)
            return

        if action.kind == "open":
            self._open_new_mood(action.description, position)
            return

        if action.kind == "continue":
            mood_id = action.mood_id
            if mood_id is None or self._registry.get(mood_id) is None:
                # Parser coerces unknown ids upstream; guard anyway.
                self._open_new_mood(None, position)
                return
            self._open_mood_id = mood_id
            self._extend_mood(mood_id, position)
            return

        if action.kind == "close_and_open":
            self._close_mood(action.close_mood_id, position)
            self._open_new_mood(action.description, position)
            return

    def close_chapter(self, last_position: SectionRef) -> None:
        """Close any open mood at end-of-chapter, extending its end to *last_position*.

        Per the US-034 spec, moods are bounded within a chapter. Arcs that
        span chapters open a fresh mood in the next chapter with
        ``continues_from`` set by a later call.
        """
        if self._open_mood_id is None:
            return
        self._extend_mood(self._open_mood_id, last_position)
        self._open_mood_id = None

    def finalize(self, book: Book) -> None:
        """Run merge + back-fill passes after all chapters are parsed.

        Moods that cover fewer than two sections are merged into whichever
        textually-adjacent neighbour is closer (earlier one, by default).
        Then every :class:`Section` is stamped with its ``mood_id``.
        """
        self._merge_short_moods()
        self._backfill_section_mood_ids(book)

    # ── internals ────────────────────────────────────────────────────────

    def _open_new_mood(
        self, description: Optional[str], position: SectionRef,
    ) -> None:
        """Synthesise a new mood_id and register it starting at *position*."""
        chapter = position.chapter
        self._chapter_mood_count[chapter] = self._chapter_mood_count.get(chapter, 0) + 1
        mood_id = f"ch{chapter}_mood_{self._chapter_mood_count[chapter]}"
        mood = Mood(
            mood_id=mood_id,
            description=description or "(unspecified)",
            start=position,
            end=position,
        )
        self._registry.upsert(mood)
        self._open_mood_id = mood_id

    def _extend_open_mood(self, position: SectionRef) -> None:
        """Extend the currently-open mood's end to *position* (if any)."""
        if self._open_mood_id is None:
            return
        self._extend_mood(self._open_mood_id, position)

    def _extend_mood(self, mood_id: str, position: SectionRef) -> None:
        """Set the end of *mood_id* to *position* if it advances the span."""
        mood = self._registry.get(mood_id)
        if mood is None:
            return
        if _section_index_key(position) >= _section_index_key(mood.end):
            self._registry.upsert(dc_replace(mood, end=position))

    def _close_mood(
        self, mood_id: Optional[str], position: SectionRef,
    ) -> None:
        """Close *mood_id* by extending its end to just before *position*.

        Falls back to the currently-open mood when *mood_id* is missing
        or unknown. The closing section itself belongs to the new mood
        about to be opened.
        """
        target = mood_id if mood_id and self._registry.get(mood_id) else self._open_mood_id
        if target is None:
            return
        mood = self._registry.get(target)
        if mood is None:
            return
        # Close at the previous section if possible; otherwise at the start.
        close_end = _previous_section(position, fallback=mood.start)
        if _section_index_key(close_end) < _section_index_key(mood.start):
            close_end = mood.start
        self._registry.upsert(dc_replace(mood, end=close_end))
        if self._open_mood_id == target:
            self._open_mood_id = None

    def _merge_short_moods(self) -> None:
        """Merge moods spanning fewer than two sections into an adjacent neighbour.

        Moods are evaluated per chapter (moods are chapter-bounded). A mood
        is merged into the immediately-preceding mood in the same chapter
        if present; otherwise the immediately-following one. A lone short
        mood in a chapter is kept as-is since there is no neighbour to
        absorb it.
        """
        moods = sorted(self._registry.all(), key=lambda m: _section_index_key(m.start))
        by_chapter: dict[int, list[Mood]] = {}
        for m in moods:
            by_chapter.setdefault(m.start.chapter, []).append(m)

        for chapter_moods in by_chapter.values():
            if len(chapter_moods) <= 1:
                continue
            for idx, mood in enumerate(chapter_moods):
                span = _span_length(mood)
                if span >= 2:
                    continue
                neighbour = (
                    chapter_moods[idx - 1] if idx > 0 else chapter_moods[idx + 1]
                )
                # Anchor against the neighbour so we don't lose its id/description.
                # Absorbing a later mood extends the previous neighbour's end.
                # Absorbing an earlier mood extends the following neighbour's start.
                if idx > 0:
                    self._registry.upsert(dc_replace(neighbour, end=mood.end))
                else:
                    self._registry.upsert(
                        dc_replace(neighbour, start=mood.start)
                    )
                # Drop the short mood.
                self._registry._moods.pop(mood.mood_id, None)
                logger.debug(
                    "story_mood_merged",
                    merged_id=mood.mood_id,
                    into=neighbour.mood_id,
                )

    def _backfill_section_mood_ids(self, book: Book) -> None:
        """Populate :attr:`Section.mood_id` for every section in *book*.

        Iterates every chapter/section and finds the mood whose span
        covers the section's position. Sections that fall outside any
        mood span (unlikely after close/merge) keep ``mood_id`` unset.
        """
        moods = sorted(
            self._registry.all(), key=lambda m: _section_index_key(m.start),
        )
        for chapter in book.content.chapters:
            for idx, section in enumerate(chapter.sections):
                pos = SectionRef(chapter=chapter.number, section=idx + 1)
                section.mood_id = _find_covering_mood(pos, moods)


def _section_index_key(ref: SectionRef) -> tuple[int, int]:
    """Tuple key for ordering section refs by chapter then section."""
    return (ref.chapter, ref.section)


def _previous_section(
    ref: SectionRef, fallback: SectionRef,
) -> SectionRef:
    """Return the section immediately before *ref* within its chapter."""
    if ref.section <= 1:
        return fallback
    return SectionRef(chapter=ref.chapter, section=ref.section - 1)


def _span_length(mood: Mood) -> int:
    """Inclusive section count for a mood that stays within one chapter."""
    if mood.start.chapter != mood.end.chapter:
        # Cross-chapter moods shouldn't exist post-parse, but degrade safely.
        return max(1, mood.end.section - mood.start.section + 1)
    return mood.end.section - mood.start.section + 1


def _find_covering_mood(
    position: SectionRef, moods: list[Mood],
) -> Optional[str]:
    """Return the mood_id whose span covers *position*, or ``None``."""
    for mood in moods:
        if mood.start.chapter != position.chapter:
            continue
        if mood.start.section <= position.section <= mood.end.section:
            return mood.mood_id
    return None
