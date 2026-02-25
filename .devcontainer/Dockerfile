FROM mcr.microsoft.com/devcontainers/python:1-3.11

# Remove yarn repository (has expired GPG key and isn't needed)
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Install system dependencies: audio tools and Python pip
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    espeak \
    ffmpeg \
    python3-pip \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Create python symlink for convenience
RUN ln -sf /usr/local/bin/python3 /usr/local/bin/python
