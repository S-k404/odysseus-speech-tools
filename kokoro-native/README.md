# Kokoro Dual-Stack TTS Setup

This directory contains the **native macOS Apple Metal (MPS) GPU TTS server** running alongside the containerized **Speaches Docker** instance.

---

## Architecture: Dual-Stack Setup

| Engine | Environment | Port | Hardware Backend | Purpose |
|---|---|---|---|---|
| **Speaches Docker** | Docker Container | `8000` | CPU (Linux container) | Odysseus, container-to-container calls, general web UI |
| **Kokoro Native** | macOS Host (Python venv) | `8001` | **Apple Metal GPU (MPS)** | Fast on-demand batch audiobook generation via `make_audiobook` |

---

## ⚡ Performance

* **Speaches in Docker (CPU)**: ~0.3–0.5× real-time.
* **Kokoro Native (Apple Metal GPU)**: **~10–16× real-time** (0.93 seconds per chunk, cool CPU operation).

---

## 🚀 Usage

### 1. On-Demand Audiobook Generation (Recommended)

The `make_audiobook` CLI handles starting the GPU server, converting the book, and shutting down the server automatically:

```bash
# Convert a single PDF or EPUB to a chaptered M4B audiobook
make_audiobook mybook.pdf

# Convert from ~/Documents/Books by index number or title
make_audiobook 11
make_audiobook "Linus"

# Select a specific voice (e.g., Bella, Adam, George)
make_audiobook -v af_bella 1
make_audiobook -v am_adam 10
make_audiobook -v bm_george "Python"

# View all available voices and style descriptions
make_audiobook --voices

# List available books in ~/Documents/Books
make_audiobook --list

# Batch-convert all pending books (optional: adjust speed)
make_audiobook -v af_heart --speed 1.15
```

Outputs are automatically saved to: `~/Documents/AudioBook/<BookTitle>.m4b`.

### 2. Manual Server Control

If you want the native GPU server running continuously on port 8001:

```bash
cd ~/Documents/Docker/Speaches/kokoro-native
./start.sh
```

Health check:
```bash
curl http://localhost:8001/health
# {"status":"ok","backend":"pytorch-metal-mps","device":"mps","port":8001}
```

Synthesize audio directly via OpenAI-compatible endpoint:
```bash
curl -s -X POST http://localhost:8001/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Hello from Apple Metal GPU!","voice":"af_heart"}' \
  --output test.mp3
```

---

## 🎙️ Popular Voices & Aliases

* **American Female (`af_*`)**: `af_heart` (default), `af_bella` (storytelling), `af_sky` (bright), `af_nicole`, `af_sarah` (non-fiction), `af_river`, `af_alloy`
* **American Male (`am_*`)**: `am_adam` (deep narrator), `am_michael` (podcast), `am_onyx` (baritone), `am_echo`, `am_eric`
* **British Female (`bf_*`)**: `bf_emma` (refined RP), `bf_alice` (crisp), `bf_isabella`, `bf_lily`
* **British Male (`bm_*`)**: `bm_george` (classic audiobook), `bm_daniel`, `bm_fable`, `bm_lewis`

*(Short aliases like `heart`, `bella`, `adam`, `george`, `emma`, etc. are supported directly).*
