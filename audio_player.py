"""Cross-platform audio playback helpers for Odysseus Speech Tools."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def build_playback_command(audio_path: str | Path, platform: str | None = None) -> list[str] | None:
    """Return a non-blocking/native playback command for the active platform, or None if using os.startfile."""
    plat = platform or sys.platform
    target = str(audio_path)
    if plat == "darwin":
        return ["afplay", target]
    if plat.startswith("win"):
        ffplay = shutil.which("ffplay")
        if ffplay:
            return [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", target]
        escaped = target.replace("'", "''")
        ps_cmd = (
            "Add-Type -AssemblyName presentationCore; "
            "$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([Uri]::new((Resolve-Path -LiteralPath '{escaped}').Path)); "
            "Start-Sleep -Milliseconds 300; "
            "$p.Play(); "
            "while ($p.NaturalDuration.HasTimeSpan -and $p.Position -lt $p.NaturalDuration.TimeSpan) { "
            "Start-Sleep -Milliseconds 200 }; "
            "$p.Close()"
        )
        shell = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
        return [shell, "-NoProfile", "-Command", ps_cmd]
    for player in ("ffplay", "paplay", "aplay"):
        exe = shutil.which(player)
        if exe:
            if player == "ffplay":
                return [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", target]
            return [exe, target]
    return None


def play_audio_file(audio_path: str | Path) -> bool:
    """Play an audio file using native OS playback where available."""
    target = Path(audio_path)
    if sys.platform.startswith("win") and target.suffix.lower() == ".wav" and not shutil.which("ffplay"):
        try:
            import winsound

            winsound.PlaySound(str(target), winsound.SND_FILENAME)
            return True
        except Exception:
            pass
    cmd = build_playback_command(target)
    if cmd is not None:
        try:
            subprocess.run(cmd, check=True)
            return True
        except KeyboardInterrupt:
            print("\nPlayback stopped.")
            return False
        except Exception as exc:
            print(f"Playback error: {exc}")
    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        try:
            os.startfile(str(target))
            return True
        except Exception as exc:
            print(f"Playback error: {exc}")
            return False
    print(f"[-] Live playback unavailable on {sys.platform}. File saved to {target}")
    return False
