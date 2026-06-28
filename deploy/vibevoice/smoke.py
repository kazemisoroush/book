"""Smoke test: one short line through the VibeVoice endpoint -> smoke.wav.

Confirms the endpoint returns valid audio before we wire it into the book pipeline.
Run: .venv/bin/python smoke.py
"""
import json
import sys

import boto3

ENDPOINT = "vibevoice-15b"
REGION = "us-east-1"
TEXT = (
    "It is a truth universally acknowledged, that a single man in possession "
    "of a good fortune, must be in want of a wife."
)
VOICE = sys.argv[1] if len(sys.argv) > 1 else "en-Alice_woman"

rt = boto3.client("sagemaker-runtime", region_name=REGION)
resp = rt.invoke_endpoint(
    EndpointName=ENDPOINT,
    ContentType="application/json",
    Accept="audio/wav",
    Body=json.dumps({"text": TEXT, "voice": VOICE, "cfg_scale": 1.3}),
)
audio = resp["Body"].read()
out = "smoke.wav"
with open(out, "wb") as f:
    f.write(audio)
print(f"wrote {out}: {len(audio)} bytes (voice={VOICE})")
