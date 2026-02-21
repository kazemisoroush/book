"""Chapter announcement functionality."""
from dataclasses import replace
from src.domain.models import Chapter, Segment, SegmentType


class ChapterAnnouncer:
    """Adds chapter/preface announcements to the beginning of chapters."""

    def add_announcement(self, chapter: Chapter) -> Chapter:
        """
        Add a narration segment at the beginning that announces the chapter title.

        Args:
            chapter: The chapter to add announcement to

        Returns:
            A new Chapter with the announcement prepended
        """
        announcement_segment = Segment(
            text=chapter.title,
            segment_type=SegmentType.NARRATION,
            speaker=None
        )

        new_segments = [announcement_segment] + list(chapter.segments)

        return replace(chapter, segments=new_segments)
