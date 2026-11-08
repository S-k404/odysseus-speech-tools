#!/usr/bin/env python3
"""
narrator.py — High-Performance Universal Document Reader & Narration Engine.

Powered by Speaches (Kokoro-82M ONNX) local audio server.
Supports:
  - PDF (.pdf)
  - Markdown (.md, .markdown)
  - EPUB (.epub)
  - Plain Text (.txt)

Features:
  - Intelligent sentence and paragraph chunking tailored for Kokoro-82M prosody.
  - Cleans PDF headers, footers, and page artifacts.
  - Formats Markdown (strips code fences, transforms links, pauses on headings).
  - Native EPUB chapter extraction using zipfile and BeautifulSoup.
  - MP3 frame concatenation for seamless audiobook generation.
  - Live system playback on macOS via afplay.
"""

import os
import sys
import re
import io
import time
import zipfile
import argparse
import subprocess
import urllib.request
import urllib.error
import json
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

# Optional libraries with fallbacks
try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    import warnings
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    BeautifulSoup = None

DEFAULT_SPEACHES_URL = os.getenv("SPEACHES_BASE_URL", "http://localhost:8000/v1")
DEFAULT_MODEL = os.getenv("SPEACHES_TTS_MODEL", "speaches-ai/Kokoro-82M-v1.0-ONNX")
DEFAULT_VOICE = os.getenv("SPEACHES_TTS_VOICE", "af_heart")
DEFAULT_SPEED = 1.0
TARGET_CHUNK_CHARS = 500  # Optimal chunk size for Kokoro prosody & natural cadence


# ==============================================================================
# 1. Document Extractors
# ==============================================================================

