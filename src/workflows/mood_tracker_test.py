"""Tests for :class:`MoodTracker` (US-034)."""
from src.domain.models import (
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Mood,
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


# ── TD-028: state seeding from registry on cache-resume ────────────────────


class TestMoodTrackerConstructorSeedsFromRegistry:
    """Constructing a tracker with a populated registry rebuilds runtime state."""

    def test_first_chapter_to_parse_past_registered_mood_leaves_tracker_closed(
        self,
    ) -> None:
        """Ch1 mood already registered and we're about to parse ch2: no open mood.

        The workflow's prior end-of-ch1 close_chapter() has already run, so the
        tracker should start with ``open_mood_id = None`` even though the mood
        is in the registry.
        """
        # Arrange — registry with a single ch1 mood ending at ch1.38
        registry = MoodRegistry()
        registry.upsert(Mood(
            mood_id="ch1_mood_1",
            description="dry social commentary",
            start=SectionRef(chapter=1, section=1),
            end=SectionRef(chapter=1, section=38),
        ))

        # Act — resume at chapter 2
        tracker = MoodTracker(registry, first_chapter_to_parse=2)

        # Assert — tracker treats the registered mood as already closed
        assert tracker.open_mood_id is None

    def test_chapter_mood_count_reflects_registered_moods(self) -> None:
        """After seeding, ``_open_new_mood`` uses the correct per-chapter counter.

        Two ch1 moods already registered: the next ch1 mood opened via apply
        must get id ``ch1_mood_3``, not ``ch1_mood_1`` (collision).
        """
        # Arrange
        registry = MoodRegistry()
        registry.upsert(Mood(
            mood_id="ch1_mood_1",
            description="A",
            start=SectionRef(chapter=1, section=1),
            end=SectionRef(chapter=1, section=5),
        ))
        registry.upsert(Mood(
            mood_id="ch1_mood_2",
            description="B",
            start=SectionRef(chapter=1, section=6),
            end=SectionRef(chapter=1, section=38),
        ))
        tracker = MoodTracker(registry, first_chapter_to_parse=2)

        # Act — open a new mood in ch2
        tracker.apply(
            MoodAction(kind="open", description="C"),
            SectionRef(chapter=2, section=1),
        )

        # Assert — per-chapter counters are chapter-scoped, ch2 mood starts at 1
        assert tracker.open_mood_id == "ch2_mood_1"

    def test_candidate_open_mood_kept_open_when_first_chapter_matches(self) -> None:
        """If the registered mood's end.chapter >= first_chapter_to_parse, open.

        This simulates an in-progress mid-chapter resume: the last registered
        mood ends inside the chapter we're about to parse, so it is still
        considered open.
        """
        # Arrange — mood ends earlier than the last section in its chapter
        registry = MoodRegistry()
        registry.upsert(Mood(
            mood_id="ch1_mood_1",
            description="dry social commentary",
            start=SectionRef(chapter=1, section=1),
            end=SectionRef(chapter=1, section=5),
        ))

        # Act — resume at the same chapter
        tracker = MoodTracker(registry, first_chapter_to_parse=1)

        # Assert — tracker treats the registered mood as still open
        assert tracker.open_mood_id == "ch1_mood_1"


class TestMoodTrackerAutoClosesOnChapterTransition:
    """apply() on a position in a new chapter auto-closes and opens a continuation."""

    def test_continue_referencing_cached_mood_from_closed_chapter_opens_new_mood(
        self,
    ) -> None:
        """A ``continue`` on ch2 referencing a cached ch1 mood must not extend it.

        This is the cache-resume scenario: the tracker seeded from a registry
        whose last mood ends at the close of ch1, with first_chapter_to_parse=2,
        starts with ``_open_mood_id = None``. The LLM, seeing the cached mood
        under "Known moods", emits ``continue ch1_mood_1`` on ch2 section 1.
        The tracker must refuse to extend the ch1 mood into ch2 and instead
        open a fresh ch2 mood that continues from it.
        """
        # Arrange — resume scenario: ch1 fully cached, no open mood seeded.
        registry = MoodRegistry()
        registry.upsert(Mood(
            mood_id="ch1_mood_1",
            description="dry social commentary",
            start=SectionRef(chapter=1, section=1),
            end=SectionRef(chapter=1, section=38),
        ))
        tracker = MoodTracker(registry, first_chapter_to_parse=2)
        assert tracker.open_mood_id is None

        # Act — LLM emits continue on ch2 section 1
        tracker.apply(
            MoodAction(kind="continue", mood_id="ch1_mood_1"),
            SectionRef(chapter=2, section=1),
        )

        # Assert — no cross-chapter mood; new ch2 mood continues from ch1_mood_1.
        ch1 = registry.get("ch1_mood_1")
        assert ch1 is not None
        assert ch1.start.chapter == 1 and ch1.end.chapter == 1
        new_id = tracker.open_mood_id
        assert new_id is not None and new_id != "ch1_mood_1"
        new_mood = registry.get(new_id)
        assert new_mood is not None
        assert new_mood.start.chapter == 2 and new_mood.end.chapter == 2
        assert new_mood.continues_from == "ch1_mood_1"

    def test_continue_across_chapter_boundary_opens_new_mood_with_continues_from(
        self,
    ) -> None:
        """A ``continue`` in ch2 while open mood is in ch1 closes old, opens new.

        The new mood is chapter-local (start.chapter == end.chapter), carries
        the old mood's description, and sets ``continues_from`` to the closed
        mood's id. The old mood is closed at the last seen position in its
        own chapter.
        """
        # Arrange — an open ch1 mood with ``_last_position_per_chapter[1]`` at (1, 38)
        registry = MoodRegistry()
        registry.upsert(Mood(
            mood_id="ch1_mood_1",
            description="dry social commentary",
            start=SectionRef(chapter=1, section=1),
            end=SectionRef(chapter=1, section=38),
        ))
        tracker = MoodTracker(registry, first_chapter_to_parse=1)
        assert tracker.open_mood_id == "ch1_mood_1"

        # Act — the parser emits ``continue`` on ch2 section 1
        tracker.apply(
            MoodAction(kind="continue", mood_id="ch1_mood_1"),
            SectionRef(chapter=2, section=1),
        )

        # Assert — old mood stays chapter-local; new mood is chapter-local,
        # carries the description, and cross-links via continues_from.
        old = registry.get("ch1_mood_1")
        assert old is not None
        assert old.start.chapter == 1 and old.end.chapter == 1
        new_id = tracker.open_mood_id
        assert new_id is not None and new_id != "ch1_mood_1"
        new_mood = registry.get(new_id)
        assert new_mood is not None
        assert new_mood.start.chapter == 2
        assert new_mood.end.chapter == 2
        assert new_mood.description == "dry social commentary"
        assert new_mood.continues_from == "ch1_mood_1"
