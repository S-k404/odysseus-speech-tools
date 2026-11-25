import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import audio_player


class TestOdysseusWin32Compat(unittest.TestCase):
    def test_playback_command_dispatch_by_platform(self):
        with mock.patch("audio_player.shutil.which", return_value=None):
            self.assertEqual(audio_player.build_playback_command("out.mp3", platform="darwin"), ["afplay", "out.mp3"])
            win_cmd = audio_player.build_playback_command("out.mp3", platform="win32")
            self.assertIsNotNone(win_cmd)
            self.assertIn("MediaPlayer", " ".join(win_cmd))

        with mock.patch("audio_player.shutil.which", side_effect=lambda name: f"C:\\ffmpeg\\{name}.exe" if name == "ffplay" else None):
            win_ffplay = audio_player.build_playback_command("out.mp3", platform="win32")
            self.assertEqual(win_ffplay, ["C:\\ffmpeg\\ffplay.exe", "-nodisp", "-autoexit", "-loglevel", "quiet", "out.mp3"])

        with mock.patch("audio_player.shutil.which", side_effect=lambda name: "/usr/bin/paplay" if name == "paplay" else None):
            self.assertEqual(audio_player.build_playback_command("out.mp3", platform="linux"), ["/usr/bin/paplay", "out.mp3"])

    def test_narrator_and_read_doc_cli_help(self):
        import importlib.util

        scripts = ["narrator.py", "read_doc.py"]
        if importlib.util.find_spec("pymupdf") is not None:
            scripts.append("pdf2epub_tts.py")
        for script in scripts:
            proc = subprocess.run(
                [sys.executable, str(ROOT / script), "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, f"{script} --help failed: {proc.stderr}")

    def test_pdf2epub_tts_win32_venv_resolution_syntax(self):
        src = (ROOT / "pdf2epub_tts.py").read_text(encoding="utf-8")
        compile(src, str(ROOT / "pdf2epub_tts.py"), "exec")
        self.assertIn("Scripts/python.exe", src)

    def test_kokoro_native_server_imports_cleanly(self):
        code = (ROOT / "kokoro-native" / "server.py").read_text(encoding="utf-8")
        compile(code, str(ROOT / "kokoro-native" / "server.py"), "exec")
        app_code = (ROOT / "kokoro-native" / "app.py").read_text(encoding="utf-8")
        compile(app_code, str(ROOT / "kokoro-native" / "app.py"), "exec")


if __name__ == "__main__":
    unittest.main()
