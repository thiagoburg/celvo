"""PulseAudio-compatible Linux capture backend."""

from __future__ import annotations

import re
import select
import subprocess
import time
import wave
from pathlib import Path
from threading import Event

import sounddevice as sd

from .base import AudioCaptureError, AudioDevice, TrackInfo
from .capture import capture_microphone


class LinuxAudioBackend:
    name = "PulseAudio / sounddevice"

    def list_devices(self) -> list[AudioDevice]:
        devices: list[AudioDevice] = []
        try:
            default_input = sd.default.device[0]
            for index, item in enumerate(sd.query_devices()):
                if item["max_input_channels"]:
                    devices.append(AudioDevice(index, item["name"], "microphone", index == default_input))
        except Exception as exc:
            raise AudioCaptureError(f"Could not enumerate microphone devices: {exc}") from exc
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sources"], capture_output=True, text=True, check=True, timeout=5
            )
            for line in result.stdout.splitlines():
                fields = line.split()
                if len(fields) >= 2 and ".monitor" in fields[1]:
                    devices.append(AudioDevice(fields[1], fields[1], "system"))
        except (OSError, subprocess.SubprocessError) as exc:
            raise AudioCaptureError(f"Could not list PulseAudio sources (pactl): {exc}") from exc
        return devices

    def capture_microphone(
        self, path: Path, stop: Event, ready: Event, start: Event, device: str | int | None = None
    ) -> TrackInfo:
        return capture_microphone(path, stop, ready, start, device)

    def capture_system_audio(
        self, path: Path, stop: Event, ready: Event, start: Event, device: str | int | None = None
    ) -> TrackInfo:
        monitor = str(device) if device is not None else self._default_monitor()
        command = ["parec", "--device", monitor, "--format=s16le", "--rate=48000", "--channels=2"]
        stderr_path = path.with_suffix(".stderr")
        ready.set()
        if not start.wait(10):
            raise AudioCaptureError("Timed out waiting for coordinated recording start.")
        try:
            stderr_file = stderr_path.open("wb")
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_file, bufsize=0)
        except OSError as exc:
            raise AudioCaptureError(f"Could not start system audio capture with parec: {exc}") from exc
        frames = 0
        first_at: float | None = None
        last_at = 0.0
        pending = b""
        last_data_at = time.monotonic()
        try:
            with wave.open(str(path), "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(48000)
                while not stop.is_set():
                    readable, _, _ = select.select([process.stdout], [], [], 0.2)
                    if not readable:
                        if process.poll() is not None:
                            break
                        if frames and time.monotonic() - last_data_at > 5:
                            raise AudioCaptureError("PulseAudio monitor stalled for more than 5 seconds.")
                        continue
                    data = process.stdout.read(8192)
                    if not data:
                        if process.poll() is not None:
                            break
                        continue
                    stamp = time.monotonic()
                    last_data_at = stamp
                    if first_at is None:
                        first_at = stamp
                    data = pending + data
                    aligned_bytes = len(data) - (len(data) % 4)
                    if aligned_bytes == 0:
                        pending = data
                        continue
                    output.writeframesraw(data[:aligned_bytes])
                    pending = data[aligned_bytes:]
                    n = aligned_bytes // 4
                    frames += n
                    last_at = stamp + n / 48000
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
            process.stdout.close()
            stderr_file.close()
        diagnostic = stderr_path.read_text(errors="replace") if stderr_path.exists() else ""
        if re.search(r"\b(overflow|dropped frame|xrun)\b", diagnostic, re.IGNORECASE):
            raise AudioCaptureError(f"PulseAudio reported possible audio loss: {diagnostic.strip()}")
        if pending:
            raise AudioCaptureError(
                "PulseAudio ended with an incomplete sample frame; partial capture was retained."
            )
        if process.returncode not in (0, -15, 143) and not stop.is_set():
            raise AudioCaptureError(
                f"PulseAudio capture exited with status {process.returncode}: {diagnostic.strip()}"
            )
        if not stop.is_set():
            raise AudioCaptureError(f"PulseAudio capture stopped unexpectedly (status {process.returncode}).")
        if frames == 0:
            raise AudioCaptureError(
                f"PulseAudio monitor {monitor!r} returned no frames. {diagnostic.strip()}"
            )
        stderr_path.unlink(missing_ok=True)
        return TrackInfo(path, 48000, 2, frames, first_at or time.monotonic(), last_at)

    @staticmethod
    def _default_monitor() -> str:
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sources"], capture_output=True, text=True, check=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise AudioCaptureError(f"Could not query PulseAudio sources: {exc}") from exc
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 2 and ".monitor" in fields[1]:
                return fields[1]
        raise AudioCaptureError("No PulseAudio output monitor was found; system audio is unavailable.")
