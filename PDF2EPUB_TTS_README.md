# PDF to Chaptered M4U Audiobook & EPUB Converter (`pdf2epub_tts.py`)

A high-performance CLI tool that transforms raw PDFs into clean, beautifully chaptered **`.m4u` / `.m4b` / `.mp3` audiobooks** powered by your local **Kokoro-82M TTS** running in Docker, as well as clean **EPUB** eBooks.

---

## Features

- **Local Docker Kokoro TTS Integration**: Connects directly to the Speaches Docker container (`http://localhost:8000/v1`) using the OpenAI-compatible speech endpoint.
- **True Chaptered Audiobooks (`.m4u` / `.m4b`)**: Automatically generates an `FFMETADATA1` chapter track and embeds iPod/M4B chapter atoms (`chpl`) using `ffmpeg`. Works seamlessly in Apple Books, VLC, and BookPlayer with chapter titles, jump points, and progress tracking.
- **Intelligent Text & Layout Cleaning**:
  - Automatically detects and removes repeating running headers, footers, and page numbers.
  - Reassembles words hyphenated across line breaks and joins hard-wrapped lines into natural flowing paragraphs.
  - Cleans ligatures, soft hyphens, zero-width characters, drop caps, bullet symbols, and dot-leader table of contents lines.
  - Optionally strips URLs, footnote text, and citation brackets (`[1]`, `[2, 3]`).
- **Parallel Synthesis**: Synthesizes chapter audio chunks concurrently using multi-threading (default: 4 workers) for maximum throughput.
- **Automatic Environment Detection**: If run under global Python without required packages, it automatically re-executes itself inside the Odysseus virtual environment (`~/Documents/Docker/Odysseus/.venv`).

---

## Prerequisites

1. **Speaches / Kokoro Docker Container**:
   Make sure the container is running on port 8000:
   ```bash
   docker ps | grep speaches
   ```
2. **ffmpeg**:
   Used for audio chunk merging and chapter metadata injection (`brew install ffmpeg`).

---

## Configured Directories

- **Books Library**: `~/Documents/Books` (contains your PDFs and EPUBs)
- **AudioBook Destination**: `~/Documents/AudioBook` (where all `.m4u` files are created by default)

---

## Quick Start & Usage Examples

### 1. View Your Library & Audio Status
Running the script with no arguments or `--list` shows all books, file sizes, and whether the audiobook is already made:
```bash
python3 ~/Documents/pdf2epub_tts.py --list
```
Output:
```text
📚 Available Books in ~/Documents/Books:
  #  Title / Filename                                                       Size  Audio (.m4u)
-----------------------------------------------------------------------------------------------
  1. __Comprehensive Guide to Electronics and Communication Enginee...     1.2MB  —
  2. _OceanofPDF.com_Python_Illustrated_-_Maaike_van_Putten.epub          28.1MB  —
  3. Additive_Manufacturing_Essentials_-_WEB.pdf                          19.3MB  —
  ...
  6. Finding 1_ GATE 2026 Results and Scorecards.pdf                       2.0MB  ✓ Ready
```

---

### 2. Convert Any Book by Number or Name
You don't need to specify output paths or full file paths. The script automatically looks in `~/Documents/Books` and writes to `~/Documents/AudioBook`:

```bash
# Convert by book number from the list
python3 ~/Documents/pdf2epub_tts.py 1

# Convert by title search
python3 ~/Documents/pdf2epub_tts.py "Python"

# Convert and immediately play aloud via macOS afplay
python3 ~/Documents/pdf2epub_tts.py "GATE" --play

---

### 3. Batch Convert All Pending Books
To convert all books in `~/Documents/Books` sequentially into `~/Documents/AudioBook` (automatically skipping books that are already converted):
```bash
python3 ~/Documents/pdf2epub_tts.py --all
```
* Use `--force` to re-convert already synthesized audiobooks.
* Use `--voice <voice>` to select the voice for the entire batch.
```

---

### 3. Test Run on Specific Pages
Great for previewing voice and speed:
```bash
python3 ~/Documents/pdf2epub_tts.py "GATE" --pages 1-3 --play
```

---

### 4. Recommended Production Command for Books & Papers
Cleans front matter, footnote text, citations, and synthesizes at 4x concurrency:
```bash
python3 ~/Documents/pdf2epub_tts.py "book.pdf" \
  --skip-front \
  --strip-citations \
  --drop-footnotes \
  --voice af_sky \
  --speed 1.0 \
  --concurrency 4
```

---

### 4. Create Both EPUB and M4U Audiobook Simultaneously
```bash
python3 ~/Documents/pdf2epub_tts.py "book.pdf" -o "book.m4u" --epub
```
Generates `book.m4u` (chaptered audio) and `book.epub` (clean ebook) side-by-side.

