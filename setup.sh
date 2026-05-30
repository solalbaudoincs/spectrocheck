#!/usr/bin/env bash
# One-time setup for the Transcode Detector (macOS / Linux).
set -euo pipefail
cd "$(dirname "$0")"

command -v ffmpeg >/dev/null 2>&1 || echo "WARNING: ffmpeg not found. Install it (brew install ffmpeg / apt install ffmpeg)."

echo "Creating Python venv + installing backend deps..."
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

echo "Installing frontend deps..."
npm --prefix frontend install

echo ""
echo "Setup complete. Start the app with:  ./run.sh"
