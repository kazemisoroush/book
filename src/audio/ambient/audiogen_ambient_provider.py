"""AudioGen ambient provider — uses Meta AudioCraft AudioGen for local inference.

Generates ambient audio from text prompts using Meta's AudioGen model.
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

from src.audio.ambient.ambient_provider import AmbientProvider
from src.domain.models import Scene

logger = structlog.get_logger(__name__)

_DEFAULT_MODEL_ID = "facebook/audiogen-medium"


def _wav_duration_seconds(path: Path) -> float:
    """Return WAV duration in seconds via the standard library ``wave`` module."""
    import wave
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
    return frames / float(rate) if rate else 0.0

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


class AudioGenAmbientProvider(AmbientProvider):
    """Meta AudioGen local ambient audio provider.

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
        books_dir: Path,
        model_id: str = _DEFAULT_MODEL_ID,
        device: str = "cpu",
    ) -> None:
        """Initialize AudioGen ambient provider.

        Args:
            books_dir: Base directory for book output.
            model_id: HuggingFace model identifier or local path.
            device: PyTorch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
        """
        self._books_dir = books_dir
        self._model_id = model_id
        self._device = device
        # Lazy-loaded on first use
        self._model: Any = None

    def provide(self, scene: Scene, book_id: str) -> float:
        if scene.ambient_prompt is None:
            raise ValueError(
                f"Scene {scene.scene_id!r} has no ambient_prompt set"
            )
        output_path = (
            self._books_dir / book_id / "audio" / "ambient" / self.name
            / f"{scene.scene_id}.wav"
        )
        result = self._generate(scene.ambient_prompt, output_path)
        if result is None:
            return 0.0
        return _wav_duration_seconds(result)

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
            "audiogen_ambient_loading_model",
            model_id=self._model_id,
            device=self._device,
        )

        self._model = AudioGen.get_pretrained(self._model_id)
        self._model.to(self._device)

        logger.info("audiogen_ambient_model_loaded", device=self._device)

    def _generate(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: float = 60.0,
    ) -> Optional[Path]:
        """Generate ambient audio, skipping the call if the file already exists.

        Args:
            prompt: Natural-language description of the ambient environment.
            output_path: Where to save the generated ``.wav`` file. Existence
                acts as the cache.
            duration_seconds: Desired duration of the ambient clip in seconds.

        Returns:
            Path to generated audio file, or None on failure.
        """
        if output_path.exists():
            logger.debug(
                "audiogen_ambient_cache_hit",
                output_path=str(output_path),
            )
            return output_path

        ta = _import_torchaudio()
        self._ensure_loaded()

        logger.info(
            "audiogen_ambient_generate_start",
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
                "audiogen_ambient_generate_done",
                output_path=str(output_path),
            )
            return output_path

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "audiogen_ambient_generate_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None
