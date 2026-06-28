"""SageMaker inference handler for VibeVoice-1.5B TTS.

Contract (HuggingFace inference toolkit): model_fn -> input_fn -> predict_fn -> output_fn.

Request  (application/json): {"text": "...", "voice": "en-Carter_man"}
         multi-speaker:       {"text": "Speaker 1: ...\nSpeaker 2: ...", "voices": ["en-Alice_woman", "en-Carter_man"]}
         optional:            {"cfg_scale": 1.3}
Response (audio/wav):         raw 24kHz mono WAV bytes
         (application/json):  {"audio_base64": "...", "sample_rate": 24000}

The vibevoice package is vendored alongside this file; voices/ holds reference WAVs.
"""
import base64
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import torch

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))  # make the vendored vibevoice package importable

from vibevoice.modular.modeling_vibevoice_inference import (  # noqa: E402
    VibeVoiceForConditionalGenerationInference,
)
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor  # noqa: E402

MODEL_ID = os.environ.get("VIBEVOICE_MODEL_ID", "aoi-ot/VibeVoice-1.5B")
VOICES_DIR = _HERE / "voices"
SAMPLE_RATE = 24000
DEFAULT_VOICE = "en-Carter_man"
DDPM_STEPS = int(os.environ.get("VIBEVOICE_DDPM_STEPS", "10"))


def _device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def model_fn(model_dir):
    device = _device()
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    processor = VibeVoiceProcessor.from_pretrained(MODEL_ID)
    model = VibeVoiceForConditionalGenerationInference.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        attn_implementation="sdpa",  # flash_attention_2 is not available in the DLC
    )
    model.to(device)
    model.eval()
    model.set_ddpm_inference_steps(num_steps=DDPM_STEPS)
    return {"model": model, "processor": processor, "device": device}


def _voice_path(name: str) -> str:
    """Resolve a voice name to a bundled reference WAV. Tolerant of short names."""
    exact = VOICES_DIR / f"{name}.wav"
    if exact.exists():
        return str(exact)
    low = name.lower()
    for f in sorted(VOICES_DIR.glob("*.wav")):
        if low in f.stem.lower():
            return str(f)
    return str(VOICES_DIR / f"{DEFAULT_VOICE}.wav")


def input_fn(request_body, content_type="application/json"):
    if isinstance(request_body, (bytes, bytearray)):
        request_body = request_body.decode("utf-8")
    if content_type and "json" in content_type:
        return json.loads(request_body)
    return {"text": request_body}


def _build_script(text: str) -> str:
    """Pass through pre-formatted 'Speaker N:' scripts; else wrap as single speaker."""
    if re.search(r"^\s*Speaker\s+\d+\s*:", text, flags=re.MULTILINE):
        return text.strip()
    return f"Speaker 1: {text.strip()}"


def predict_fn(data, context):
    model = context["model"]
    processor = context["processor"]
    device = context["device"]

    text = (data.get("text") or "").strip()
    if not text:
        raise ValueError("request must include non-empty 'text'")
    voices = data.get("voices") or [data.get("voice", DEFAULT_VOICE)]
    cfg_scale = float(data.get("cfg_scale", 1.3))

    voice_paths = [_voice_path(v) for v in voices]
    full_script = _build_script(text)

    inputs = processor(
        text=[full_script],
        voice_samples=[voice_paths],
        padding=True,
        return_tensors="pt",
        return_attention_mask=True,
    )
    for k, v in inputs.items():
        if torch.is_tensor(v):
            inputs[k] = v.to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=None,
            cfg_scale=cfg_scale,
            tokenizer=processor.tokenizer,
            generation_config={"do_sample": False},
            verbose=False,
            is_prefill=True,
        )

    wav = outputs.speech_outputs[0]
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        processor.save_audio(wav, output_path=tmp.name)
        return Path(tmp.name).read_bytes()
    finally:
        os.unlink(tmp.name)


def output_fn(prediction, accept="audio/wav"):
    # MMS json.dumps()-es any non-bytes return value, so return raw bytes for the audio
    # path (passed through unchanged) and a dict for json (MMS serializes it correctly).
    # Never return a tuple/str here.
    if accept and "json" in accept:
        return {"audio_base64": base64.b64encode(prediction).decode("ascii"), "sample_rate": SAMPLE_RATE}
    return prediction
