"""Chains AudioTrimmers over beat MP3s and tears down what it produced."""
from typing import Optional

from src.audio.tts.audio_trimmer.audio_trimmer import AudioTrimmer
from src.domain.beat import Beat
from src.storage.audio_store import AudioStore
from src.storage.objects import TrimStepRef, TTSBeatRef


class AudioTrimmerPipeline:
    """Owns the trim-chain naming convention and the trimmed-sibling lifecycle."""

    def __init__(self, trimmers: Optional[list[AudioTrimmer]] = None) -> None:
        self._trimmers = trimmers or []

    def apply(
        self,
        beat_refs: list[tuple[Beat, TTSBeatRef]],
        audio_store: AudioStore,
    ) -> list[tuple[Beat, TTSBeatRef]]:
        """Run every trimmer over every beat; return pairs whose ref points at the trimmed sibling."""
        if not self._trimmers:
            return beat_refs
        last_index = len(self._trimmers) - 1
        result: list[tuple[Beat, TTSBeatRef]] = []
        for beat, beat_ref in beat_refs:
            self._trim_one(beat_ref, last_index, audio_store)
            result.append((beat, beat_ref))
        return result

    def cleanup(
        self,
        applied: list[tuple[Beat, TTSBeatRef]],
        original: list[tuple[Beat, TTSBeatRef]],
        audio_store: AudioStore,
    ) -> None:
        """Delete every chain intermediate and the final trimmed sibling for each beat."""
        if applied is original:
            return
        for _, beat_ref in original:
            audio_store.delete_trim_artifacts(beat_ref)

    def has_trimmers(self) -> bool:
        return bool(self._trimmers)

    def _trim_one(
        self,
        beat_ref: TTSBeatRef,
        last_index: int,
        audio_store: AudioStore,
    ) -> None:
        prev: TTSBeatRef | TrimStepRef = beat_ref
        for i, trimmer in enumerate(self._trimmers):
            target = TrimStepRef(
                beat=beat_ref, step="final" if i == last_index else i,
            )
            with _open_for_reading(prev, audio_store) as in_path:
                with audio_store.open_trim_step(target, "w") as out_path:
                    trimmer.trim(in_path, out_path)
            prev = target


def _open_for_reading(
    ref: TTSBeatRef | TrimStepRef, audio_store: AudioStore,
):
    if isinstance(ref, TTSBeatRef):
        return audio_store.open_tts_beat(ref)
    return audio_store.open_trim_step(ref, "r")
