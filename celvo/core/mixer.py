"""Bounded-memory synchronization, resampling, and WAV mixing."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from .audio.base import AudioCaptureError, TrackInfo

TARGET_RATE = 16000
CHUNK_FRAMES = 32768


def mix_tracks(
    tracks: list[TrackInfo],
    output: Path,
    *,
    sample_rate: int = TARGET_RATE,
    gains: tuple[float, ...] | None = None,
    chunk_frames: int = CHUNK_FRAMES,
) -> Path:
    """Align tracks on monotonic start times and mix without loading them whole."""
    if not tracks:
        raise AudioCaptureError("No audio tracks were captured.")
    if any(track.frames <= 0 for track in tracks):
        raise AudioCaptureError("A captured audio track is empty.")
    gains = gains or tuple(0.5 if len(tracks) > 1 else 1.0 for _ in tracks)
    if len(gains) != len(tracks):
        raise ValueError("Provide exactly one gain per track.")
    if not 1 <= sample_rate <= 192000 or chunk_frames < 1:
        raise ValueError("Invalid output sample rate or chunk size.")
    earliest = min(t.first_sample_at for t in tracks)
    latest = max(_track_end(t) for t in tracks)
    total = max(1, math.ceil(max(0.0, latest - earliest) * sample_rate - 1e-9))
    readers = [_TrackReader(t) for t in tracks]
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(output), "wb") as dest:
            dest.setnchannels(1)
            dest.setsampwidth(2)
            dest.setframerate(sample_rate)
            for base in range(0, total, chunk_frames):
                count = min(chunk_frames, total - base)
                times = (base + np.arange(count, dtype=np.float64)) / sample_rate
                mixed = np.zeros(count, dtype=np.float64)
                for reader, track, gain in zip(readers, tracks, gains):
                    local = times - (track.first_sample_at - earliest)
                    active = (local >= 0) & (local < reader.wall_duration)
                    if active.any():
                        mixed[active] += reader.sample(local[active], sample_rate) * gain
                pcm = np.clip(np.rint(mixed), -32768, 32767).astype("<i2")
                dest.writeframesraw(pcm.tobytes())
    except (OSError, wave.Error) as exc:
        output.unlink(missing_ok=True)
        raise AudioCaptureError(f"Could not write mixed WAV: {exc}") from exc
    finally:
        for reader in readers:
            reader.close()
    validate_wav(output, sample_rate)
    return output


def _track_end(track: TrackInfo) -> float:
    duration = max(track.frames / track.sample_rate, track.wall_duration)
    return track.first_sample_at + duration


class _TrackReader:
    def __init__(self, track: TrackInfo):
        self.track = track
        try:
            self.wave = wave.open(str(track.path), "rb")
        except (OSError, wave.Error) as exc:
            raise AudioCaptureError(f"Could not read captured track {track.path}: {exc}") from exc
        if (
            self.wave.getnframes() != track.frames
            or self.wave.getnchannels() != track.channels
            or self.wave.getframerate() != track.sample_rate
            or self.wave.getsampwidth() != 2
        ):
            raise AudioCaptureError(f"Captured WAV metadata does not match track metadata: {track.path}")
        expected_size = 44 + track.frames * track.channels * 2
        if track.path.stat().st_size < expected_size:
            self.wave.close()
            raise AudioCaptureError(f"Captured WAV is truncated: {track.path}")
        self.wall_duration = track.wall_duration or track.frames / track.sample_rate
        self.frames = track.frames

    def sample(self, seconds: np.ndarray, output_rate: int) -> np.ndarray:
        # Wall-time normalization absorbs measured capture clock error and corrects drift.
        positions = np.clip(seconds / self.wall_duration * self.frames, 0, self.frames - 1)
        radius = 12
        spacing = self.frames / (self.wall_duration * output_rate)
        cutoff = min(1.0, 1.0 / spacing)
        centers = np.floor(positions).astype(np.int64)
        offsets = np.arange(-radius + 1, radius + 1)
        indexes = centers[:, None] + offsets[None, :]
        distance = positions[:, None] - indexes
        window = np.where(np.abs(distance) < radius, 0.5 + 0.5 * np.cos(np.pi * distance / radius), 0.0)
        weights = np.sinc(distance * cutoff) * cutoff * window
        weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
        data = self._read_window(int(indexes.min()), int(indexes.max()) + 1)
        values = data[np.clip(indexes - int(indexes.min()), 0, len(data) - 1)]
        return np.sum(values * weights, axis=1)

    def _read_window(self, first: int, end: int) -> np.ndarray:
        bounded_first = max(0, first)
        bounded_end = min(self.frames, end)
        self.wave.setpos(bounded_first)
        raw = self.wave.readframes(bounded_end - bounded_first)
        data = np.frombuffer(raw, dtype="<i2").reshape(-1, self.track.channels)
        if len(data) != bounded_end - bounded_first:
            raise AudioCaptureError(f"Captured WAV became truncated while mixing: {self.track.path}")
        mono = data.astype(np.float64).mean(axis=1)
        if bounded_first > first:
            mono = np.pad(mono, (bounded_first - first, 0), mode="edge")
        if bounded_end < end:
            mono = np.pad(mono, (0, end - bounded_end), mode="edge")
        return mono

    def close(self) -> None:
        self.wave.close()


def validate_wav(path: Path, expected_rate: int | None = None) -> None:
    try:
        with wave.open(str(path), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getnframes() < 1:
                raise AudioCaptureError(f"Output WAV is empty or has an unsupported format: {path}")
            if expected_rate and source.getframerate() != expected_rate:
                raise AudioCaptureError(f"Output WAV has an unexpected sample rate: {path}")
            frames, channels, width = source.getnframes(), source.getnchannels(), source.getsampwidth()
            source.setpos(max(0, frames - 1))
            if len(source.readframes(1)) != channels * width:
                raise AudioCaptureError(f"Output WAV is truncated: {path}")
    except (OSError, wave.Error) as exc:
        raise AudioCaptureError(f"Output is not a valid WAV file: {path}: {exc}") from exc


def mix_audio(microphone_file: Path, system_file: Path, output: Path) -> Path:
    """Compatibility wrapper for legacy callers with WAV inputs."""

    def info(path: Path) -> TrackInfo:
        with wave.open(str(path), "rb") as src:
            frames, rate = src.getnframes(), src.getframerate()
            return TrackInfo(path, rate, src.getnchannels(), frames, 0.0, frames / rate)

    return mix_tracks([info(microphone_file), info(system_file)], output)
