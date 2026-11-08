#!/usr/bin/env python3
"""
apply_audio_config.py

Applies the Odysseus audio configuration requested by user:
- TTS_ENABLED=true
- TTS_PROVIDER=openai
- TTS_OPENAI_API_BASE=http://speaches:8000/v1
- TTS_OPENAI_API_KEY=not-needed
- TTS_MODEL=hexgrad/Kokoro-82M
- TTS_VOICE=af_sky
- STT_ENABLED=true
- STT_PROVIDER=openai
- STT_OPENAI_API_BASE=http://speaches:8000/v1
- STT_OPENAI_API_KEY=not-needed
- STT_MODEL=Systran/faster-whisper-small

Updates:
1. .env in Odysseus
2. services/tts/tts_service.py
3. services/stt/stt_service.py
4. static/js/voiceRecorder.js
5. data/settings.json
"""

import os
import re
import json
import shutil
from pathlib import Path

ODYSSEUS_DIR = (Path.home() / "Documents/Docker/Odysseus")
ENV_PATH = ODYSSEUS_DIR / ".env"
TTS_SERVICE_PATH = ODYSSEUS_DIR / "services" / "tts" / "tts_service.py"
STT_SERVICE_PATH = ODYSSEUS_DIR / "services" / "stt" / "stt_service.py"
VOICE_RECORDER_PATH = ODYSSEUS_DIR / "static" / "js" / "voiceRecorder.js"
SETTINGS_PATH = ODYSSEUS_DIR / "data" / "settings.json"

CONFIG_BLOCK = """
# ==============================================================================
# ODYSSEUS AUDIO CONFIGURATION (SPEACHES: KOKORO TTS + WHISPER STT)
# ==============================================================================

# TTS (Voice Output - Kokoro 82M)
TTS_ENABLED=true
TTS_PROVIDER=openai
TTS_OPENAI_API_BASE=http://speaches:8000/v1
TTS_OPENAI_API_KEY=not-needed
TTS_MODEL=hexgrad/Kokoro-82M
TTS_VOICE=af_sky # Options: af_sky, af_bella, am_adam, am_michael, bf_emma, bm_george

# STT (Voice Input - Faster-Whisper)
STT_ENABLED=true
STT_PROVIDER=openai
STT_OPENAI_API_BASE=http://speaches:8000/v1
STT_OPENAI_API_KEY=not-needed
STT_MODEL=Systran/faster-whisper-small
"""


def update_env_file():
    print("[1/5] Updating .env file...")
    content = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    
    # Check if block is already present; if so, replace it, otherwise append
    pattern = r"# ===+\s*# ODYSSEUS AUDIO CONFIGURATION[\s\S]*?(?=\n# ===|\Z)"
    if re.search(pattern, content):
        content = re.sub(pattern, CONFIG_BLOCK.strip(), content)
    else:
        content = content.rstrip() + "\n" + CONFIG_BLOCK

    ENV_PATH.write_text(content, encoding="utf-8")
    print("      ✓ .env updated.")


