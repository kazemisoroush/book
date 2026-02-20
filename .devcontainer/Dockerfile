FROM mcr.microsoft.com/devcontainers/python:1-3.11

# Install system dependencies: audio tools and Python pip
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    espeak \
    ffmpeg \
    python3-pip \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*
