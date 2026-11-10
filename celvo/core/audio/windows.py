"""Native Windows microphone and WASAPI loopback capture."""

from __future__ import annotations

import queue
import time
import wave
from pathlib import Path
from threading import Event

import sounddevice as sd

from .base import AudioCaptureError, AudioDevice, TrackInfo, map_stream_time
from .capture import capture_microphone


class WindowsAudioBackend:
    name = "WASAPI loopback / sounddevice"

    def list_devices(self) -> list[AudioDevice]:
        devices: list[AudioDevice] = []
        try:
            default_input = sd.default.device[0]
            for index, item in enumerate(sd.query_devices()):
                if item["max_input_channels"]:
                    devices.append(AudioDevice(index, item["name"], "microphone", index == default_input))
            import pyaudiowpatch as pyaudio

            with pyaudio.PyAudio() as audio:
                default = audio.get_default_wasapi_device(d_out=True)
                host = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
                host_index = int(host["index"])
                default_index = int(default["index"]) if default else -1
                for item in audio.get_device_info_generator_by_host_api(host_api_index=host_index):
                    if item.get("maxOutputChannels", 0) > 0:
                        devices.append(
                            AudioDevice(
                                item["index"], item["name"], "system", int(item["index"]) == default_index
                            )
                        )
        except ImportError as exc:
            raise AudioCaptureError(
                "PyAudioWPatch is missing. Reinstall Celvo to enable WASAPI loopback."
            ) from exc
        except Exception as exc:
            raise AudioCaptureError(f"Could not enumerate Windows audio devices: {exc}") from exc
        return devices

    def capture_microphone(
        self, path: Path, stop: Event, ready: Event, start: Event, device: str | int | None = None
    ) -> TrackInfo:
        return capture_microphone(path, stop, ready, start, device)

    def capture_system_audio(
        self, path: Path, stop: Event, ready: Event, start: Event, device: str | int | None = None
    ) -> TrackInfo:
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise AudioCaptureError("PyAudioWPatch is missing; WASAPI loopback cannot be started.") from exc
        audio = pyaudio.PyAudio()
        stream = None
        try:
            loopback = (
                audio.get_default_wasapi_loopback()
                if device is None
                else audio.get_wasapi_loopback_analogue_by_index(int(device))
            )
            if not loopback:
                raise AudioCaptureError("The selected Windows output has no WASAPI loopback input.")
            index = int(loopback["index"])
            default_rate = int(loopback.get("defaultSampleRate", 48000))
            max_channels = min(2, int(loopback.get("maxInputChannels", 2))) or 2
            pa_format = pyaudio.paInt16
            candidates = list(dict.fromkeys([default_rate, 48000, 44100, 32000, 16000]))
            selected = next(
                (
                    (candidate_rate, candidate_channels)
                    for candidate_rate in candidates
                    for candidate_channels in range(max_channels, 0, -1)
                    if _supports_format(audio, index, candidate_rate, candidate_channels, pa_format)
                ),
                None,
            )
            if selected:
                rate, channels = selected
            else:
                raise AudioCaptureError(
                    f"WASAPI loopback device {loopback['name']!r} rejected supported formats."
                )
            blocks: queue.Queue[tuple[bytes, int, float]] = queue.Queue(maxsize=64)
            callback_errors: list[str] = []

            def callback(in_data, frame_count, time_info, status_flags):
                timestamp = map_stream_time(time.monotonic(), time_info, pyaudio=True)
                if status_flags:
                    callback_errors.append(f"WASAPI reported input overflow/status {status_flags}.")
                    stop.set()
                    return None, pyaudio.paAbort
                if in_data is None or len(in_data) != frame_count * channels * 2:
                    callback_errors.append("WASAPI returned an incomplete audio block.")
                    stop.set()
                    return None, pyaudio.paAbort
                try:
                    blocks.put_nowait((in_data, frame_count, timestamp))
                except queue.Full:
                    callback_errors.append("WASAPI writer queue overflowed; audio frames were lost.")
                    stop.set()
                    return None, pyaudio.paAbort
                return None, pyaudio.paContinue

            try:
                stream = audio.open(
                    format=pa_format,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=index,
                    frames_per_buffer=2048,
                    stream_callback=callback,
                    start=False,
                )
            except Exception as exc:
                raise AudioCaptureError(
                    f"Could not open WASAPI loopback for {loopback['name']!r}: {exc}"
                ) from exc
            ready.set()
            if not start.wait(10):
                raise AudioCaptureError("Timed out waiting for coordinated recording start.")
            if stop.is_set():
                raise AudioCaptureError(
                    "Capture cancelled before start because another recording source failed."
                )
            capture_started_at = time.monotonic()
            stream.start_stream()
            frames = 0
            stream_stopped = False
            bytes_per_frame = channels * 2
            # WASAPI loopback callbacks can pause while the endpoint is silent.
            # Keep a small latency cushion so queued callbacks arrive before we
            # synthesize their corresponding quiet samples.
            silence_safety_seconds = 0.25
            with wave.open(str(path), "wb") as output:
                output.setnchannels(channels)
                output.setsampwidth(2)
                output.setframerate(rate)
                while True:
                    if stop.is_set() and not stream_stopped:
                        # Stop the producer before draining. Otherwise a busy
                        # loopback callback can keep the bounded queue nonempty
                        # forever while the writer is trying to finish.
                        stream.stop_stream()
                        stream_stopped = True
                    try:
                        data, block_frames, stamp = blocks.get(timeout=0.2)
                    except queue.Empty:
                        if stop.is_set():
                            target_frames = round((time.monotonic() - capture_started_at) * rate)
                            missing = max(0, target_frames - frames)
                            _write_silence(output, missing, bytes_per_frame)
                            frames += missing
                            break
                        if not stream.is_active():
                            raise AudioCaptureError("WASAPI loopback stream stopped unexpectedly.")
                        target_seconds = max(
                            0.0,
                            time.monotonic() - capture_started_at - silence_safety_seconds,
                        )
                        target_frames = round(target_seconds * rate)
                        missing = max(0, target_frames - frames)
                        _write_silence(output, missing, bytes_per_frame)
                        frames += missing
                        continue
                    target_frame = max(0, round((stamp - capture_started_at) * rate))
                    if target_frame > frames:
                        missing = target_frame - frames
                        _write_silence(output, missing, bytes_per_frame)
                        frames += missing
                    # If scheduling delay caused synthetic silence to cover part
                    # of this callback, trim that overlap rather than duplicate
                    # samples or shift later audio.
                    overlap = max(0, frames - target_frame)
                    trim = min(overlap, block_frames)
                    if trim < block_frames:
                        output.writeframesraw(data[trim * bytes_per_frame :])
                        frames += block_frames - trim
            if callback_errors:
                raise AudioCaptureError(callback_errors[0])
            if frames == 0:
                raise AudioCaptureError("WASAPI loopback returned no audio frames.")
            return TrackInfo(
                path, rate, channels, frames, capture_started_at, capture_started_at + frames / rate
            )
        finally:
            if stream is not None:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                finally:
                    audio.terminate()
            else:
                audio.terminate()


def _supports_format(audio, device: int, rate: int, channels: int, audio_format: int) -> bool:
    try:
        return bool(
            audio.is_format_supported(
                rate, input_device=device, input_channels=channels, input_format=audio_format
            )
        )
    except Exception:
        return False


def _write_silence(output, frames: int, bytes_per_frame: int) -> None:
    """Write zero samples without allocating a recording-sized buffer."""
    if frames <= 0:
        return
    chunk_frames = max(1, 16_384 // bytes_per_frame)
    silence = bytes(min(frames, chunk_frames) * bytes_per_frame)
    while frames:
        count = min(frames, chunk_frames)
        output.writeframesraw(silence[: count * bytes_per_frame])
        frames -= count
