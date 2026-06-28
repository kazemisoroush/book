"""Prime the endpoint: the model loads lazily on first invoke (download + GPU load),
which can exceed the real-time 60s invoke limit. The client errors but the backend
keeps loading (SAGEMAKER_MODEL_SERVER_TIMEOUT=1800). Retry until a call returns audio.

Run: .venv/bin/python warm.py
"""
import json
import sys
import time

import boto3
from botocore.config import Config

rt = boto3.client(
    "sagemaker-runtime",
    region_name="us-east-1",
    config=Config(read_timeout=70, connect_timeout=10, retries={"max_attempts": 0}),
)

DEADLINE = time.time() + 1200  # up to 20 min for cold download+load
attempt = 0
while time.time() < DEADLINE:
    attempt += 1
    t0 = time.time()
    try:
        r = rt.invoke_endpoint(
            EndpointName="vibevoice-15b",
            ContentType="application/json",
            Accept="audio/wav",
            Body=json.dumps({"text": "Hello there.", "voice": "en-Carter_man"}),
        )
        audio = r["Body"].read()
        print(f"READY after {attempt} attempts: {len(audio)} bytes audio in {time.time()-t0:.0f}s")
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print(f"attempt {attempt} (+{time.time()-t0:.0f}s): warming... [{str(e)[:90]}]")
        time.sleep(25)
print("gave up waiting for warm-up")
sys.exit(1)
