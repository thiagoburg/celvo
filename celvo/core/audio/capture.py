"""Callback-driven microphone capture with bounded memory use."""

from __future__ import annotations

import queue
import time
import wave
from pathlib import Path
from threading import Event

import numpy as np
import sounddevice as sd

from .base import AudioCaptureError, TrackInfo, map_stream_time

_RATES = (48000, 44100, 32000, 24000, 16000)
_CHANNELS = (2, 1)
_BLOCK = 2048


def capture_microphone(
    path: Path, stop: Event, ready: Event, start: Event, device: str | int | None = None
) -> TrackInfo:
    """Capture input in a callback into a bounded queue and stream it to WAV."""
    selected = device if device is not None else sd.default.device[0]
    candidates = [
        (rate, channels) for rate in _RATES for channels in _CHANNELS if _supports(selected, rate, channels)
    ]
    if not candidates:
        raise AudioCaptureError(f"No supported microphone format found for input device {selected!r}.")
    rate, channels = candidates[0]
    blocks: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(maxsize=64)
    callback_errors: list[str] = []
    last_callback_at = [time.monotonic()]
    first_at: float | None = None
    last_at = 0.0
    frames = 0

    def callback(indata, frame_count, time_info, status):
        if status:
            callback_errors.append(f"Microphone stream reported: {status}")
            stop.set()
            raise sd.CallbackAbort
        timestamp = map_stream_time(time.monotonic(), time_info)
        last_callback_at[0] = timestamp
        try:
            blocks.put_nowait((np.asarray(indata).copy(), timestamp))
        except queue.Full:
            callback_errors.append("Microphone writer queue overflowed; audio frames were lost.")
            stop.set()
            raise sd.CallbackAbort

    try:
        stream = sd.InputStream(
            device=selected,
            samplerate=rate,
            channels=channels,
            dtype="int16",
            blocksize=_BLOCK,
            callback=callback,
        )
    except Exception as exc:
        raise AudioCaptureError(f"Could not open microphone input {selected!r}: {exc}") from exc

    try:
        ready.set()
        if not start.wait(10):
            raise AudioCaptureError("Timed out waiting for coordinated recording start.")
        if stop.is_set():
            raise AudioCaptureError("Capture cancelled before start because another recording source failed.")
        stream.start()
        with wave.open(str(path), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(2)
            output.setframerate(rate)
            while not stop.is_set() or not blocks.empty():
                if not stop.is_set() and time.monotonic() - last_callback_at[0] > 5:
                    raise AudioCaptureError("Microphone input stalled for more than 5 seconds.")
                try:
                    data, timestamp = blocks.get(timeout=0.2)
                except queue.Empty:
                    continue
                if first_at is None:
                    first_at = timestamp
                last_at = timestamp + len(data) / rate
                output.writeframesraw(data.tobytes())
                frames += len(data)
        if callback_errors:
            raise AudioCaptureError(callback_errors[0])
        if frames == 0:
            raise AudioCaptureError("Microphone produced no audio frames.")
        return TrackInfo(path, rate, channels, frames, first_at or time.monotonic(), last_at)
    finally:
        try:
            if stream.active:
                stream.stop()
        finally:
            stream.close()


def _supports(device: str | int | None, rate: int, channels: int) -> bool:
    try:
        sd.check_input_settings(device=device, samplerate=rate, channels=channels, dtype="int16")
        return True
    except Exception:
        return False
