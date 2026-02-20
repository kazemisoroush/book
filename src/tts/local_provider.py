"""Local TTS provider implementation using piper."""
from pathlib import Path
import subprocess
from src.tts.tts_provider import TTSProvider


class LocalTTSProvider(TTSProvider):
    """Local TTS provider using piper-tts."""

    def __init__(self, models_dir: Path = Path("models")):
        """
        Initialize local TTS provider.

        Args:
            models_dir: Directory containing piper models
        """
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Default voice mappings
        self._voice_map = {
            "narrator": "en_US-lessac-medium",
            "male_1": "en_US-joe-medium",
            "female_1": "en_US-amy-medium",
            "male_2": "en_GB-alan-medium",
            "female_2": "en_GB-alba-medium",
        }

    def synthesize(self, text: str, voice_id: str, output_path: Path) -> None:
        """Synthesize text using piper."""
        # Get the model name for this voice
        model_name = self._voice_map.get(voice_id, self._voice_map["narrator"])
        model_path = self.models_dir / f"{model_name}.onnx"

        # Check if piper is available
        temp_text = None
        try:
            # Write text to temp file
            temp_text = output_path.parent / f"{output_path.stem}_temp.txt"
            with open(temp_text, 'w', encoding='utf-8') as f:
                f.write(text)

            # Run piper
            result = subprocess.run(
                [
                    "piper",
                    "--model", str(model_path),
                    "--output_file", str(output_path),
                ],
                stdin=open(temp_text, 'r'),
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"Piper failed: {result.stderr}")

        except FileNotFoundError:
            # Fallback to espeak if piper is not available
            self._synthesize_with_espeak(text, output_path)
        finally:
            # Always clean up temp file if it was created
            if temp_text is not None:
                temp_text.unlink(missing_ok=True)

    def _synthesize_with_espeak(self, text: str, output_path: Path) -> None:
        """Fallback to espeak for synthesis."""
        try:
            result = subprocess.run(
                [
                    "espeak",
                    "-w", str(output_path),
                    text
                ],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"espeak failed: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                "No TTS engine available. Install piper-tts or espeak."
            )

    def get_available_voices(self) -> dict[str, str]:
        """Get available local voices."""
        return self._voice_map.copy()
