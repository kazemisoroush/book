"""Tests for :class:`MoodTracker` (US-034)."""
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    MoodRegistry,
    Section,
    SectionRef,
)
from src.parsers.ai_section_parser import MoodAction
from src.workflows.mood_tracker import MoodTracker


def _empty_book(chapters: list[Chapter]) -> Book:
    """Helper to build a minimal Book with the given chapters."""
    return Book(
        metadata=BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        ),
        content=BookContent(chapters=chapters),
    )


class TestMoodTrackerOpen:
    """apply('open') registers a new mood and tracks it as open."""

    def test_open_action_creates_registry_entry(self) -> None:
        """An ``open`` action synthesises a mood_id and registers the mood."""
        # Arrange
        registry = MoodRegistry()
        tracker = MoodTracker(registry)

        # Act
        tracker.apply(
            MoodAction(kind="open", description="dry social commentary"),
            SectionRef(chapter=1, section=3),
        )

        # Assert
        moods = registry.all()
        assert len(moods) == 1
        assert moods[0].description == "dry social commentary"
        assert moods[0].start == SectionRef(chapter=1, section=3)
        assert tracker.open_mood_id == moods[0].mood_id


class TestMoodTrackerContinue:
    """apply('continue') extends an existing mood's end."""

    def test_continue_extends_mood_end(self) -> None:
        """A ``continue`` advances the mood's end to the current section."""
        # Arrange
        registry = MoodRegistry()
        tracker = MoodTracker(registry)
        tracker.apply(
            MoodAction(kind="open", description="dread"),
            SectionRef(chapter=1, section=1),
        )
        mood_id = tracker.open_mood_id
        assert mood_id is not None

        # Act
        tracker.apply(
            MoodAction(kind="continue", mood_id=mood_id),
            SectionRef(chapter=1, section=7),
        )

        # Assert
        mood = registry.get(mood_id)
        assert mood is not None
        assert mood.end == SectionRef(chapter=1, section=7)


class TestMoodTrackerCloseAndOpen:
    """apply('close_and_open') closes the current mood and starts a new one."""

    def test_close_and_open_creates_second_mood(self) -> None:
        """A shift produces two moods with no section overlap."""
        # Arrange
        registry = MoodRegistry()
        tracker = MoodTracker(registry)
        tracker.apply(
            MoodAction(kind="open", description="banter"),
            SectionRef(chapter=1, section=1),
        )
        first_id = tracker.open_mood_id
        assert first_id is not None

        # Act
        tracker.apply(
            MoodAction(
                kind="close_and_open",
                close_mood_id=first_id,
                description="sarcastic resignation",
            ),
            SectionRef(chapter=1, section=5),
        )

        # Assert
        first = registry.get(first_id)
        assert first is not None
        assert first.end == SectionRef(chapter=1, section=4)
        second_id = tracker.open_mood_id
        assert second_id is not None and second_id != first_id
        second = registry.get(second_id)
        assert second is not None
        assert second.start == SectionRef(chapter=1, section=5)


class TestMoodTrackerCloseChapter:
    """close_chapter() closes any open mood at end-of-chapter."""

    def test_close_chapter_extends_end_to_last_section(self) -> None:
        """Open mood is closed at the last section of the chapter."""
        # Arrange
        registry = MoodRegistry()
        tracker = MoodTracker(registry)
        tracker.apply(
            MoodAction(kind="open", description="banter"),
            SectionRef(chapter=1, section=1),
        )
        mood_id = tracker.open_mood_id
        assert mood_id is not None

        # Act
        tracker.close_chapter(SectionRef(chapter=1, section=38))

        # Assert
        mood = registry.get(mood_id)
        assert mood is not None
        assert mood.end == SectionRef(chapter=1, section=38)
        assert tracker.open_mood_id is None


class TestMoodTrackerMergeShortMoods:
    """finalize() merges moods shorter than two sections into neighbours."""

    def test_short_mood_merges_into_previous_neighbour(self) -> None:
        """A one-section mood between two longer ones is absorbed by the previous."""
        # Arrange
        registry = MoodRegistry()
        tracker = MoodTracker(registry)
        # Open a long first mood (sections 1–4).
        tracker.apply(
            MoodAction(kind="open", description="banter"),
            SectionRef(chapter=1, section=1),
        )
        tracker.apply(
            MoodAction(kind="continue", mood_id=tracker.open_mood_id),
            SectionRef(chapter=1, section=4),
        )
        first_id = tracker.open_mood_id
        # Short mood (section 5 only).
        tracker.apply(
            MoodAction(
                kind="close_and_open",
                close_mood_id=first_id,
                description="blink of melancholy",
            ),
            SectionRef(chapter=1, section=5),
        )
        # Third mood from 6 onwards, extending to 10.
        tracker.apply(
            MoodAction(
                kind="close_and_open",
                close_mood_id=tracker.open_mood_id,
                description="calm afternoon",
            ),
            SectionRef(chapter=1, section=6),
        )
        tracker.apply(
            MoodAction(kind="continue", mood_id=tracker.open_mood_id),
            SectionRef(chapter=1, section=10),
        )
        tracker.close_chapter(SectionRef(chapter=1, section=10))

        book = _empty_book([Chapter(
            number=1, title="C1",
            sections=[Section(text=f"s{i}") for i in range(1, 11)],
        )])

        # Act
        tracker.finalize(book)

        # Assert — short mood is gone, previous mood extends over section 5.
        assert first_id is not None
        ids = {m.mood_id for m in registry.all()}
        assert len(ids) == 2
        first = registry.get(first_id)
        assert first is not None
        assert first.end.section == 5


class TestMoodTrackerBackfill:
    """finalize() stamps mood_id on every section."""

    def test_backfill_populates_section_mood_ids(self) -> None:
        """Sections within a mood's span get the mood_id after finalize."""
        # Arrange
        registry = MoodRegistry()
        tracker = MoodTracker(registry)
        tracker.apply(
            MoodAction(kind="open", description="banter"),
            SectionRef(chapter=1, section=1),
        )
        tracker.apply(
            MoodAction(kind="continue", mood_id=tracker.open_mood_id),
            SectionRef(chapter=1, section=3),
        )
        tracker.close_chapter(SectionRef(chapter=1, section=3))

        book = _empty_book([Chapter(
            number=1, title="C1",
            sections=[Section(text=f"s{i}") for i in range(1, 4)],
        )])

        # Act
        tracker.finalize(book)

        # Assert — every section carries the mood id.
        mood_id = registry.all()[0].mood_id
        assigned = [s.mood_id for s in book.content.chapters[0].sections]
        assert assigned == [mood_id, mood_id, mood_id]


class TestMoodTrackerNoneAction:
    """apply(None) extends the currently-open mood if one exists."""

    def test_none_action_extends_open_mood(self) -> None:
        """A missing action still advances the mood's end."""
        # Arrange
        registry = MoodRegistry()
        tracker = MoodTracker(registry)
        tracker.apply(
            MoodAction(kind="open", description="banter"),
            SectionRef(chapter=1, section=1),
        )
        mood_id = tracker.open_mood_id
        assert mood_id is not None

        # Act
        tracker.apply(None, SectionRef(chapter=1, section=4))

        # Assert
        mood = registry.get(mood_id)
        assert mood is not None
        assert mood.end == SectionRef(chapter=1, section=4)
