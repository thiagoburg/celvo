from __future__ import annotations

import pytest

from celvo.core.audio import AudioCaptureError, get_audio_backend


def test_selects_linux_backend():
    assert get_audio_backend("linux").name.startswith("PulseAudio")


def test_selects_windows_backend_without_loading_windows_api():
    assert get_audio_backend("win32").name.startswith("WASAPI")


def test_rejects_unsupported_platform():
    with pytest.raises(AudioCaptureError, match="Unsupported operating system"):
        get_audio_backend("darwin")
