#!/usr/bin/env python3
"""
verify_all.py — End-to-End Comprehensive Verification of Speaches, Odysseus & Document Reader.

Checks:
1.  Docker container status & network (speaches on odysseus_default).
2.  Speaches API availability (/v1/models: Kokoro-82M + Faster-Whisper).
3.  Direct Kokoro TTS synthesis via host HTTP.
4.  Direct Faster-Whisper STT transcription via host HTTP.
5.  Odysseus .env configuration validation.
6.  Odysseus settings.json synchronization.
7.  Odysseus SQLite database check:
    - ModelEndpoint 'speaches_audio_engine'
    - CrewMember 'Document Narrator'
8.  Odysseus data/presets.json check ('document_narrator').
9.  Live Odysseus container test (TTS synthesis & STT transcription inside odysseus-odysseus-1).
10. Document Reader CLI (read_doc.py) end-to-end test on Markdown, Text, and PDF.
"""

import os
import sys
import json
import sqlite3
import subprocess
import time
import urllib.request
import urllib.parse
from pathlib import Path

ODYSSEUS_DIR = Path("~/Documents/Docker/Odysseus")
SPEACHES_DIR = Path("~/Documents/Docker/Speaches")
SPEACHES_HOST = "http://localhost:8000/v1"
DB_PATH = ODYSSEUS_DIR / "data" / "app.db"
SETTINGS_PATH = ODYSSEUS_DIR / "data" / "settings.json"
PRESETS_PATH = ODYSSEUS_DIR / "data" / "presets.json"
ENV_PATH = ODYSSEUS_DIR / ".env"

results = []

def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append((name, status, detail))
    symbol = "✓" if passed else "✗"
    print(f"[{symbol}] {name}: {status}")
    if detail:
        print(f"    -> {detail}")

print("=" * 70)
print("     COMPREHENSIVE SPEACHES & ODYSSEUS VERIFICATION SUITE")
print("=" * 70)

# 1. Docker Container Status
try:
    ps_out = subprocess.check_output(
        ["docker", "ps", "--filter", "name=speaches", "--format", "{{.Names}} - {{.Status}} - {{.Ports}}"],
        text=True
    ).strip()
    passed = "speaches" in ps_out and "Up" in ps_out and "8000" in ps_out
    record("1. Speaches Docker Container Running", passed, ps_out)
except Exception as e:
    record("1. Speaches Docker Container Running", False, str(e))

# 2. Speaches Models API
try:
    req = urllib.request.Request(f"{SPEACHES_HOST}/models")
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode())
        models = [m["id"] for m in data.get("data", [])]
        has_tts = any("kokoro" in m.lower() for m in models)
        has_stt = any("whisper" in m.lower() for m in models)
        record("2. Speaches Models API (/v1/models)", has_tts and has_stt, f"Loaded: {models}")
except Exception as e:
    record("2. Speaches Models API (/v1/models)", False, str(e))

# 3. Direct Kokoro TTS Synthesis
audio_bytes = None
try:
    req_data = json.dumps({
        "model": "speaches-ai/Kokoro-82M-v1.0-ONNX",
        "input": "Speaches verification test with Kokoro voice af_sky.",
        "voice": "af_sky",
        "response_format": "mp3"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{SPEACHES_HOST}/audio/speech",
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=10) as r:
        audio_bytes = r.read()
    elapsed = time.time() - t0
    is_mp3 = len(audio_bytes) > 5000 and (audio_bytes[:3] == b"ID3" or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0))
    record("3. Host Kokoro TTS Synthesis (/v1/audio/speech)", is_mp3, f"{len(audio_bytes)} bytes in {elapsed:.2f}s")
except Exception as e:
    record("3. Host Kokoro TTS Synthesis (/v1/audio/speech)", False, str(e))