class DocumentExtractor:
    """Extracts and cleans readable text from diverse document formats."""

    @staticmethod
    def extract_text(file_path: str, start_page: int = 1, end_page: Optional[int] = None) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return DocumentExtractor.extract_from_pdf(path, start_page, end_page)
        elif suffix in (".md", ".markdown"):
            return DocumentExtractor.extract_from_markdown(path)
        elif suffix == ".epub":
            return DocumentExtractor.extract_from_epub(path)
        elif suffix in (".txt", ".text", ".rst", ".log"):
            return DocumentExtractor.extract_from_txt(path)
        else:
            # Fallback to plain text read
            return DocumentExtractor.extract_from_txt(path)

    @staticmethod
    def extract_from_pdf(path: Path, start_page: int = 1, end_page: Optional[int] = None) -> str:
        """Extract and clean text from PDF using PyMuPDF or pypdf fallback."""
        text_parts = []

        if fitz is not None:
            doc = fitz.open(str(path))
            total_pages = len(doc)
            last_page = min(end_page or total_pages, total_pages)
            first_page = max(1, start_page)

            print(f"[Extractor] Reading PDF '{path.name}' (pages {first_page} to {last_page} of {total_pages})...")

            for page_num in range(first_page - 1, last_page):
                page = doc[page_num]
                page_text = page.get_text("text")
                cleaned = DocumentExtractor._clean_pdf_page_text(page_text)
                if cleaned:
                    text_parts.append(cleaned)
            doc.close()
        else:
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                total_pages = len(reader.pages)
                last_page = min(end_page or total_pages, total_pages)
                first_page = max(1, start_page)

                for page_num in range(first_page - 1, last_page):
                    page = reader.pages[page_num]
                    page_text = page.extract_text() or ""
                    cleaned = DocumentExtractor._clean_pdf_page_text(page_text)
                    if cleaned:
                        text_parts.append(cleaned)
            except ImportError:
                raise RuntimeError("Neither PyMuPDF ('pymupdf') nor pypdf is installed for PDF parsing.")

        raw_content = "\n\n".join(text_parts)
        return DocumentExtractor._normalize_extracted_text(raw_content)

    @staticmethod
    def _clean_pdf_page_text(page_text: str) -> str:
        """Clean running headers, footers, standalone page numbers, and soft hyphens."""
        lines = page_text.splitlines()
        filtered = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            # Filter solitary page numbers (e.g. '1', '12', 'Page 4 of 20')
            if re.match(r"^(?:page\s+)?\d+(?:\s+of\s+\d+)?$", line_str, re.IGNORECASE):
                continue
            filtered.append(line_str)

        text = "\n".join(filtered)
        # De-hyphenate words broken across lines: e.g. "com-\nputer" -> "computer"
        text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
        # Convert single newlines into spaces, preserving paragraph breaks
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
        return text

    @staticmethod
    def extract_from_markdown(path: Path) -> str:
        """Extract clean narrative text from Markdown, stripping code and formatting."""
        raw = path.read_text(encoding="utf-8", errors="replace")

        # 1. Strip YAML frontmatter
        raw = re.sub(r"^---[\s\S]*?---\n", "", raw)

        # 2. Strip HTML comments
        raw = re.sub(r"<!--[\s\S]*?-->", "", raw)

        # 3. Strip or transform code blocks
        # Replace fenced code blocks with a brief pause note so narration flows naturally
        raw = re.sub(r"```[\w]*\n[\s\S]*?\n```", "\n[Code block omitted.]\n", raw)
        # Replace inline code `foo` with foo
        raw = re.sub(r"`([^`]+)`", r"\1", raw)

        # 4. Convert markdown links [Text](URL) -> Text
        raw = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw)

        # 5. Remove image tags ![alt](url) -> ""
        raw = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", raw)

        # 6. Transform headings to sentences with ending punctuation for voice cadence
        def _heading_repl(match):
            heading_text = match.group(2).strip()
            if heading_text and not heading_text.endswith((".", "!", "?", ":")):
                return f"\n\n{heading_text}.\n\n"
            return f"\n\n{heading_text}\n\n"

        raw = re.sub(r"^(#{1,6})\s+(.+)$", _heading_repl, raw, flags=re.MULTILINE)

        # 7. Convert bullet points (- item, * item) into punctuated pauses
        raw = re.sub(r"^[\*\-\+]\s+", "", raw, flags=re.MULTILINE)

        # 8. Clean bold/italic asterisks & underscores
        raw = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", raw)

        return DocumentExtractor._normalize_extracted_text(raw)

    @staticmethod
    def extract_from_epub(path: Path) -> str:
        """Extract chapters and text from EPUB using built-in zipfile and BeautifulSoup."""
        print(f"[Extractor] Reading EPUB '{path.name}'...")
        chapters_text = []

        with zipfile.ZipFile(str(path), "r") as z:
            # Locate container.xml to find the root OPF file
            rootfile_path = None
            try:
                container_data = z.read("META-INF/container.xml")
                if BeautifulSoup:
                    soup = BeautifulSoup(container_data, "html.parser")
                    rootfile = soup.find("rootfile")
                    if rootfile and rootfile.get("full-path"):
                        rootfile_path = rootfile["full-path"]
            except Exception:
                pass

            # Gather all html / xhtml files
            html_files = [f for f in z.namelist() if f.lower().endswith((".xhtml", ".html", ".htm"))]
            html_files.sort()

            for hf in html_files:
                data = z.read(hf).decode("utf-8", errors="replace")
                if BeautifulSoup:
                    soup = BeautifulSoup(data, "html.parser")
                    # Remove script, style, and navigation elements
                    for tag in soup(["script", "style", "nav", "header", "footer"]):
                        tag.extract()

                    # Extract paragraphs and headings
                    text_blocks = []
                    for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"]):
                        txt = elem.get_text().strip()
                        if txt:
                            if elem.name.startswith("h") and not txt.endswith((".", "!", "?")):
                                txt += "."
                            text_blocks.append(txt)

                    if text_blocks:
                        chapters_text.append("\n\n".join(text_blocks))
                else:
                    # Regex fallback if bs4 is missing
                    clean = re.sub(r"<[^>]+>", " ", data)
                    clean = re.sub(r"\s+", " ", clean).strip()
                    if clean:
                        chapters_text.append(clean)

        raw_content = "\n\n".join(chapters_text)
        return DocumentExtractor._normalize_extracted_text(raw_content)

    @staticmethod
    def extract_from_txt(path: Path) -> str:
        """Extract plain text with encoding auto-detection fallback."""
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = path.read_text(encoding="latin-1", errors="replace")
        return DocumentExtractor._normalize_extracted_text(raw)

    @staticmethod
    def _normalize_extracted_text(text: str) -> str:
        """Clean up multiple whitespaces, extraneous blank lines, and non-printable characters."""
        # Replace non-breaking spaces
        text = text.replace("\xa0", " ").replace("\u200b", "")
        # Normalize multiple spaces
        text = re.sub(r"[ \t]+", " ", text)
        # Normalize multiple newlines (keep max 2 for paragraph separation)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()


