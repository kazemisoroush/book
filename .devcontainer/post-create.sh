#!/bin/bash
set -e

echo "Configuring Git..."
git config --global user.email 'kazemi.soroush@gmail.com'
git config --global user.name 'Soroush Kazemi'

echo "Installing Python dependencies..."
python3 -m pip install --break-system-packages pytest

echo "Running tests..."
python3 -m pytest src/ -v

echo ""
echo "Post-create setup complete!"
echo ""
echo "Try the example:"
echo "  python3 example.py"
echo ""
echo "To generate an audiobook:"
echo "  python3 -m src.cli books/pg1342.txt --discover-characters"
echo "  python3 -m src.cli books/pg1342.txt --provider local"