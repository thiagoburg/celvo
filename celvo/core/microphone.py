"""Compatibility wrapper for the shared microphone backend."""

from pathlib import Path
from threading import Event

from .audio import get_audio_backend


def record_microphone(output: Path, stop_event: Event):
    start = Event()
    start.set()
    return get_audio_backend().capture_microphone(output, stop_event, Event(), start)