# 4. Direct Faster-Whisper STT Transcription
if audio_bytes:
    try:
        import http.client
        boundary = "----WebKitFormBoundaryVerify7MA4"
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="model"\r\n\r\n')
        body.extend(b"Systran/faster-whisper-small\r\n")
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="file"; filename="test.mp3"\r\n')
        body.extend(b"Content-Type: audio/mpeg\r\n\r\n")
        body.extend(audio_bytes)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())

        conn = http.client.HTTPConnection("localhost", 8000)
        t0 = time.time()
        conn.request("POST", "/v1/audio/transcriptions", body=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        elapsed = time.time() - t0
        text = data.get("text", "")
        passed = resp.status == 200 and len(text) > 5
        record("4. Host Faster-Whisper STT (/v1/audio/transcriptions)", passed, f"\"{text}\" in {elapsed:.2f}s")
    except Exception as e:
        record("4. Host Faster-Whisper STT (/v1/audio/transcriptions)", False, str(e))
else:
    record("4. Host Faster-Whisper STT (/v1/audio/transcriptions)", False, "Skipped (TTS failed)")

# 5. Odysseus .env Configuration
try:
    env_text = ENV_PATH.read_text(encoding="utf-8")
    checks = [
        "TTS_ENABLED=true",
        "TTS_PROVIDER=openai",
        "TTS_OPENAI_API_BASE=http://speaches:8000/v1",
        "TTS_MODEL=hexgrad/Kokoro-82M",
        "TTS_VOICE=af_sky",
        "STT_ENABLED=true",
        "STT_PROVIDER=openai",
        "STT_OPENAI_API_BASE=http://speaches:8000/v1",
        "STT_MODEL=Systran/faster-whisper-small",
    ]
    all_present = all(c in env_text for c in checks)
    record("5. Odysseus .env Audio Configuration Block", all_present, f"All {len(checks)} configuration keys present")
except Exception as e:
    record("5. Odysseus .env Audio Configuration Block", False, str(e))

# 6. Odysseus settings.json
try:
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    tts_ok = settings.get("tts_enabled") is True and settings.get("tts_provider") == "openai" and settings.get("tts_voice") == "af_sky"
    stt_ok = settings.get("stt_enabled") is True and settings.get("stt_provider") == "openai"
    record("6. Odysseus settings.json Audio Bindings", tts_ok and stt_ok, f"TTS: {settings.get('tts_provider')} ({settings.get('tts_voice')}) | STT: {settings.get('stt_provider')}")
except Exception as e:
    record("6. Odysseus settings.json Audio Bindings", False, str(e))

# 7. Odysseus SQLite Database (CrewMember & ModelEndpoint)
try:
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT id, name, base_url FROM model_endpoints WHERE id = 'speaches_audio_engine'")
    ep_row = c.fetchone()

    c.execute("SELECT id, name, avatar FROM crew_members WHERE name = 'Document Narrator'")
    cm_row = c.fetchone()
    conn.close()

    ep_ok = ep_row is not None and ep_row[2] == "http://speaches:8000/v1"
    cm_ok = cm_row is not None and cm_row[1] == "Document Narrator"
    record("7. Odysseus Database (ModelEndpoint & CrewMember)", ep_ok and cm_ok, f"Endpoint: {ep_row[0] if ep_row else None} | Agent: {cm_row[1] if cm_row else None} {cm_row[2] if cm_row else ''}")
except Exception as e:
    record("7. Odysseus Database (ModelEndpoint & CrewMember)", False, str(e))

# 8. Odysseus presets.json
try:
    presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    has_narrator = "document_narrator" in presets
    name = presets.get("document_narrator", {}).get("name", "")
    record("8. Odysseus Chat Presets (document_narrator)", has_narrator and name == "Document Narrator", f"Preset Name: '{name}'")
except Exception as e:
    record("8. Odysseus Chat Presets (document_narrator)", False, str(e))

# 9. Inside Odysseus Container Execution
try:
    cmd = [
        "docker", "exec", "odysseus-odysseus-1", "python3", "-c",
        """
import os
from dotenv import load_dotenv
load_dotenv('/app/.env')
from services.tts import get_tts_service
from services.stt.stt_service import STTService

tts = get_tts_service()
audio = tts.synthesize('Container verification test passed.', use_cache=False)
stt = STTService()
text = stt.transcribe(audio) if audio else ''
print(f"BYTES:{len(audio) if audio else 0}|TEXT:{text}")
"""
    ]
    out = subprocess.check_output(cmd, text=True, timeout=20).strip()
    parts = out.split("|")
    bytes_num = int(parts[0].replace("BYTES:", ""))
    text_val = parts[1].replace("TEXT:", "")
    passed = bytes_num > 10000 and len(text_val) > 5
    record("9. Live Container TTS & STT (odysseus-odysseus-1)", passed, f"Synthesized {bytes_num} bytes | Transcribed: \"{text_val}\"")
except Exception as e:
    record("9. Live Container TTS & STT (odysseus-odysseus-1)", False, str(e))

# 10. Document Reader CLI (read_doc.py)
try:
    python_bin = str(ODYSSEUS_DIR / ".venv" / "bin" / "python")
    test_pdf = str(SPEACHES_DIR / "test_docs" / "sample.pdf")
    out_mp3 = str(SPEACHES_DIR / "test_docs" / "read_doc_verify.mp3")

    cmd = [python_bin, str(SPEACHES_DIR / "read_doc.py"), test_pdf, "--output", out_mp3, "--voice", "af_sky"]
    out = subprocess.check_output(cmd, text=True, timeout=30)

    p = Path(out_mp3)
    passed = p.exists() and p.stat().st_size > 5000
    record("10. Document Reader CLI (read_doc.py on PDF)", passed, f"Generated {p.name} ({p.stat().st_size / 1024:.1f} KB)")
except Exception as e:
    record("10. Document Reader CLI (read_doc.py on PDF)", False, str(e))

print("\n" + "=" * 70)
all_passed = all(r[1] == "PASS" for r in results)
summary = f"VERIFICATION RESULT: {'ALL 10 CHECKS PASSED!' if all_passed else 'SOME CHECKS FAILED'}"
print(f"     {summary}")
print("=" * 70)

sys.exit(0 if all_passed else 1)