def update_tts_service():
    print("[2/5] Updating services/tts/tts_service.py...")
    code = TTS_SERVICE_PATH.read_text(encoding="utf-8")
    
    # 1. Update _load_settings to read environment variables
    old_load = """    def _load_settings(self) -> dict:
        from src.settings import load_settings
        saved = load_settings()
        return {
            "tts_enabled": saved.get("tts_enabled", True),
            "tts_provider": saved.get("tts_provider", "disabled"),
            "tts_model": saved.get("tts_model", "tts-1"),
            "tts_voice": saved.get("tts_voice", "alloy"),
            "tts_speed": saved.get("tts_speed", "1"),
        }"""

    new_load = """    def _load_settings(self) -> dict:
        from src.settings import load_settings
        saved = load_settings()
        env_enabled = os.getenv("TTS_ENABLED")
        tts_enabled = (env_enabled.lower() in ("true", "1", "yes")) if env_enabled is not None else saved.get("tts_enabled", True)
        tts_provider = os.getenv("TTS_PROVIDER") or saved.get("tts_provider", "disabled")
        tts_model = os.getenv("TTS_MODEL") or saved.get("tts_model", "tts-1")
        tts_voice = os.getenv("TTS_VOICE") or saved.get("tts_voice", "alloy")
        tts_speed = os.getenv("TTS_SPEED") or saved.get("tts_speed", "1")
        openai_base = os.getenv("TTS_OPENAI_API_BASE", "")
        openai_key = os.getenv("TTS_OPENAI_API_KEY", "")
        return {
            "tts_enabled": tts_enabled,
            "tts_provider": tts_provider,
            "tts_model": tts_model,
            "tts_voice": tts_voice,
            "tts_speed": tts_speed,
            "openai_api_base": openai_base,
            "openai_api_key": openai_key,
        }"""

    if old_load in code:
        code = code.replace(old_load, new_load)

    # 2. Update available property
    old_avail = """        if provider == "disabled":
            return False
        if provider == "browser":
            return True  # handled client-side
        if provider == "local":
            kokoro = self._get_kokoro()
            return kokoro is not None and kokoro.available
        if isinstance(provider, str) and provider.startswith("endpoint:"):
            return True  # assume reachable; errors surface at synthesis time
        return False"""

    new_avail = """        if provider == "disabled":
            return False
        if provider == "browser":
            return True  # handled client-side
        if provider == "local":
            kokoro = self._get_kokoro()
            return kokoro is not None and kokoro.available
        if provider == "openai":
            return bool(settings.get("openai_api_base") or os.getenv("TTS_OPENAI_API_BASE"))
        if isinstance(provider, str) and provider.startswith("endpoint:"):
            return True  # assume reachable; errors surface at synthesis time
        return False"""

    if old_avail in code:
        code = code.replace(old_avail, new_avail)

    # 3. Add _synthesize_openai method and model aliasing
    if "def _synthesize_openai(" not in code:
        method_code = """    def _synthesize_openai(self, text: str, base_url: str, api_key: str, model: str, voice: str, speed: float = 1.0) -> Optional[bytes]:
        url = base_url.rstrip("/") + "/audio/speech"
        headers = {"Content-Type": "application/json"}
        if api_key and api_key != "not-needed":
            headers["Authorization"] = f"Bearer {api_key}"

        # Resolve model name alias for Speaches Kokoro
        effective_model = model
        if effective_model in ("hexgrad/Kokoro-82M", "kokoro", "Kokoro-82M"):
            effective_model = "speaches-ai/Kokoro-82M-v1.0-ONNX"

        payload = {
            "model": effective_model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
            "speed": speed,
        }

        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=60)
            r.raise_for_status()
            logger.info(f"OpenAI TTS: {len(r.content)} bytes from {base_url}")
            return r.content
        except Exception as e:
            logger.error(f"OpenAI TTS synthesis failed: {e}")
            return None

    # ── API endpoint ──"""

        code = code.replace("    # ── API endpoint ──", method_code)

    # In _synthesize_api, also alias hexgrad/Kokoro-82M
    old_synth_api = """        url = base_url + "/audio/speech"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,"""

    new_synth_api = """        url = base_url + "/audio/speech"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        effective_model = model
        if effective_model in ("hexgrad/Kokoro-82M", "kokoro", "Kokoro-82M"):
            effective_model = "speaches-ai/Kokoro-82M-v1.0-ONNX"

        payload = {
            "model": effective_model,"""

    if old_synth_api in code:
        code = code.replace(old_synth_api, new_synth_api)

    # 4. Update synthesize dispatch
    old_synth_dispatch = """        if provider == "local":
            kokoro = self._get_kokoro()
            if kokoro and kokoro.available:
                audio_data = kokoro.synthesize_raw(text, voice)
            else:
                logger.warning("Kokoro TTS not available")
                return None
        elif provider.startswith("endpoint:"):
            endpoint_id = provider.split(":", 1)[1]
            audio_data = self._synthesize_api(text, endpoint_id, model, voice, speed)"""

    new_synth_dispatch = """        if provider == "local":
            kokoro = self._get_kokoro()
            if kokoro and kokoro.available:
                audio_data = kokoro.synthesize_raw(text, voice)
            else:
                logger.warning("Kokoro TTS not available")
                return None
        elif provider == "openai":
            base_url = settings.get("openai_api_base") or os.getenv("TTS_OPENAI_API_BASE", "http://speaches:8000/v1")
            api_key = settings.get("openai_api_key") or os.getenv("TTS_OPENAI_API_KEY", "")
            audio_data = self._synthesize_openai(text, base_url, api_key, model, voice, speed)
        elif isinstance(provider, str) and provider.startswith("endpoint:"):
            endpoint_id = provider.split(":", 1)[1]
            audio_data = self._synthesize_api(text, endpoint_id, model, voice, speed)"""

    if old_synth_dispatch in code:
        code = code.replace(old_synth_dispatch, new_synth_dispatch)

    TTS_SERVICE_PATH.write_text(code, encoding="utf-8")
    print("      ✓ tts_service.py updated.")


