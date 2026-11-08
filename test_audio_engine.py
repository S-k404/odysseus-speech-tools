#!/usr/bin/env python3
"""
test_audio_engine.py — Comprehensive Verification Suite for Speaches, Odysseus & Narrator.

Tests:
1. Speaches API connectivity and loaded models (Kokoro-82M TTS + Faster-Whisper STT).
2. Direct TTS synthesis (synthesize test speech to MP3).
3. Direct STT transcription (transcribe synthesized speech back to text).
4. Multi-format Document Narration:
   - Markdown (.md)
   - Plain Text (.txt)
   - PDF (.pdf)
   - EPUB (.epub)
5. Odysseus Workspace DB & Settings integration check.
"""

import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = os.getenv("SPEACHES_BASE_URL", "http://localhost:8000/v1")
ODYSSEUS_DIR = "~/Documents/Docker/Odysseus"
DB_PATH = os.path.join(ODYSSEUS_DIR, "data", "app.db")
SETTINGS_PATH = os.path.join(ODYSSEUS_DIR, "data", "settings.json")


def report_step(title: str):
    print(f"\n{'='*60}\n--> {title}\n{'='*60}")


def test_speaches_models():
    report_step("1. Verifying Speaches Models Endpoint")
    url = f"{BASE_URL}/models"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        data = json.loads(resp.read().decode())
        models = [m["id"] for m in data.get("data", [])]
        print(f"[✓] Speaches active. Models available: {models}")
        assert any("Kokoro" in m for m in models), "Kokoro model not found in /v1/models"
        assert any("whisper" in m.lower() for m in models), "Whisper model not found in /v1/models"


def test_tts_synthesis():
    report_step("2. Verifying Kokoro-82M TTS Audio Synthesis")
    url = f"{BASE_URL}/audio/speech"
    test_text = "Speaches is now successfully deployed and powering Odysseus audio."
    payload = {
        "model": "speaches-ai/Kokoro-82M-v1.0-ONNX",
        "input": test_text,
        "voice": "af_heart",
        "response_format": "mp3",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        audio_bytes = resp.read()

    elapsed = time.time() - t0
    assert len(audio_bytes) > 5000, f"Audio bytes too small: {len(audio_bytes)}"
    # Verify MP3 sync word or ID3
    is_mp3 = (len(audio_bytes) >= 3 and audio_bytes[:3] == b"ID3") or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0)
    assert is_mp3, "Audio payload does not appear to be valid MP3."

    print(f"[✓] TTS synthesis succeeded: {len(audio_bytes)} bytes in {elapsed:.2f}s (valid MP3).")
    Path("test_docs/test_synthesis.mp3").write_bytes(audio_bytes)
    return audio_bytes


def test_stt_transcription(audio_bytes: bytes):
    report_step("3. Verifying Faster-Whisper STT Audio Transcription")
    import http.client

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = io_body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    body.extend(b"Systran/faster-whisper-small\r\n")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="file"; filename="audio.mp3"\r\n')
    body.extend(b"Content-Type: audio/mpeg\r\n\r\n")
    body.extend(audio_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    parsed = urllib.parse.urlparse(f"{BASE_URL}/audio/transcriptions")
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port)

    t0 = time.time()
    conn.request(
        "POST",
        parsed.path,
        body=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = conn.getresponse()
    resp_data = resp.read().decode()
    elapsed = time.time() - t0

    assert resp.status == 200, f"Transcription failed: {resp.status} {resp_data}"
    result = json.loads(resp_data)
    text = result.get("text", "")
    print(f"[✓] STT transcription succeeded in {elapsed:.2f}s: \"{text}\"")
    assert "Speaches" in text or "Speech" in text or "Odysseus" in text or "audio" in text, f"Transcription content unexpected: {text}"


def test_document_narrator():
    report_step("4. Verifying Universal Document Narrator (PDF, Markdown, EPUB, TXT)")
    from narrator import DocumentNarrator

    narrator = DocumentNarrator(base_url=BASE_URL, voice="af_heart")

    test_files = [
        ("Markdown", "test_docs/sample.md", "test_docs/sample_md.mp3"),
        ("Plain Text", "test_docs/sample.txt", "test_docs/sample_txt.mp3"),
        ("PDF", "test_docs/sample.pdf", "test_docs/sample_pdf.mp3"),
        ("EPUB", "test_docs/sample.epub", "test_docs/sample_epub.mp3"),
    ]

    for fmt_name, in_path, out_path in test_files:
        print(f"\n--- Testing {fmt_name} Narration ({in_path}) ---")
        out = narrator.narrate_document(in_path, output_path=out_path, play_live=False)
        out_p = Path(out)
        assert out_p.exists(), f"Output audio {out} does not exist!"
        assert out_p.stat().st_size > 5000, f"Output audio {out} is suspiciously small: {out_p.stat().st_size} bytes"
        print(f"[✓] {fmt_name} narration verified: {out_p.name} ({out_p.stat().st_size / 1024:.1f} KB)")


def test_odysseus_integration():
    report_step("5. Verifying Odysseus DB & Settings Integration")

    # 1. Verify ModelEndpoint in SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, base_url, is_enabled FROM model_endpoints WHERE id = 'speaches_audio_engine'")
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "ModelEndpoint 'speaches_audio_engine' not found in Odysseus DB"
    assert row[2] == "http://speaches:8000/v1", f"Base URL mismatch: {row[2]}"
    print(f"[✓] Odysseus SQLite ModelEndpoint verified: ID={row[0]} | Name={row[1]} | URL={row[2]}")

    # 2. Verify settings.json
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    assert settings.get("tts_enabled") is True, "tts_enabled is not True in settings.json"
    assert settings.get("tts_provider") == "endpoint:speaches_audio_engine", "tts_provider not bound to Speaches"
    assert settings.get("stt_enabled") is True, "stt_enabled is not True in settings.json"
    assert settings.get("stt_provider") == "endpoint:speaches_audio_engine", "stt_provider not bound to Speaches"

    print(f"[✓] Odysseus settings.json verified:")
    print(f"    TTS Provider: {settings['tts_provider']} ({settings['tts_model']})")
    print(f"    STT Provider: {settings['stt_provider']} ({settings['stt_model']})")


def main():
    print("============================================================")
    print("      SPEACHES & ODYSSEUS AUDIO ENGINE VERIFICATION        ")
    print("============================================================")

    test_speaches_models()
    audio_bytes = test_tts_synthesis()
    test_stt_transcription(audio_bytes)
    test_document_narrator()
    test_odysseus_integration()

    print("\n============================================================")
    print("   ALL TESTS PASSED! SPEACHES ENGINE & NARRATOR ARE READY!  ")
    print("============================================================")


if __name__ == "__main__":
    main()
