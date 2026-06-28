# VibeVoice SageMaker endpoint

Tooling to stand up the self-hosted VibeVoice TTS endpoint that the
[vibevoice TTS provider](../../src/audio/tts/vibevoice_tts_provider.py) calls.

## What is here

* `code/inference.py`. SageMaker handler (model load, synth, WAV response).
* `code/requirements.txt`. Runtime deps installed into the container at start.
* `fetch.sh`. Pull the VibeVoice package and voices from the community fork into `code/` at a pinned commit. They are not stored in this repo.
* `build.sh`. Run `fetch.sh`, package the tarball, and upload it to S3.
* `deploy.py`. Create or delete the endpoint.
* `warm.py`. Prime the model after deploy (first call triggers the weight download).
* `smoke.py`. Send one line and save a WAV to confirm the endpoint works.

The VibeVoice package and the five reference voice WAVs are fetched at build time
rather than committed, so the repo stays lean. `fetch.sh` pins a commit sha for
reproducibility, and the MIT mirror `aoi-ot/VibeVoice` can stand in if the fork moves.

## Prerequisites

* AWS credentials with SageMaker, S3, and IAM access.
* A SageMaker execution role and an S3 bucket for the model artifact.
* Endpoint quota for one `ml.g5.xlarge` instance in the chosen region.

## Deploy

Run from this directory.

```bash
# 1. Fetch the package + voices, package the tarball, and upload it.
#    Override the target bucket with VIBEVOICE_BUCKET if needed.
./build.sh

# 2. Create the endpoint (about 15 minutes; weights download on first call).
python deploy.py

# 3. Prime the model, then confirm it returns audio.
python warm.py
python smoke.py
```

Tear the endpoint down when you are done so it stops billing:

```bash
python deploy.py --delete
```

## Gotchas learned the hard way

* The endpoint loads weights from `aoi-ot/VibeVoice-1.5B`. The official
  `microsoft/VibeVoice-1.5B` is also live and can be used instead. The community
  fork is needed for the non-streaming inference class that the official repo does
  not ship. The shards are stored on HuggingFace Xet, so the container needs
  `hf_xet` or it fetches the index but not the weights.
* The model tarball must hold `code/inference.py` at its root. Passing a local
  `source_dir` without a tarball leaves the handler unfound.
* `output_fn` must return raw bytes. The model server tries to JSON encode any
  non bytes return value, which fails on audio.
* Real time invoke has a hard 60 second limit. The provider splits long beats so
  each request stays under it.
* Container: HuggingFace PyTorch inference, transformers 4.51.3, torch 2.6, py312.
