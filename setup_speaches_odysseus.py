#!/usr/bin/env python3
"""
setup_speaches_odysseus.py

Configures and registers Speaches (Kokoro-82M TTS + Faster-Whisper STT)
into the Odysseus AI Workspace database (app.db) and settings (settings.json).
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timezone
import urllib.request
import urllib.error

ODYSSEUS_DIR = os.path.expanduser("~/Documents/Docker/Odysseus")
DB_PATH = os.path.join(ODYSSEUS_DIR, "data", "app.db")
SETTINGS_PATH = os.path.join(ODYSSEUS_DIR, "data", "settings.json")

ENDPOINT_ID = "speaches_audio_engine"
ENDPOINT_NAME = "Speaches Audio Engine (Kokoro + Whisper)"
CONTAINER_BASE_URL = "http://speaches:8000/v1"
HOST_BASE_URL = "http://localhost:8000/v1"

TTS_MODEL = "speaches-ai/Kokoro-82M-v1.0-ONNX"
TTS_VOICE = "af_heart"
STT_MODEL = "Systran/faster-whisper-small"


def check_speaches_health(base_url: str = HOST_BASE_URL) -> bool:
    """Check if Speaches API is reachable."""
    try:
        req = urllib.request.Request(f"{base_url}/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("id") for m in data.get("data", [])]
            print(f"[+] Speaches is reachable at {base_url}. Loaded models: {models}")
            return True
    except Exception as e:
        print(f"[-] Warning: Speaches probe at {base_url} failed: {e}")
        return False


def register_model_endpoint():
    """Register or update Speaches in Odysseus SQLite database."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if endpoint already exists
        cursor.execute("SELECT id, name, base_url FROM model_endpoints WHERE id = ?", (ENDPOINT_ID,))
        row = cursor.fetchone()

        if row:
            cursor.execute(
                """
                UPDATE model_endpoints 
                SET name = ?, base_url = ?, is_enabled = 1, updated_at = ?
                WHERE id = ?
                """,
                (ENDPOINT_NAME, CONTAINER_BASE_URL, now, ENDPOINT_ID),
            )
            print(f"[+] Updated existing ModelEndpoint: {ENDPOINT_ID} -> {CONTAINER_BASE_URL}")
        else:
            cursor.execute(
                """
                INSERT INTO model_endpoints (
                    id, name, base_url, api_key, is_enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ENDPOINT_ID, ENDPOINT_NAME, CONTAINER_BASE_URL, "sk-no-key", 1, now, now),
            )
            print(f"[+] Created new ModelEndpoint: {ENDPOINT_ID} -> {CONTAINER_BASE_URL}")

        conn.commit()
    finally:
        conn.close()


def update_odysseus_settings():
    """Update settings.json with TTS and STT configurations pointing to Speaches."""
    if not os.path.exists(SETTINGS_PATH):
        raise FileNotFoundError(f"Settings file not found at {SETTINGS_PATH}")

    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Configure Text-to-Speech
    settings["tts_enabled"] = True
    settings["tts_provider"] = f"endpoint:{ENDPOINT_ID}"
    settings["tts_model"] = TTS_MODEL
    settings["tts_voice"] = TTS_VOICE
    settings["tts_speed"] = "1"

    # Configure Speech-to-Text
    settings["stt_enabled"] = True
    settings["stt_provider"] = f"endpoint:{ENDPOINT_ID}"
    settings["stt_model"] = STT_MODEL
    settings["stt_language"] = ""

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    print("[+] Odysseus settings.json successfully updated:")
    print(f"    TTS Provider: {settings['tts_provider']} | Model: {settings['tts_model']} | Voice: {settings['tts_voice']}")
    print(f"    STT Provider: {settings['stt_provider']} | Model: {settings['stt_model']}")


def main():
    print("=== Odysseus <-> Speaches Audio Integration ===")
    check_speaches_health(HOST_BASE_URL)
    register_model_endpoint()
    update_odysseus_settings()
    print("=== Integration Complete ===")


if __name__ == "__main__":
    main()
