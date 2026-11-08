# Project Progress & Architecture Documentation

**Last Updated:** September 19, 2026  
**Workspace:** `~/Documents/Docker/`  
**Audiobooks Destination:** `~/Documents/AudioBook/`  
**Source Books Directory:** `~/Documents/Books/`  

---

## 1. Executive Summary & Dual-Stack Architecture

This repository hosts a unified dual-stack speech architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             macOS Host Machine                              │
│                                                                             │
│  ┌─────────────────────────────┐           ┌─────────────────────────────┐  │
│  │    DOCKER CONTAINER STACK   │           │     NATIVE HOST PROCESS     │  │
│  │                             │           │                             │  │
│  │  • speaches (port 8000)     │           │  • kokoro-native (port 8001)│  │
│  │    - TTS: Kokoro-82M (CPU)  │           │    - 100% Apple Metal GPU   │  │
│  │    - STT: Faster-Whisper    │           │    - PyTorch MPS backend    │  │
│  │    - Dynamic model unload   │           │    - ~10–16× real-time speed│  │
│  │                             │           │    - Strictly ON-DEMAND     │  │
│  │  • odysseus (port 7000)     │           │                             │  │
│  │    - Connected via docker   │           │  • make_audiobook CLI       │  │
│  │      network odysseus_def   │           │    - Fast batch conversion  │  │
│  └─────────────────────────────┘           └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Audiobook Conversion Progress

### 2.1. Completed Audiobooks (Saved & Verified in `~/Documents/AudioBook/`)
All files contain embedded chapter metadata and resume markers:

| Book Title | Format | File Size | Audio Length | Synthesis Details |
|---|---|---|---|---|
| **Astronomy 2e** *(OpenStax)* | `.m4b` | **`1.65 GB`** | **55.5 hours** | 43 chapters, 199,946s audio, complete |
| **Additive Manufacturing Essentials** | `.m4b` | **`303 MB`** | ~8.0 hours | Full book, chapters embedded |
| **Python Illustrated** (*Maaike van Putten*) | `.m4b` | **`256 MB`** | ~9.0 hours | 18 chapters, complete |
| **Linus Torvalds — Just for Fun** | `.m4b` | **`224 MB`** | ~7.5 hours | 40 chapters, verified |
| **GATE 2026 Results** | `.m4u` | **`0.3 MB`** | ~5 mins | Complete |

**Total Completed Audio:** **~2.44 GB** (~80+ hours of spoken content).

---

### 2.2. In-Progress Books (Active on Apple Metal GPU)

1. **Book #10: Introduction to Python Programming** (`Introduction_to_Python_Programming-WEB.pdf`, 8.7 MB)
   * **Mode**: Parallel dedicated job
   * **Voice**: `am_adam` (deep male narrator)
   * **Progress**: Chapter 13 of 17 (~89% completed)
   * **Log**: `~/Documents/Docker/Speaches/kokoro-native/parallel_book10.log`

2. **Book #5: Digital Fundamentals** (`Digital Fundamentals -- Thomas L. Floyd`, 45.0 MB)
   * **Mode**: Main batch queue
   * **Voice**: `af_heart` (expressive female narrator)
   * **Progress**: Chapter 10 of 37 (~27% completed)
   * **Log**: `~/Documents/Docker/Speaches/kokoro-native/batch_audiobook.log`

---

### 2.3. Remaining Queue (Will Convert Sequentially)
Once *Digital Fundamentals* finishes, the batch queue will process:
1. `Foundations_of_Information_Systems_-_WEB_oNlbGYl.pdf` (23.7 MB)
2. `Grob's Basic Electronics 13th latest edition` (37.2 MB)
3. `Introduction_To_Computer_Science_-_WEB.pdf` (52.5 MB)
4. `Make_ Electronics -- Charles Platt` (68.1 MB)

*(Note: `Introduction_to_Python_Programming` is already running in parallel and will be automatically skipped by the batch queue when it finishes).*

---

## 3. Odysseus & Docker Integration Details

### 3.1. Container Setup
* Container `speaches` (`ghcr.io/speaches-ai/speaches:latest-cpu`) runs on port `8000:8000` on the `odysseus_default` network.
* Container `odysseus-odysseus-1` runs on port `127.0.0.1:7000:7000`.

### 3.2. Odysseus Environment Variables (`Odysseus/docker-compose.yml`)
```yaml
      - TTS_ENABLED=true
      - TTS_PROVIDER=openai
      - TTS_OPENAI_API_BASE=http://speaches:8000/v1
      - TTS_OPENAI_API_KEY=not-needed
      - TTS_MODEL=hexgrad/Kokoro-82M
      - TTS_VOICE=af_heart
      - STT_ENABLED=true
      - STT_PROVIDER=openai
      - STT_OPENAI_API_BASE=http://speaches:8000/v1
      - STT_OPENAI_API_KEY=not-needed
      - STT_MODEL=Systran/faster-whisper-small
```

