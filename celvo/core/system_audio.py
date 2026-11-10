"""Compatibility wrapper for the platform system audio backend."""

from pathlib import Path
from threading import Event

from .audio import get_audio_backend


def record_system_audio(output: Path, stop_event: Event):
    start = Event()
    start.set()
    return get_audio_backend().capture_system_audio(output, stop_event, Event(), start)
