"""Threaded task controllers that keep Tk callbacks off worker threads."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.processor import process_audio
from ..core.recorder import record_audio


@dataclass(frozen=True)
class UiEvent:
    kind: str
    payload: Any = None


class RecordingController:
    def __init__(self, record_fn: Callable[..., Path] = record_audio):
        self._record_fn = record_fn
        self._events: queue.Queue[UiEvent] = queue.Queue()
        self._stop: threading.Event | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        source: str,
        microphone_device: int | str | None,
        system_device: int | str | None,
    ) -> None:
        if self.running:
            raise RuntimeError("A recording is already in progress.")
        self._stop = threading.Event()

        def report_progress(seconds: float) -> None:
            self._events.put(UiEvent("recording_progress", seconds))

        def run() -> None:
            try:
                output = self._record_fn(
                    source,
                    microphone_device,
                    system_device,
                    stop_event=self._stop,
                    progress_callback=report_progress,
                )
            except Exception as exc:
                self._events.put(UiEvent("recording_failed", str(exc)))
            else:
                self._events.put(UiEvent("recording_finished", Path(output)))

        self._thread = threading.Thread(target=run, name="celvo-ui-recording", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()

    def drain_events(self) -> list[UiEvent]:
        events: list[UiEvent] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events


class TranscriptionController:
    def __init__(self, process_fn: Callable[..., Path] = process_audio):
        self._process_fn = process_fn
        self._events: queue.Queue[UiEvent] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._cancel: threading.Event | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, audio_path: Path) -> None:
        if self.running:
            raise RuntimeError("A transcription is already in progress.")
        audio_path = Path(audio_path)
        self._cancel = threading.Event()

        def report_status(message: str) -> None:
            self._events.put(UiEvent("transcription_status", message))

        def run() -> None:
            try:
                output = self._process_fn(
                    audio_path, status_callback=report_status, cancel_event=self._cancel
                )
            except Exception as exc:
                kind = "transcription_cancelled" if self._cancel.is_set() else "transcription_failed"
                self._events.put(UiEvent(kind, str(exc)))
            else:
                self._events.put(UiEvent("transcription_finished", Path(output)))

        self._thread = threading.Thread(target=run, name="celvo-ui-transcription", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        """Ask the active Whisper process to stop promptly."""
        if self._cancel is not None:
            self._cancel.set()

    def drain_events(self) -> list[UiEvent]:
        events: list[UiEvent] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events
