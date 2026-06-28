#!/usr/bin/env bash
# Fetch the package, package the model tarball, and upload it to S3.
# Run this before deploy.py. Override the bucket with VIBEVOICE_BUCKET.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BUCKET="${VIBEVOICE_BUCKET:-sagemaker-vibevoice-116129308579-us-east-1}"

"$HERE/fetch.sh"

cd "$HERE"
tar --exclude='*/__pycache__' --exclude='*.pyc' -czf model.tar.gz code
aws s3 cp model.tar.gz "s3://$BUCKET/vibevoice/model.tar.gz"
echo "uploaded model.tar.gz to s3://$BUCKET/vibevoice/"
