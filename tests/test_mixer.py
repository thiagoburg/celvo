from __future__ import annotations

import wave

import numpy as np
import pytest

from celvo.core.audio.base import AudioCaptureError
from celvo.core.mixer import mix_tracks


def read(path):
    with wave.open(str(path), "rb") as src:
        return src.getframerate(), np.frombuffer(src.readframes(src.getnframes()), dtype="<i2")


def test_mixes_different_rates_and_channels_with_offset(tmp_path, write_track):
    mic = write_track(tmp_path / "mic.wav", np.full(9600, 8000), 48000, 1, 3.0)
    system = write_track(tmp_path / "sys.wav", np.full((2400, 2), 4000), 24000, 2, 3.05)
    out = tmp_path / "mix.wav"
    mix_tracks([mic, system], out, chunk_frames=512)
    rate, samples = read(out)
    assert rate == 16000
    assert len(samples) == 3200
    assert np.all(samples[:800] == 4000)
    assert np.all(samples[800:2400] == 6000)
    assert np.all(samples[2400:] == 4000)


def test_silent_and_short_tracks_are_valid(tmp_path, write_track):
    silent = write_track(tmp_path / "silent.wav", np.zeros(8), 8000)
    out = tmp_path / "out.wav"
    mix_tracks([silent], out)
    rate, samples = read(out)
    assert rate == 16000
    assert len(samples) == 16
    assert not samples.any()


def test_gains_prevent_overflow_and_clip_when_requested(tmp_path, write_track):
    full = write_track(tmp_path / "full.wav", np.full(100, 32767), 16000)
    second = write_track(tmp_path / "second.wav", np.full(100, 32767), 16000)
    out = tmp_path / "out.wav"
    mix_tracks([full, second], out, gains=(1.0, 1.0))
    _, samples = read(out)
    assert np.all(samples == 32767)


def test_large_track_is_processed_in_bounded_chunks(tmp_path, write_track):
    # A two-minute synthetic track checks the chunk path, not real two-hour hardware behavior.
    large = write_track(tmp_path / "large.wav", np.arange(16000 * 120, dtype=np.int16), 16000)
    out = tmp_path / "large-mix.wav"
    mix_tracks([large], out, chunk_frames=1024)
    _, samples = read(out)
    assert len(samples) == 16000 * 120


def test_empty_tracks_are_rejected(tmp_path, write_track):
    empty = write_track(tmp_path / "empty.wav", np.array([], dtype=np.int16), 16000)
    with pytest.raises(AudioCaptureError, match="empty"):
        mix_tracks([empty], tmp_path / "out.wav")
