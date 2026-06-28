#!/usr/bin/env bash
# Fetch the VibeVoice package and reference voices into code/ at a pinned commit.
# The package is not vendored in this repo; it is pulled from the community fork
# at build time so the repo stays lean. Pin is a commit sha for reproducibility.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FORK="https://github.com/vibevoice-community/VibeVoice.git"
PIN="07cb79feadd2d3fd7f47530d4c964a12857936a0"
VOICES="en-Alice_woman en-Carter_man en-Frank_man en-Maya_woman in-Samuel_man"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git -C "$tmp" init -q
git -C "$tmp" remote add origin "$FORK"
git -C "$tmp" fetch -q --depth 1 origin "$PIN"
git -C "$tmp" checkout -q FETCH_HEAD

rm -rf "$HERE/code/vibevoice" "$HERE/code/voices"
cp -r "$tmp/vibevoice" "$HERE/code/vibevoice"
mkdir -p "$HERE/code/voices"
for v in $VOICES; do
  cp "$tmp/demo/voices/$v.wav" "$HERE/code/voices/"
done

echo "fetched vibevoice package + 5 voices at pinned $PIN"
