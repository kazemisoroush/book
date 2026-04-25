"""VibeVoice TTS provider implementation.

Uses Microsoft's open-source VibeVoice model for local text-to-speech
synthesis.  Completely free — no API keys required, runs on local GPU/CPU.

Model: ``microsoft/VibeVoice-Realtime-0.5B`` (HuggingFace).
Voices: pre-baked ``.pt`` embedding files shipped with the model repo.

Requires ``torch`` and ``transformers`` at runtime.  These are NOT declared
as project dependencies because they are heavy; install them manually::

    pip install torch transformers
"""
from pathlib import Path
from typing import Any, Optional

import structlog

from src.audio.tts.tts_provider import TTSProvider

logger = structlog.get_logger(__name__)

# Default HuggingFace model identifier
_DEFAULT_MODEL_ID = "microsoft/VibeVoice-Realtime-0.5B"

# Built-in voice presets bundled with the model repo (en-* subset).
# Keys are human-friendly names, values are the ``.pt`` file stems used
# to locate cached voice embeddings inside the model directory.
_BUILTIN_VOICES: dict[str, dict[str, str]] = {
    "Carter": {"voice_id": "en-Carter_man", "gender": "male"},
    "Davis": {"voice_id": "en-Davis_man", "gender": "male"},
    "Emma": {"voice_id": "en-Emma_woman", "gender": "female"},
    "Frank": {"voice_id": "en-Frank_man", "gender": "male"},
    "Grace": {"voice_id": "en-Grace_woman", "gender": "female"},
    "Mike": {"voice_id": "en-Mike_man", "gender": "male"},
}


class VibeVoiceTTSProvider(TTSProvider):
    """Microsoft VibeVoice local TTS provider.

    Loads the VibeVoice-Realtime-0.5B model on first ``synthesize`` call
    (lazy init) and caches it for the lifetime of the provider instance.

    This provider is completely free — it runs inference locally and does
    not call any external API.
    """

    @property
    def name(self) -> str:
        return "vibevoice"

    def __init__(
        self,
        model_id: str = _DEFAULT_MODEL_ID,
        device: str = "cpu",
        voices_dir: Optional[Path] = None,
    ) -> None:
        """Initialize VibeVoice provider.

        Args:
            model_id: HuggingFace model identifier or local path.
            device: PyTorch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
            voices_dir: Directory containing ``<voice_id>.pt`` files.
                If ``None``, defaults to ``demo/voices/streaming_model``
                inside the HuggingFace cache for *model_id*.
        """
        self._model_id = model_id
        self._device = device
        self._voices_dir = voices_dir
        # Lazy-loaded on first use
        self._model: Any = None
        self._processor: Any = None

    def provide(self, segment: Any, voice_id: str, book_id: str) -> float:
        """Not yet implemented for VibeVoice provider."""
        raise NotImplementedError("VibeVoiceTTSProvider.provide() not yet implemented")

    # ── lazy model loading ──────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Load model + processor on first use."""
        if self._model is not None:
            return

        try:
            import torch  # type: ignore[import-not-found]
            from vibevoice.modular.modeling_vibevoice_streaming_inference import (  # type: ignore[import-not-found]
                VibeVoiceStreamingForConditionalGenerationInference,
            )
            from vibevoice.processor.vibevoice_streaming_processor import (  # type: ignore[import-not-found]
                VibeVoiceStreamingProcessor,
            )
        except ImportError as exc:
            raise ImportError(
                "VibeVoice requires 'torch' and the vibevoice package. "
                "Install with: pip install torch && pip install git+https://github.com/microsoft/VibeVoice.git"
            ) from exc

        logger.info(
            "vibevoice_loading_model",
            model_id=self._model_id,
            device=self._device,
        )

        self._processor = VibeVoiceStreamingProcessor.from_pretrained(self._model_id)

        dtype = torch.bfloat16 if self._device != "cpu" else torch.float32
        self._model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
            self._model_id,
            torch_dtype=dtype,
            device_map=self._device,
        )
        self._model.eval()

        logger.info("vibevoice_model_loaded", device=self._device)

    # ── voice embedding helpers ─────────────────────────────────────────

    def _resolve_voice_path(self, voice_id: str) -> Optional[Path]:
        """Resolve a voice_id to its ``.pt`` embedding file."""
        if self._voices_dir is not None:
            candidate = self._voices_dir / f"{voice_id}.pt"
            if candidate.exists():
                return candidate

        # Try HuggingFace cache default location
        try:
            from huggingface_hub import (  # type: ignore[import-not-found]
                hf_hub_download,
            )
            path = hf_hub_download(
                repo_id=self._model_id,
                filename=f"demo/voices/streaming_model/{voice_id}.pt",
            )
            return Path(path)
        except Exception:  # noqa: BLE001
            logger.debug("vibevoice_voice_file_not_found", voice_id=voice_id)
            return None

    # ── TTSProvider interface ───────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Synthesize text using local VibeVoice model.

        Args:
            text: Text to synthesize.
            voice_id: Voice preset stem (e.g. ``"en-Emma_woman"``).
            output_path: Where to save the generated ``.wav`` file.
            emotion: Ignored (VibeVoice does not support emotion tags).
            previous_text: Ignored.
            next_text: Ignored.
            voice_stability: Ignored.
            voice_style: Ignored.
            voice_speed: Ignored.
            previous_request_ids: Ignored.

        Returns:
            ``None`` — local inference has no request ID concept.
        """
        import torch  # type: ignore[import-not-found]

        self._ensure_loaded()

        logger.info(
            "vibevoice_synthesize_start",
            voice_id=voice_id,
            text_length=len(text),
            output_path=str(output_path),
        )

        # Load voice embedding (if available)
        voice_path = self._resolve_voice_path(voice_id)
        all_prefilled_outputs = None
        if voice_path is not None:
            all_prefilled_outputs = torch.load(voice_path, map_location=self._device, weights_only=True)
            logger.debug("vibevoice_voice_loaded", voice_id=voice_id)
        else:
            logger.warning("vibevoice_voice_not_found_using_default", voice_id=voice_id)

        try:
            inputs = self._processor(text=text, return_tensors="pt").to(self._device)

            outputs = self._model.generate(
                **inputs,
                max_new_tokens=None,
                cfg_scale=1.5,
                tokenizer=self._processor.tokenizer,
                generation_config={"do_sample": False},
                verbose=False,
                all_prefilled_outputs=all_prefilled_outputs,
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._processor.save_audio(outputs.speech_outputs[0], str(output_path))

            logger.info(
                "vibevoice_synthesize_done",
                output_path=str(output_path),
            )
            return None

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "vibevoice_synthesize_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None

    def get_available_voices(self) -> dict[str, str]:
        """Return built-in English voice presets.

        Returns:
            Dictionary mapping human-friendly names to voice ID stems.
        """
        return {name: info["voice_id"] for name, info in _BUILTIN_VOICES.items()}

    def get_voices(self) -> list[dict[str, Any]]:
        """Return built-in voices with metadata.

        Returns:
            List of voice dicts with ``voice_id``, ``name``, and ``labels``.
        """
        return [
            {
                "voice_id": info["voice_id"],
                "name": name,
                "labels": {"gender": info["gender"]},
            }
            for name, info in _BUILTIN_VOICES.items()
        ]