### 3.3. Cleanups Performed
* Removed obsolete `kokoro-tts` container (`ghcr.io/remsky/kokoro-fastapi-cpu`), reclaiming **~790 MB RAM**.
* Removed orphaned volumes (`odysseus_kokoro-models`, `odysseus_kokoro-voices`).
* Verified dynamic memory unloading: `curl http://localhost:8000/api/ps` returns `{"models":[]}` when idle.

---

## 4. Interactive Audiobook Studio App (`make_audiobook` / `app.py`)

The audiobook generator is now a full interactive terminal application built with `rich` and native Apple Silicon Metal GPU acceleration:

```
╭──────────────────────────────────────────────────────────────────────────────╮
│  🎧 AUDIOBOOK STUDIO — Apple Silicon Metal GPU Accelerated                   │
│  Transform your PDF & EPUB library into chaptered M4B audiobooks on-demand   │
╰──────────────────────────────────────────────────────────────────────────────╯
╭────┬────────┬────────────────────────┬──────────┬────────────────┬───────────────────────────╮
│  # │  Type  │ Title / Book Name      │     Size │   Audiobook    │ Pipeline Workflow         │
├────┼────────┼────────────────────────┼──────────┼────────────────┼───────────────────────────┤
│  1 │ [EPUB] │ Python Illustrated     │  28.1 MB │ ✓ Ready (.m4b) │ 1) Direct TTS synthesis   │
│  2 │  [PDF] │ Additive Manufacturing │  19.3 MB │ ✓ Ready (.m4b) │ 2) Extract -> EPUB -> TTS │
│  3 │  [PDF] │ astronomy 2e           │ 154.1 MB │ ✓ Ready (.m4b) │ 2) Extract -> EPUB -> TTS │
...
```

### 4.1. Core Capabilities & Pipeline Differentiation
1. **Interactive Book Picker**:
   * Invoking `make_audiobook` with no arguments opens the library menu.
   * Supports selection by row number (e.g. `1`), title search (`"Python"`), or custom file path / drag-and-drop from Finder.
2. **Format-Aware Pipeline**:
   * **`[EPUB]`**: Direct TTS pipeline. Directly extracts the EPUB document structure, chapter outlines, and text content for immediate Kokoro TTS synthesis with zero intermediate re-encoding.
   * **`[PDF]`**: Two-step pipeline. Step 1 cleans the PDF text layer (stripping running headers, footers, page numbers, footnotes), writing a clean `.epub` file (`~/Documents/AudioBook/<Book>.epub`). Step 2 feeds the chapter outline into Kokoro TTS.
3. **Custom & Baked-in Destination Directory**:
   * Prompts the user: `Save audiobooks to [~/Documents/AudioBook]:`
   * Pressing <kbd>Enter</kbd> keeps the baked-in default; typing/pasting any custom path saves there.
4. **Interactive Narrator Voice Selector**:
   * Shows a curated table of 10 Kokoro voices across American and British accents with timbre and pacing notes.
5. **Full-CMD Live Dashboard**:
   * **Header Panel**: Book metadata, Apple Metal GPU shader telemetry, narrator voice, speed, format, destination.
   * **Synthesis Telemetry**: Dual progress bars — Overall Book progress (percentage, chapter count, elapsed time, ETA) and Current Chapter chunk progress.
   * **Completed Chapters Log**: Compact live table with chapter titles, durations, sizes, and completion ticks.
6. **M4B Container Packaging**:
   * Uses `ffmpeg` to embed chapter bookmarks and ID3/QuickTime metadata into `.m4b` containers compatible with Apple Books, QuickTime Player, and VLC.
7. **On-Demand GPU Server Lifecycle**:
   * Automatically starts the native Apple Metal GPU server (`port 8001`) when synthesis begins and cleanly terminates it on exit or cancellation.

### 4.2. CLI Usage Reference

```bash
# Launch interactive Studio App:
make_audiobook

# Quick run by book number:
make_audiobook 4

# Quick run with specific voice:
make_audiobook 4 bella                      # Female storytelling (Bella)
make_audiobook 4 adam                       # Deep male narrator (Adam)
make_audiobook 4:george                     # Colon syntax (George)

# List library status table:
make_audiobook --list

# View curated voice catalog:
make_audiobook --voices

# Dry run (analyzes chapters & writes EPUB without synthesizing audio):
make_audiobook 8 --dry-run
```

---

## 5. Quick Monitoring & Verification Commands

```bash
# Launch the interactive audiobook studio:
make_audiobook

# Check generated audiobooks:
ls -lh ~/Documents/AudioBook/

# Check Kokoro GPU server health:
curl -s http://localhost:8001/health

# Check Speaches Docker container health (Odysseus):
curl -s http://localhost:8000/health
```
