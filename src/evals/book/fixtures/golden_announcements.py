"""Golden-labeled test cases for evaluating the AnnouncementFormatter.

Each case pairs raw metadata (as it comes from Project Gutenberg HTML) with
human-annotated expectations for what the LLM-formatted output should contain.

Cases are ordered by difficulty: clean metadata → messy metadata → edge cases.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenBookTitle:
    """A book title formatting test case with human-annotated expectations."""

    name: str
    raw_title: str
    raw_author: str | None
    # Substrings that MUST appear in the formatted output (recall checks)
    expected_substrings: list[str] = field(default_factory=list)
    # Substrings that must NOT appear in the formatted output (precision checks)
    forbidden_substrings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GoldenChapterAnnouncement:
    """A chapter announcement formatting test case."""

    name: str
    chapter_number: int
    chapter_title: str
    # Substrings that MUST appear in the formatted output
    expected_substrings: list[str] = field(default_factory=list)
    # Substrings that must NOT appear in the formatted output
    forbidden_substrings: list[str] = field(default_factory=list)


# ── Book title cases ────────────────────────────────────────────────────


TITLE_CLEAN = GoldenBookTitle(
    name="clean_metadata",
    raw_title="Pride and Prejudice",
    raw_author="Jane Austen",
    expected_substrings=["Pride and Prejudice", "Jane Austen"],
    forbidden_substrings=[],
)

TITLE_INVERTED_WITH_DATES = GoldenBookTitle(
    name="inverted_author_with_dates",
    raw_title="Pride and Prejudice",
    raw_author="Austen, Jane, 1775-1817",
    expected_substrings=["Pride and Prejudice", "Jane Austen"],
    forbidden_substrings=["1775", "1817", "Austen, Jane"],
)

TITLE_MESSY_AUTHOR = GoldenBookTitle(
    name="messy_gutenberg_author",
    raw_title="Moby Dick; Or, The Whale",
    raw_author="Melville, Herman, 1819-1891",
    expected_substrings=["Moby Dick", "Herman Melville"],
    forbidden_substrings=["1819", "1891", "Melville, Herman"],
)

TITLE_NO_AUTHOR = GoldenBookTitle(
    name="no_author",
    raw_title="Beowulf",
    raw_author=None,
    expected_substrings=["Beowulf"],
    forbidden_substrings=[],
)

ALL_BOOK_TITLES = [TITLE_CLEAN, TITLE_INVERTED_WITH_DATES, TITLE_MESSY_AUTHOR, TITLE_NO_AUTHOR]


# ── Chapter announcement cases ─────────────────────────────────────────


CHAPTER_WITH_TITLE = GoldenChapterAnnouncement(
    name="chapter_with_title",
    chapter_number=1,
    chapter_title="The Beginning",
    expected_substrings=["One", "Beginning"],
    forbidden_substrings=[],
)

CHAPTER_NUMERIC_ONLY = GoldenChapterAnnouncement(
    name="chapter_numeric_only",
    chapter_number=5,
    chapter_title="Chapter 5",
    expected_substrings=["Five"],
    forbidden_substrings=[],
)

CHAPTER_LONG_TITLE = GoldenChapterAnnouncement(
    name="chapter_long_title",
    chapter_number=12,
    chapter_title="In Which Several Characters Are Introduced",
    expected_substrings=["Twelve", "Characters"],
    forbidden_substrings=[],
)

ALL_CHAPTER_ANNOUNCEMENTS = [CHAPTER_WITH_TITLE, CHAPTER_NUMERIC_ONLY, CHAPTER_LONG_TITLE]
