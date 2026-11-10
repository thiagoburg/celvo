"""Select the native audio backend for the current operating system."""

from __future__ import annotations

import sys

from .base import AudioBackend, AudioCaptureError


def get_audio_backend(system: str | None = None) -> AudioBackend:
    target = (system or sys.platform).lower()
    if target.startswith("win"):
        from .windows import WindowsAudioBackend

        return WindowsAudioBackend()
    if target.startswith("linux"):
        from .linux import LinuxAudioBackend

        return LinuxAudioBackend()
    raise AudioCaptureError(f"Unsupported operating system for audio recording: {target}")
