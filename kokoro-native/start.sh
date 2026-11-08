#!/usr/bin/env bash
# =============================================================================
# start.sh — Kokoro Native TTS Server (Apple Silicon / CoreML)
#
# Usage:
#   ./start.sh          # start normally
#   ./start.sh --setup  # first-time: create venv, install deps, download model
# =============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
MODEL_FILE="$SCRIPT_DIR/kokoro-v1.0.onnx"
VOICES_FILE="$SCRIPT_DIR/voices-v1.0.bin"
MODEL_BASE_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

# -------------------------------------------------------------------------
# Setup mode: create venv + install deps + download models
# -------------------------------------------------------------------------
if [[ "${1:-}" == "--setup" ]]; then
    echo "==> Setting up Kokoro Native TTS environment…"

    echo "--- Creating Python 3.11 venv with uv ---"
    uv venv "$VENV_DIR" --python 3.11

    echo "--- Installing Python dependencies ---"
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet
    uv pip install --python "$VENV_DIR/bin/python" -r "$SCRIPT_DIR/requirements.txt"

    echo "--- Checking for model files ---"
    if [[ ! -f "$MODEL_FILE" ]]; then
        echo "Downloading kokoro-v1.0.onnx (~300 MB)…"
        curl -L --progress-bar -o "$MODEL_FILE" \
            "$MODEL_BASE_URL/kokoro-v1.0.onnx"
    else
        echo "kokoro-v1.0.onnx already present — skipping download."
    fi

    if [[ ! -f "$VOICES_FILE" ]]; then
        echo "Downloading voices-v1.0.bin (~27 MB)..."
        curl -L --progress-bar -o "$VOICES_FILE" \
            "$MODEL_BASE_URL/voices-v1.0.bin"
    else
        echo "voices-v1.0.bin already present — skipping download."
    fi

    echo ""
    echo "==> Setup complete. Verifying Apple Metal MPS GPU…"
    "$VENV_DIR/bin/python" -c "
import torch
if torch.backends.mps.is_available():
    print('✅  Apple Metal GPU (MPS) is ACTIVE — 100% GPU inference will be used')
else:
    print('⚠️  MPS not available — running on CPU')
"
    echo ""
    echo "Run ./start.sh (without --setup) to start the server."
    exit 0
fi

# -------------------------------------------------------------------------
# Normal start
# -------------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    echo "ERROR: venv not found. Run './start.sh --setup' first."
    exit 1
fi

if [[ ! -f "$MODEL_FILE" ]] || [[ ! -f "$VOICES_FILE" ]]; then
    echo "ERROR: Model files missing. Run './start.sh --setup' first."
    exit 1
fi

echo "==> Starting Kokoro Native TTS server on port 8001…"
echo "    Health: http://localhost:8001/health"
echo "    Speech: POST http://localhost:8001/v1/audio/speech"
echo ""

source "$VENV_DIR/bin/activate"
exec uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
