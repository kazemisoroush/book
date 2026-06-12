"""Chains AudioTrimmers over beat MP3s and tears down what it produced."""
from pathlib import Path
from typing import Optional

from src.audio.tts.audio_trimmer.audio_trimmer import AudioTrimmer
from src.domain.beat import Beat

_FINAL_SUFFIX = ".trimmed.mp3"
_STEP_SUFFIX = ".trim_step_{i}.mp3"
_STEP_GLOB = "{stem}.trim_step_*.mp3"


class AudioTrimmerPipeline:
    """Owns the trim-chain naming convention and the trimmed-sibling lifecycle."""

    def __init__(self, trimmers: Optional[list[AudioTrimmer]] = None) -> None:
        self._trimmers = trimmers or []

    def apply(
        self, beat_pairs: list[tuple[Beat, Path]],
    ) -> list[tuple[Beat, Path]]:
        """Run every trimmer over every beat; return pairs at the final output."""
        if not self._trimmers:
            return beat_pairs
        last_index = len(self._trimmers) - 1
        result: list[tuple[Beat, Path]] = []
        for beat, raw in beat_pairs:
            current = raw
            for i, trimmer in enumerate(self._trimmers):
                suffix = _FINAL_SUFFIX if i == last_index else _STEP_SUFFIX.format(i=i)
                current = trimmer.trim(current, raw.with_suffix(suffix))
            result.append((beat, current))
        return result

    def cleanup(
        self,
        applied: list[tuple[Beat, Path]],
        original: list[tuple[Beat, Path]],
    ) -> None:
        """Delete every trimmed sibling and chain intermediate produced by apply()."""
        if applied is original:
            return
        for (_, final_path), (_, raw_path) in zip(applied, original):
            final_path.unlink(missing_ok=True)
            for intermediate in raw_path.parent.glob(
                _STEP_GLOB.format(stem=raw_path.stem),
            ):
                intermediate.unlink(missing_ok=True)
