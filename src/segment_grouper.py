"""Groups segments intelligently for more natural audio generation."""
from typing import List
from src.domain.models import Segment, SegmentType


class SegmentGrouper:
    """Groups segments for more natural audio output."""

    def group_segments(self, segments: List[Segment]) -> List[Segment]:
        """
        Group consecutive segments from the same speaker.

        This combines:
        - Consecutive dialogue from the same character
        - Consecutive narration segments
        - Removes very short attribution fragments

        Args:
            segments: List of segments to group

        Returns:
            List of grouped segments
        """
        if not segments:
            return []

        grouped = []
        current_group = None

        for segment in segments:
            # Check if we should merge with current group
            if current_group and self._should_merge(current_group, segment):
                # Merge the text
                current_group.text = self._merge_text(current_group.text, segment.text)
            else:
                # Start a new group
                if current_group:
                    grouped.append(current_group)
                current_group = Segment(
                    text=segment.text,
                    segment_type=segment.segment_type,
                    speaker=segment.speaker
                )

        # Don't forget the last group
        if current_group:
            grouped.append(current_group)

        # Filter out very short narration fragments that are just attribution
        grouped = self._filter_short_fragments(grouped)

        return grouped

    def _should_merge(self, seg1: Segment, seg2: Segment) -> bool:
        """Check if two segments should be merged."""
        # Must be same type
        if seg1.segment_type != seg2.segment_type:
            return False

        # For dialogue, must be same speaker
        if seg1.is_dialogue():
            return seg1.speaker and seg1.speaker.lower() == (seg2.speaker.lower() if seg2.speaker else None)

        # For narration, merge if the first segment is very short (likely attribution)
        # or if both are reasonably sized
        if seg1.is_narration():
            # Merge short fragments with next narration
            if len(seg1.text.strip()) < 50:
                return True
            # Also merge if second segment is continuation (doesn't start with capital)
            seg2_text = seg2.text.strip()
            if seg2_text and not seg2_text[0].isupper():
                return True

        return False

    def _merge_text(self, text1: str, text2: str) -> str:
        """Merge two text segments intelligently."""
        text1 = text1.strip()
        text2 = text2.strip()

        # If first text ends with comma/dash or second starts lowercase, just concatenate with space
        if text1 and text2:
            if text1[-1] in ',-' or (text2[0].islower() and text1[-1] not in '.!?'):
                return f"{text1} {text2}"

        # Otherwise, ensure proper spacing
        if text1 and text2:
            return f"{text1} {text2}"

        return text1 or text2

    def _filter_short_fragments(self, segments: List[Segment]) -> List[Segment]:
        """Filter out very short narration fragments that are just attribution."""
        filtered = []

        for i, segment in enumerate(segments):
            # Keep dialogue always
            if segment.is_dialogue():
                filtered.append(segment)
                continue

            # For narration, filter out very short ones that look like attribution
            text = segment.text.strip()

            # Keep if it's substantial
            if len(text) > 30:
                filtered.append(segment)
                continue

            # Keep if it has substantive content (not just "said X" type phrases)
            attribution_words = {'said', 'replied', 'asked', 'cried', 'exclaimed',
                               'whispered', 'shouted', 'answered', 'returned', 'continued',
                               'impatiently', 'coldly', 'warmly', 'softly', 'loudly'}

            words = text.lower().split()
            if not any(word in attribution_words for word in words):
                filtered.append(segment)
            elif len(text) > 15:  # Keep longer attribution as it might have context
                filtered.append(segment)

        return filtered
