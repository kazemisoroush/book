"""Chains AudioTrimmers over beat MP3s and tears down what it produced."""
from typing import Optional

from src.audio.tts.audio_trimmer.audio_trimmer import AudioTrimmer
from src.domain.beat import Beat
from src.storage.audio_store import AudioStore

_FINAL_SUFFIX = ".trimmed.mp3"
_STEP_SUFFIX_TEMPLATE = ".trim_step_{i}.mp3"
_STEP_PREFIX = ".trim_step_"


class AudioTrimmerPipeline:
    """Owns the trim-chain naming convention and the trimmed-sibling lifecycle."""

    def __init__(self, trimmers: Optional[list[AudioTrimmer]] = None) -> None:
        self._trimmers = trimmers or []

    def apply(
        self,
        beat_pairs: list[tuple[Beat, str]],
        audio_store: AudioStore,
    ) -> list[tuple[Beat, str]]:
        """Run every trimmer over every beat; return pairs at the final output key."""
        if not self._trimmers:
            return beat_pairs
        last_index = len(self._trimmers) - 1
        result: list[tuple[Beat, str]] = []
        for beat, raw_key in beat_pairs:
            current_key = raw_key
            for i, trimmer in enumerate(self._trimmers):
                suffix = (
                    _FINAL_SUFFIX
                    if i == last_index
                    else _STEP_SUFFIX_TEMPLATE.format(i=i)
                )
                next_key = _swap_suffix(raw_key, suffix)
                with audio_store.local_path(current_key, "r") as in_path:
                    with audio_store.local_path(next_key, "w") as out_path:
                        trimmer.trim(in_path, out_path)
                current_key = next_key
            result.append((beat, current_key))
        return result

    def cleanup(
        self,
        applied: list[tuple[Beat, str]],
        original: list[tuple[Beat, str]],
        audio_store: AudioStore,
    ) -> None:
        """Delete every trimmed sibling and chain intermediate produced by apply()."""
        if applied is original:
            return
        for (_, final_key), (_, raw_key) in zip(applied, original):
            audio_store.delete(final_key, missing_ok=True)
            for intermediate_key in _intermediate_keys(raw_key, audio_store):
                audio_store.delete(intermediate_key, missing_ok=True)


def _swap_suffix(raw_key: str, new_suffix: str) -> str:
    """Replace the .mp3 suffix of *raw_key* with *new_suffix*."""
    return raw_key.removesuffix(".mp3") + new_suffix


def _intermediate_keys(raw_key: str, audio_store: AudioStore) -> list[str]:
    """Find every chain-intermediate key produced for *raw_key* by apply()."""
    stem = raw_key.removesuffix(".mp3")
    prefix = stem + _STEP_PREFIX
    directory, _, _ = raw_key.rpartition("/")
    if directory:
        candidates = audio_store.list_prefix(directory)
    else:
        candidates = audio_store.list_prefix("")
    return [key for key in candidates if key.startswith(prefix) and key.endswith(".mp3")]
