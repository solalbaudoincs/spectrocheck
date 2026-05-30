#!/usr/bin/env bash
# Transcode Detector launcher (dev: backend + frontend).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Run ./setup.sh first."
  exit 1
fi

echo "Starting backend  -> http://127.0.0.1:8000"
./.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACK=$!
trap 'kill $BACK 2>/dev/null || true' EXIT
sleep 2

echo "Starting frontend -> http://localhost:5173"
npm --prefix frontend run dev