---

## Available Kokoro Voices

Pass any voice name with `--voice <name>`:

| Voice ID | Gender / Accent | Character & Style |
| :--- | :--- | :--- |
| `af_sky` *(default)* | Female (American) | Expressive, clear, modern |
| `af_heart` | Female (American) | Warm, gentle, audiobook narrator |
| `af_bella` | Female (American) | Soft, intimate narration |
| `am_adam` | Male (American) | Deep, steady, authoritative |
| `bf_emma` | Female (British) | Crisp, refined storytelling |
| `bm_george` | Male (British) | Classic British narrator |

Example:
```bash
python3 ~/Documents/pdf2epub_tts.py "book.pdf" -o "book.m4u" --voice bm_george --speed 1.1
```

---

## Command Line Reference

```text
usage: pdf2epub_tts.py [-h] [-o OUTPUT] [--title TITLE] [--author AUTHOR]
                       [--lang LANG] [--pages PAGES] [--min-words MIN_WORDS]
                       [--max-words MAX_WORDS] [--strip-urls]
                       [--strip-citations] [--keep-headers] [--drop-footnotes]
                       [--skip-front] [--keep-all-sections] [--sort]
                       [--dump-text DUMP_TEXT] [--audio]
                       [--audio-format {m4u,m4b,m4a,mp3}] [--voice VOICE]
                       [--speed SPEED] [--endpoint ENDPOINT] [--model MODEL]
                       [--concurrency CONCURRENCY] [--keep-chapters] [--play]
                       [--epub]
                       pdf
```

### Core Options:
| Flag | Description |
| :--- | :--- |
| `pdf` | Path to the input PDF file. |
| `-o, --output` | Output path (`.m4u`, `.m4b`, `.mp3`, or `.epub`). |
| `--pages` | Page range to convert (e.g. `1-10` or `15-150`). |
| `--title` / `--author` | Metadata overrides (defaults to PDF metadata or filename). |
| `--epub` | Also generate `.epub` when synthesizing audio. |

### Text Cleaning Options:
| Flag | Description |
| :--- | :--- |
| `--skip-front` | Discards front matter before Chapter 1 (title page, copyright, table of contents). |
| `--strip-citations` | Strips bracketed citations (e.g. `[1]`, `[12, 14]`). |
| `--drop-footnotes` | Removes small-print footnote lines at the bottom of pages. |
| `--strip-urls` | Removes raw web links from spoken narration. |
| `--keep-headers` | Disables automatic removal of running headers/footers. |
| `--sort` | Forces top-to-bottom layout sorting for complex multi-column PDFs. |
| `--dump-text <file>` | Writes the cleaned extracted text to a `.txt` file for inspection. |

### Audio Synthesis Options:
| Flag | Description |
| :--- | :--- |
| `--voice` | Voice ID (e.g. `af_sky`, `af_heart`, `bf_emma`, `am_adam`; default: `af_sky`). |
| `--speed` | Speech speed multiplier (e.g. `1.0`, `1.15`; default: `1.0`). |
| `--endpoint` | Kokoro/Speaches API endpoint (default: `http://localhost:8000/v1`). |
| `--concurrency` | Number of simultaneous HTTP synthesis workers (default: `4`). |
| `--keep-chapters` | Retains individual per-chapter `.mp3` files alongside the master `.m4u`. |
| `--play` | Automatically plays the finished file using macOS `afplay`. |

---

## How It Works

```
                     ┌─────────────────────────────┐
                     │          Input PDF          │
                     └──────────────┬──────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │ PyMuPDF Geometry Extraction │
                     │   - Header/footer removal   │
                     │   - Hyphen reassembly       │
                     │   - Footnote & citation drop│
                     └──────────────┬──────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │     Chapter Detection       │
                     │ (TOC outline / Headings)    │
                     └──────────────┬──────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
                  ▼                                   ▼
       ┌────────────────────┐               ┌────────────────────┐
       │   Clean .EPUB      │               │   TTS Chunking     │
       │  (Single or Multi- │               │ (<600 char clauses)│
       │    file book)      │               └─────────┬──────────┘
       └────────────────────┘                         │
                                                      ▼
                                            ┌────────────────────┐
                                            │ Docker Speaches    │
                                            │ Kokoro-82M API     │
                                            │ (Concurrent HTTP)  │
                                            └─────────┬──────────┘
                                                      │
                                                      ▼
                                            ┌────────────────────┐
                                            │      FFmpeg        │
                                            │ - Concat Chunks    │
                                            │ - Inject Metadata  │
                                            │ - Write .M4U / .M4B│
                                            └────────────────────┘
```
