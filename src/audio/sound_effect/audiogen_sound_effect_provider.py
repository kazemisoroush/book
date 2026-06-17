"""AudioGen sound effect provider, uses Meta AudioCraft AudioGen for local inference.

Generates sound effects from text descriptions using Meta's AudioGen model.
Completely free, no API keys required, runs on local GPU/CPU.

Model: ``facebook/audiogen-medium`` (HuggingFace).

Requires ``audiocraft`` and ``torchaudio`` at runtime.  These are NOT declared
as project dependencies because they are heavy; install them manually::

    pip install audiocraft torchaudio
"""
from types import ModuleType
from typing import Any, Optional

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider
from src.domain.beat import Beat
from src.storage.audio_store import AudioStore

logger = structlog.get_logger(__name__)

_DEFAULT_MODEL_ID = "facebook/audiogen-medium"

torchaudio: Optional[ModuleType] = None


def _import_torchaudio() -> ModuleType:
    """Import torchaudio, raising a helpful error if not installed."""
    global torchaudio
    if torchaudio is None:
        try:
            import torchaudio as _ta  # type: ignore[import-not-found]
            torchaudio = _ta
        except ImportError as exc:
            raise ImportError(
                "AudioGen requires the 'torchaudio' package. "
                "Install with: pip install torchaudio"
            ) from exc
    return torchaudio


class AudioGenSoundEffectProvider(SoundEffectProvider):
    """Meta AudioGen local sound effect provider."""

    @property
    def name(self) -> str:
        return "audiogen"

    def __init__(
        self,
        audio_store: AudioStore,
        model_id: str = _DEFAULT_MODEL_ID,
        device: str = "cpu",
    ) -> None:
        self._audio_store = audio_store
        self._model_id = model_id
        self._device = device
        self._model: Any = None
        self._beat_counter = 0

    def provide(self, beat: Beat, book_id: str) -> None:
        self._beat_counter += 1
        key = self._audio_store.sfx_beat_key(
            book_id, self.name, self._beat_counter, extension="wav",
        )
        self._generate(beat.text, key)

    def _ensure_loaded(self) -> None:
        """Load the AudioGen model on first use."""
        if self._model is not None:
            return

        try:
            from audiocraft.models import AudioGen  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AudioGen requires the 'audiocraft' package. "
                "Install with: pip install audiocraft"
            ) from exc

        logger.info(
            "audiogen_sfx_loading_model",
            model_id=self._model_id,
            device=self._device,
        )

        self._model = AudioGen.get_pretrained(self._model_id)
        self._model.to(self._device)

        logger.info("audiogen_sfx_model_loaded", device=self._device)

    def _generate(
        self,
        description: str,
        key: str,
        duration_seconds: float = 2.0,
    ) -> bool:
        """Generate a sound effect, skipping the call if the key already exists."""
        if self._audio_store.exists(key):
            logger.debug("audiogen_sfx_cache_hit", key=key)
            return True

        ta = _import_torchaudio()
        self._ensure_loaded()

        logger.info(
            "audiogen_sfx_generate_start",
            description=description,
            duration_seconds=duration_seconds,
            key=key,
        )

        try:
            self._model.set_generation_params(duration=duration_seconds)
            wav = self._model.generate([description])

            with self._audio_store.local_path(key, "w") as output_path:
                ta.save(str(output_path), wav[0].cpu(), self._model.sample_rate)

            logger.info("audiogen_sfx_generate_done", key=key)
            return True

        except Exception as exc:
            logger.warning(
                "audiogen_sfx_generate_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return False
