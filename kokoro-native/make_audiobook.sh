#!/usr/bin/env bash
# =============================================================================
# make_audiobook — Interactive Terminal Audiobook Studio (Apple Metal GPU)
# Runs Kokoro-82M native PyTorch on Apple Silicon GPU shaders.
# Supports EPUB (direct TTS) and PDF (extract -> EPUB -> TTS).
# =============================================================================
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
KOKORO_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
PYTHON="$KOKORO_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "Kokoro Python virtual environment not found at $PYTHON" >&2
    exit 1
fi

exec "$PYTHON" "$KOKORO_DIR/app.py" "$@"
