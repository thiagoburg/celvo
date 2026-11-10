from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from celvo.core.audio.base import TrackInfo


@pytest.fixture
def write_track():
    def write(
        path: Path,
        samples,
        rate: int,
        channels: int = 1,
        start: float = 0.0,
        wall_duration: float | None = None,
    ) -> TrackInfo:
        array = np.asarray(samples, dtype="<i2")
        if channels > 1 and array.ndim == 1:
            array = np.repeat(array[:, None], channels, axis=1)
        with wave.open(str(path), "wb") as out:
            out.setnchannels(channels)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(array.tobytes())
        frames = len(array)
        duration = wall_duration if wall_duration is not None else frames / rate
        return TrackInfo(path, rate, channels, frames, start, start + duration)

    return write