def update_stt_service():
    print("[3/5] Updating services/stt/stt_service.py...")
    code = STT_SERVICE_PATH.read_text(encoding="utf-8")
    
    # 1. Update _load_settings
    old_load = """    def _load_settings(self) -> dict:
        from src.settings import load_settings
        saved = load_settings()
        return {
            "stt_enabled": saved.get("stt_enabled", False),
            "stt_provider": saved.get("stt_provider", "disabled"),
            "stt_model": saved.get("stt_model", "base"),
            "stt_language": saved.get("stt_language", ""),
        }"""

    new_load = """    def _load_settings(self) -> dict:
        from src.settings import load_settings
        saved = load_settings()
        env_enabled = os.getenv("STT_ENABLED")
        stt_enabled = (env_enabled.lower() in ("true", "1", "yes")) if env_enabled is not None else saved.get("stt_enabled", False)
        stt_provider = os.getenv("STT_PROVIDER") or saved.get("stt_provider", "disabled")
        stt_model = os.getenv("STT_MODEL") or saved.get("stt_model", "base")
        stt_language = os.getenv("STT_LANGUAGE") or saved.get("stt_language", "")
        openai_base = os.getenv("STT_OPENAI_API_BASE", "")
        openai_key = os.getenv("STT_OPENAI_API_KEY", "")
        return {
            "stt_enabled": stt_enabled,
            "stt_provider": stt_provider,
            "stt_model": stt_model,
            "stt_language": stt_language,
            "openai_api_base": openai_base,
            "openai_api_key": openai_key,
        }"""

    if old_load in code:
        code = code.replace(old_load, new_load)

    # 2. Update available property
    old_avail = """        if provider == "disabled":
            return False
        if provider == "browser":
            return True  # handled client-side
        if provider == "local":
            return self._get_whisper() is not None
        if provider.startswith("endpoint:"):
            return True  # assume reachable
        return False"""

    new_avail = """        if provider == "disabled":
            return False
        if provider == "browser":
            return True  # handled client-side
        if provider == "local":
            return self._get_whisper() is not None
        if provider == "openai":
            return bool(settings.get("openai_api_base") or os.getenv("STT_OPENAI_API_BASE"))
        if isinstance(provider, str) and provider.startswith("endpoint:"):
            return True  # assume reachable
        return False"""

    if old_avail in code:
        code = code.replace(old_avail, new_avail)

    # 3. Add _transcribe_openai method
    if "def _transcribe_openai(" not in code:
        method_code = """    def _transcribe_openai(self, audio_bytes: bytes, base_url: str, api_key: str, model: str, language: str = "") -> Optional[str]:
        url = base_url.rstrip("/") + "/audio/transcriptions"
        headers = {}
        if api_key and api_key != "not-needed":
            headers["Authorization"] = f"Bearer {api_key}"

        files = {"file": ("audio.webm", io.BytesIO(audio_bytes), "audio/webm")}
        data = {"model": model or "Systran/faster-whisper-small"}
        if language:
            data["language"] = language

        try:
            r = httpx.post(url, headers=headers, files=files, data=data, timeout=60)
            r.raise_for_status()
            result = r.json()
            text = result.get("text", "")
            logger.info(f"OpenAI STT: {len(text)} chars from {base_url}")
            return text
        except Exception as e:
            logger.error(f"OpenAI STT transcription failed: {e}")
            return None

    # ── Public interface ──"""

        code = code.replace("    # ── Public interface ──", method_code)

    # 4. Update transcribe dispatch
    old_trans_dispatch = """        if provider == "local":
            return self._transcribe_local(audio_bytes, language)
        elif provider.startswith("endpoint:"):
            endpoint_id = provider.split(":", 1)[1]
            return self._transcribe_api(audio_bytes, endpoint_id, model, language)"""

    new_trans_dispatch = """        if provider == "local":
            return self._transcribe_local(audio_bytes, language)
        elif provider == "openai":
            base_url = settings.get("openai_api_base") or os.getenv("STT_OPENAI_API_BASE", "http://speaches:8000/v1")
            api_key = settings.get("openai_api_key") or os.getenv("STT_OPENAI_API_KEY", "")
            return self._transcribe_openai(audio_bytes, base_url, api_key, model, language)
        elif isinstance(provider, str) and provider.startswith("endpoint:"):
            endpoint_id = provider.split(":", 1)[1]
            return self._transcribe_api(audio_bytes, endpoint_id, model, language)"""

    if old_trans_dispatch in code:
        code = code.replace(old_trans_dispatch, new_trans_dispatch)

    STT_SERVICE_PATH.write_text(code, encoding="utf-8")
    print("      ✓ stt_service.py updated.")


def update_voice_recorder():
    print("[4/5] Updating static/js/voiceRecorder.js...")
    code = VOICE_RECORDER_PATH.read_text(encoding="utf-8")
    old_check = "else if (provider === 'local' || provider.startsWith('endpoint:')) {"
    new_check = "else if (provider === 'local' || provider.startsWith('endpoint:') || provider === 'openai') {"
    if old_check in code:
        code = code.replace(old_check, new_check)
        VOICE_RECORDER_PATH.write_text(code, encoding="utf-8")
        print("      ✓ voiceRecorder.js updated.")
    else:
        print("      - voiceRecorder.js already has provider check or pattern differs.")


def update_settings_json():
    print("[5/5] Updating data/settings.json...")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    settings["tts_enabled"] = True
    settings["tts_provider"] = "openai"
    settings["tts_model"] = "hexgrad/Kokoro-82M"
    settings["tts_voice"] = "af_sky"
    settings["tts_speed"] = "1"

    settings["stt_enabled"] = True
    settings["stt_provider"] = "openai"
    settings["stt_model"] = "Systran/faster-whisper-small"

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    print("      ✓ settings.json updated.")


def main():
    print("=== Applying Odysseus Audio Configuration ===")
    update_env_file()
    update_tts_service()
    update_stt_service()
    update_voice_recorder()
    update_settings_json()
    print("=== Configuration Applied Successfully! ===")


if __name__ == "__main__":
    main()