# ==============================================================================
# 2. Sentence & Prosody Chunking Engine
# ==============================================================================

class TextChunker:
    """Chunks long documents into natural, prosody-aware segments for Kokoro-82M."""

    # Abbreviations that should NOT trigger a sentence split
    ABBREVIATIONS = re.compile(
        r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|Fig|Vol|No|Jan|Feb|Mar|Apr|Aug|Sept?|Oct|Nov|Dec)\.$",
        re.IGNORECASE,
    )

    @classmethod
    def chunk(cls, text: str, max_chunk_chars: int = TARGET_CHUNK_CHARS) -> List[str]:
        """Split text into sentence-bounded chunks of maximum specified length."""
        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            sentences = cls._split_into_sentences(para)

            for sentence in sentences:
                sentence_len = len(sentence)

                if current_length + sentence_len + 1 <= max_chunk_chars:
                    current_chunk.append(sentence)
                    current_length += sentence_len + 1
                else:
                    if current_chunk:
                        chunks.append(" ".join(current_chunk))
                        current_chunk = []
                        current_length = 0

                    if sentence_len > max_chunk_chars:
                        # Sentence itself exceeds limit; split on clauses or commas
                        sub_parts = cls._split_long_sentence(sentence, max_chunk_chars)
                        for part in sub_parts:
                            chunks.append(part)
                    else:
                        current_chunk.append(sentence)
                        current_length = sentence_len

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return [c.strip() for c in chunks if c.strip()]

    @classmethod
    def _split_into_sentences(cls, paragraph: str) -> List[str]:
        """Split paragraph into sentences while respecting common abbreviations."""
        raw_splits = re.split(r"(?<=[.!?])\s+", paragraph)
        sentences: List[str] = []
        buffer = ""

        for part in raw_splits:
            part = part.strip()
            if not part:
                continue

            if buffer:
                buffer += " " + part
            else:
                buffer = part

            # Check if buffer ends with an abbreviation
            if cls.ABBREVIATIONS.search(buffer):
                continue

            sentences.append(buffer)
            buffer = ""

        if buffer:
            sentences.append(buffer)

        return sentences

    @classmethod
    def _split_long_sentence(cls, sentence: str, max_chars: int) -> List[str]:
        """Split exceptionally long sentences at clauses, semicolons, or commas."""
        clause_parts = re.split(r"(?<=[,;:—])\s+", sentence)
        result: List[str] = []
        curr = ""

        for part in clause_parts:
            if len(curr) + len(part) + 1 <= max_chars:
                curr = f"{curr} {part}".strip()
            else:
                if curr:
                    result.append(curr)
                curr = part

        if curr:
            result.append(curr)

        return result


# ==============================================================================
# 3. Speaches Audio Synthesizer & Stitcher
# ==============================================================================

class SpeachesSynthesizer:
    """Communicates with the Speaches Kokoro-82M API to synthesize audio chunks."""

    def __init__(
        self,
        base_url: str = DEFAULT_SPEACHES_URL,
        model: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
    ):
        self.base_url = base_url.rstrip("/")
        self.speech_url = f"{self.base_url}/audio/speech"
        self.model = model
        self.voice = voice
        self.speed = speed

    def synthesize_chunk(self, text: str) -> bytes:
        """Synthesize a single text chunk into MP3 audio bytes."""
        payload = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": "mp3",
            "speed": self.speed,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.speech_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    if resp.status == 200:
                        return resp.read()
                    raise RuntimeError(f"Speaches returned HTTP {resp.status}")
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP Error {e.code}: {err_msg}")
            except Exception as e:
                if attempt == 3:
                    raise RuntimeError(f"Failed to synthesize after 3 attempts: {e}")
                time.sleep(1)

        raise RuntimeError("Synthesis failed unexpectedly.")


# ==============================================================================
# 4. High-Level Document Narrator Engine
# ==============================================================================

