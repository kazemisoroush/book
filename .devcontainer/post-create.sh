#!/bin/bash
set -e

echo "Configuring Git..."
git config --global user.email 'kazemi.soroush@gmail.com'
git config --global user.name 'Soroush Kazemi'
git config --global --add safe.directory /workspaces/book

echo "Installing Python dependencies..."
python3 -m pip install --break-system-packages -r requirements.txt

echo "Installing SuperClaude Framework..."
if ! command -v pipx &>/dev/null; then
    python3 -m pip install --user --quiet pipx
    export PATH="$HOME/.local/bin:$PATH"
fi
pipx install superclaude
superclaude install
