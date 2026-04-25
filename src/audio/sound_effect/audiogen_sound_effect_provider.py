"""AudioGen sound effect provider — uses Meta AudioCraft AudioGen for local inference.

Generates sound effects from text descriptions using Meta's AudioGen model.
Completely free — no API keys required, runs on local GPU/CPU.

Model: ``facebook/audiogen-medium`` (HuggingFace).

Requires ``audiocraft`` and ``torchaudio`` at runtime.  These are NOT declared
as project dependencies because they are heavy; install them manually::

    pip install audiocraft torchaudio
"""
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

import structlog

from src.audio.sound_effect.sound_effect_provider import SoundEffectProvider

logger = structlog.get_logger(__name__)

_DEFAULT_MODEL_ID = "facebook/audiogen-medium"

# Optional heavy dependency — loaded on first use
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
    """Meta AudioGen local sound effect provider.

    Loads the AudioGen model on first ``generate`` call (lazy init) and
    caches it for the lifetime of the provider instance.

    This provider is completely free — it runs inference locally and does
    not call any external API.
    """

    @property
    def name(self) -> str:
        return "audiogen"

    def __init__(
        self,
        model_id: str = _DEFAULT_MODEL_ID,
        device: str = "cpu",
    ) -> None:
        """Initialize AudioGen sound effect provider.

        Args:
            model_id: HuggingFace model identifier or local path.
            device: PyTorch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
        """
        self._model_id = model_id
        self._device = device
        # Lazy-loaded on first use
        self._model: Any = None

    def provide(self, segment: Any, book_id: str) -> float:
        """Not yet implemented for AudioGen provider."""
        raise NotImplementedError("AudioGenSoundEffectProvider.provide() not yet implemented")

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
        output_path: Path,
        duration_seconds: float = 2.0,
    ) -> Optional[Path]:
        """Generate a sound effect from description using AudioGen (internal).

        Args:
            description: Natural-language description of the sound effect.
            output_path: Where to save the generated ``.wav`` file.
            duration_seconds: Desired duration of the effect in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        ta = _import_torchaudio()
        self._ensure_loaded()

        logger.info(
            "audiogen_sfx_generate_start",
            description=description,
            duration_seconds=duration_seconds,
            output_path=str(output_path),
        )

        try:
            self._model.set_generation_params(duration=duration_seconds)
            wav = self._model.generate([description])

            output_path.parent.mkdir(parents=True, exist_ok=True)
            ta.save(str(output_path), wav[0].cpu(), self._model.sample_rate)

            logger.info(
                "audiogen_sfx_generate_done",
                output_path=str(output_path),
            )
            return output_path

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "audiogen_sfx_generate_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None
