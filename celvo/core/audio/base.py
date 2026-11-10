"""Shared contracts and helpers for Celvo audio backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol


class AudioCaptureError(RuntimeError):
    """An audio source could not be captured reliably."""


@dataclass(frozen=True)
class AudioDevice:
    id: int | str
    name: str
    kind: str
    is_default: bool = False


@dataclass(frozen=True)
class TrackInfo:
    path: Path
    sample_rate: int
    channels: int
    frames: int
    first_sample_at: float
    last_sample_at: float

    @property
    def wall_duration(self) -> float:
        return max(0.0, self.last_sample_at - self.first_sample_at)


class AudioBackend(Protocol):
    name: str

    def list_devices(self) -> list[AudioDevice]: ...

    def capture_microphone(
        self, path: Path, stop: Event, ready: Event, start: Event, device: str | int | None = None
    ) -> TrackInfo: ...

    def capture_system_audio(
        self, path: Path, stop: Event, ready: Event, start: Event, device: str | int | None = None
    ) -> TrackInfo: ...


def map_stream_time(arrival: float, time_info, *, pyaudio: bool = False) -> float:
    """Map a PortAudio ADC timestamp into the process monotonic clock."""
    if time_info is None:
        return arrival
    adc_key, now_key = (
        ("input_buffer_adc_time", "current_time") if pyaudio else ("inputBufferAdcTime", "currentTime")
    )
    try:
        adc = time_info.get(adc_key) if isinstance(time_info, dict) else getattr(time_info, adc_key)
        current = time_info.get(now_key) if isinstance(time_info, dict) else getattr(time_info, now_key)
        if adc is not None and current is not None and adc > 0 and current > 0:
            return arrival + float(adc) - float(current)
    except (AttributeError, TypeError, ValueError):
        pass
    return arrival
