"""MusicGen music provider — uses Meta AudioCraft MusicGen for local inference.

Generates background music from mood/style prompts using Meta's MusicGen model.
Completely free — no API keys required, runs on local GPU/CPU.

Model: ``facebook/musicgen-small`` (HuggingFace).

Requires ``audiocraft`` and ``torchaudio`` at runtime.  These are NOT declared
as project dependencies because they are heavy; install them manually::

    pip install audiocraft torchaudio
"""
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

import structlog

from src.audio.music.music_provider import MusicProvider

logger = structlog.get_logger(__name__)

_DEFAULT_MODEL_ID = "facebook/musicgen-small"

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
                "MusicGen requires the 'torchaudio' package. "
                "Install with: pip install torchaudio"
            ) from exc
    return torchaudio


class MusicGenMusicProvider(MusicProvider):
    """Meta MusicGen local music provider.

    Loads the MusicGen model on first ``generate`` call (lazy init) and
    caches it for the lifetime of the provider instance.

    This provider is completely free — it runs inference locally and does
    not call any external API.
    """

    def __init__(
        self,
        model_id: str = _DEFAULT_MODEL_ID,
        device: str = "cpu",
    ) -> None:
        """Initialize MusicGen music provider.

        Args:
            model_id: HuggingFace model identifier or local path.
            device: PyTorch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
        """
        self._model_id = model_id
        self._device = device
        # Lazy-loaded on first use
        self._model: Any = None

    def _ensure_loaded(self) -> None:
        """Load the MusicGen model on first use."""
        if self._model is not None:
            return

        try:
            from audiocraft.models import MusicGen  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "MusicGen requires the 'audiocraft' package. "
                "Install with: pip install audiocraft"
            ) from exc

        logger.info(
            "musicgen_loading_model",
            model_id=self._model_id,
            device=self._device,
        )

        self._model = MusicGen.get_pretrained(self._model_id)
        self._model.to(self._device)

        logger.info("musicgen_model_loaded", device=self._device)

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate music from mood/style prompt using MusicGen.

        Args:
            prompt: Natural-language description of the desired music mood/style.
            output_path: Where to save the generated ``.wav`` file.
            duration_seconds: Desired duration of the music track in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        ta = _import_torchaudio()
        self._ensure_loaded()

        logger.info(
            "musicgen_generate_start",
            prompt=prompt,
            duration_seconds=duration_seconds,
            output_path=str(output_path),
        )

        try:
            self._model.set_generation_params(duration=duration_seconds)
            wav = self._model.generate([prompt])

            output_path.parent.mkdir(parents=True, exist_ok=True)
            ta.save(str(output_path), wav[0].cpu(), self._model.sample_rate)

            logger.info(
                "musicgen_generate_done",
                output_path=str(output_path),
            )
            return output_path

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "musicgen_generate_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None