class DocumentNarrator:
    """High-level narrator orchestrator."""

    def __init__(
        self,
        base_url: str = DEFAULT_SPEACHES_URL,
        model: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
    ):
        self.synthesizer = SpeachesSynthesizer(base_url, model, voice, speed)

    def narrate_document(
        self,
        file_path: str,
        output_path: Optional[str] = None,
        start_page: int = 1,
        end_page: Optional[int] = None,
        play_live: bool = False,
    ) -> str:
        """Narrate a document end-to-end, producing an audio file."""
        input_path = Path(file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {file_path}")

        # Default output path: same basename with .mp3
        if not output_path:
            output_path = str(input_path.with_suffix(".mp3"))

        print(f"\n[Narrator] Processing document: {input_path.name}")
        t0 = time.time()

        # Step 1: Extract Text
        text = DocumentExtractor.extract_text(str(input_path), start_page, end_page)
        print(f"[Narrator] Extracted {len(text)} characters.")

        if not text.strip():
            raise ValueError("No readable text found in the document.")

        # Step 2: Chunk Text
        chunks = TextChunker.chunk(text)
        print(f"[Narrator] Segmented into {len(chunks)} speech chunks for Kokoro prosody.")

        # Step 3: Synthesize and Stitch
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        audio_parts: List[bytes] = []

        print(f"[Narrator] Synthesizing audio via Speaches (Voice: {self.synthesizer.voice})...")
        for i, chunk in enumerate(chunks, 1):
            pct = int((i / len(chunks)) * 100)
            snippet = chunk[:45].replace("\n", " ") + ("..." if len(chunk) > 45 else "")
            print(f"  [{i:3d}/{len(chunks):3d}] ({pct:2d}%) Narrating: \"{snippet}\"")
            audio_bytes = self.synthesizer.synthesize_chunk(chunk)
            audio_parts.append(audio_bytes)

        # Concatenate MP3 frames
        full_audio = b"".join(audio_parts)
        out_file.write_bytes(full_audio)

        elapsed = time.time() - t0
        file_size_mb = len(full_audio) / (1024 * 1024)
        print(f"\n[Narrator] SUCCESS! Saved {file_size_mb:.2f} MB audio to: {out_file.resolve()}")
        print(f"[Narrator] Total time: {elapsed:.2f}s ({len(chunks) / elapsed:.1f} chunks/sec)\n")

        # Step 4: Optional live playback (macOS afplay)
        if play_live:
            self.play_audio(str(out_file))

        return str(out_file)

    @staticmethod
    def play_audio(audio_path: str):
        """Play audio file using macOS native afplay."""
        if sys.platform == "darwin":
            print(f"[Narrator] Playing audio aloud via macOS afplay: {audio_path}")
            try:
                subprocess.run(["afplay", audio_path], check=True)
            except KeyboardInterrupt:
                print("\n[Narrator] Playback interrupted.")
            except Exception as e:
                print(f"[-] Playback error: {e}")
        else:
            print(f"[-] Live playback not supported natively on {sys.platform}. Use an audio player to open {audio_path}")


# ==============================================================================
# 5. CLI Entrypoint
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Universal Document Reader & Narration Engine using Speaches Kokoro-82M."
    )
    parser.add_argument("file", help="Path to document file (.pdf, .md, .epub, .txt)")
    parser.add_argument("-o", "--output", help="Output audio file path (.mp3). Default: <input_stem>.mp3")
    parser.add_argument("-v", "--voice", default=DEFAULT_VOICE, help=f"Kokoro voice ID (default: {DEFAULT_VOICE})")
    parser.add_argument("-s", "--speed", type=float, default=DEFAULT_SPEED, help="Speech speed (e.g. 1.0, 1.15)")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Model ID (default: Kokoro-82M ONNX)")
    parser.add_argument("--url", default=DEFAULT_SPEACHES_URL, help="Speaches API base URL")
    parser.add_argument("--start-page", type=int, default=1, help="Start page (PDF only)")
    parser.add_argument("--end-page", type=int, default=None, help="End page (PDF only)")
    parser.add_argument("-p", "--play", action="store_true", help="Play audio aloud after synthesis")

    args = parser.parse_args()

    narrator = DocumentNarrator(
        base_url=args.url,
        model=args.model,
        voice=args.voice,
        speed=args.speed,
    )

    try:
        narrator.narrate_document(
            file_path=args.file,
            output_path=args.output,
            start_page=args.start_page,
            end_page=args.end_page,
            play_live=args.play,
        )
    except Exception as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
