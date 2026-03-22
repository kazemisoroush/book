#!/bin/bash
set -e

echo "Configuring Git..."
git config --global user.email 'kazemi.soroush@gmail.com'
git config --global user.name 'Soroush Kazemi'

echo "Installing Python dependencies..."
python3 -m pip install --break-system-packages -r requirements.txt
