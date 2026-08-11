#!/usr/bin/env bash
# One command to run the whole project: creates a local virtualenv,
# installs the core package and server dependencies, runs the test
# suite, then starts the server for every device on the network.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
PORT=${PORT:-8000}

if [ ! -d .venv ]; then
  echo "Creating virtualenv..."
  "$PYTHON" -m venv .venv
fi
echo "Installing dependencies..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e "core[dev]" fastapi "uvicorn[standard]"

echo "Running tests..."
.venv/bin/pytest core/tests -q

echo
echo "This machine:  http://localhost:$PORT/"
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)
if [ -n "${LAN_IP:-}" ]; then
  echo "LAN devices:   http://$LAN_IP:$PORT/"
fi
echo
exec .venv/bin/uvicorn server.main:app --host 0.0.0.0 --port "$PORT"
