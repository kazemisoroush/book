"""Deploy VibeVoice-1.5B to a SageMaker real-time GPU endpoint.

Uses the HuggingFace DLC + vendored code in ./code. The model weights are pulled
from the community mirror at container start (model_fn), so first boot is slow
(~pip install + ~7GB download): allow up to 30 min for the endpoint to go InService.

Run:  .venv/bin/python deploy.py
Tear down later:  .venv/bin/python deploy.py --delete
"""
import argparse

import boto3
import sagemaker
from sagemaker.huggingface import HuggingFaceModel

REGION = "us-east-1"
ROLE = "arn:aws:iam::116129308579:role/VibeVoiceSageMakerRole"
ENDPOINT_NAME = "vibevoice-15b"
INSTANCE_TYPE = "ml.g5.xlarge"  # A10G 24GB, native bf16; endpoint quota = 1
# Self-contained tarball with code/inference.py inside (the "bring your own inference
# script" layout). The toolkit auto-detects code/inference.py from the model artifact,
# so we must NOT pass source_dir/entry_point (that path left SUBMIT_DIRECTORY=file://code).
MODEL_DATA_S3 = "s3://sagemaker-vibevoice-116129308579-us-east-1/vibevoice/model.tar.gz"

# HF DLC base versions. The 4.51.3 DLC already ships VibeVoice's exact transformers
# pin (pytorch 2.6.0 / py312, available in us-east-1), so code/requirements.txt only
# needs to add the few extra runtime deps (accelerate/diffusers/ml-collections/...).
TRANSFORMERS_VERSION = "4.51.3"
PYTORCH_VERSION = "2.6.0"
PY_VERSION = "py312"


def deploy():
    boto_sess = boto3.Session(region_name=REGION)
    sess = sagemaker.Session(boto_session=boto_sess)

    model = HuggingFaceModel(
        role=ROLE,
        sagemaker_session=sess,
        model_data=MODEL_DATA_S3,
        transformers_version=TRANSFORMERS_VERSION,
        pytorch_version=PYTORCH_VERSION,
        py_version=PY_VERSION,
        name=ENDPOINT_NAME,
        env={
            "VIBEVOICE_MODEL_ID": "aoi-ot/VibeVoice-1.5B",
            "SAGEMAKER_MODEL_SERVER_TIMEOUT": "1800",  # 30 min per-invocation ceiling
            "TS_DEFAULT_RESPONSE_TIMEOUT": "1800",
        },
    )

    predictor = model.deploy(
        initial_instance_count=1,
        instance_type=INSTANCE_TYPE,
        endpoint_name=ENDPOINT_NAME,
        container_startup_health_check_timeout=1800,  # 30 min for pip + weight download
        model_data_download_timeout=1800,
        wait=True,
    )
    print(f"InService: {predictor.endpoint_name}")


def delete():
    sm = boto3.client("sagemaker", region_name=REGION)
    for fn, kwarg in (
        (sm.delete_endpoint, "EndpointName"),
        (sm.delete_endpoint_config, "EndpointConfigName"),
        (sm.delete_model, "ModelName"),
    ):
        try:
            fn(**{kwarg: ENDPOINT_NAME})
            print(f"deleted {kwarg}={ENDPOINT_NAME}")
        except Exception as exc:  # noqa: BLE001
            print(f"skip {kwarg}: {exc}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true", help="tear down endpoint + config + model")
    args = ap.parse_args()
    delete() if args.delete else deploy()
