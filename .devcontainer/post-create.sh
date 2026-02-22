#!/bin/bash
set -e

echo "Configuring Git..."
git config --global user.email 'kazemi.soroush@gmail.com'
git config --global user.name 'Soroush Kazemi'

echo "Installing Python dependencies..."
python3 -m pip install --break-system-packages -r requirements.txt

echo "Running tests..."
python3 -m pytest src/ -v

echo ""
echo "Post-create setup complete!"
echo ""
echo "To generate an audiobook:"
echo "  python3 -m src.cli books/pg1342.txt --discover-characters"
echo "  python3 -m src.cli books/pg1342.txt"
echo ""
echo "For more options:"
echo "  python3 -m src.cli --help"