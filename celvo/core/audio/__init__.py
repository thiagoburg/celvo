"""Platform audio capture backends."""

from .base import AudioBackend, AudioCaptureError, AudioDevice, TrackInfo
from .factory import get_audio_backend

__all__ = ["AudioCaptureError", "AudioBackend", "AudioDevice", "TrackInfo", "get_audio_backend"]
