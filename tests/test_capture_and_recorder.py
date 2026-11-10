from __future__ import annotations

import threading
import time
import wave
from threading import Event

import numpy as np
import pytest

from celvo.core.audio import AudioCaptureError
from celvo.core.audio import capture as capture_module
from celvo.core.audio.base import TrackInfo, map_stream_time
from celvo.core.audio.windows import WindowsAudioBackend
from celvo.core.recorder import record_audio


def test_microphone_capture_streams_blocks_and_closes(monkeypatch, tmp_path):
    captured = {}

    class FakeStream:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
            self.closed = False
            self.active = False
            captured["stream"] = self

        def close(self):
            self.closed = True

        def start(self):
            callback = captured["kwargs"]["callback"]
            callback(np.ones((8, 1), dtype=np.int16) * 123, 8, None, None)
            stop.set()

        def stop(self):
            self.active = False

    stop, ready, start = Event(), Event(), Event()
    start.set()
    monkeypatch.setattr(capture_module.sd, "default", type("Default", (), {"device": (0, 0)})())
    monkeypatch.setattr(capture_module.sd, "check_input_settings", lambda **kwargs: None)
    monkeypatch.setattr(capture_module.sd, "InputStream", FakeStream)
    result = capture_module.capture_microphone(tmp_path / "mic.wav", stop, ready, start)
    assert result.frames == 8
    assert ready.is_set()
    assert captured["kwargs"]["channels"] == 2
    assert "start" not in captured["kwargs"]
    assert captured["stream"].closed


def test_microphone_queue_overflow_is_reported(monkeypatch, tmp_path):
    class FakeStream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            self.active = False

        def close(self):
            pass

        def stop(self):
            self.active = False

        def start(self):
            data = np.zeros((1, 2), dtype=np.int16)
            for _ in range(66):
                try:
                    self.callback(data, 1, None, None)
                except capture_module.sd.CallbackAbort:
                    break

    stop, ready, start = Event(), Event(), Event()
    start.set()
    monkeypatch.setattr(capture_module.sd, "default", type("Default", (), {"device": (0, 0)})())
    monkeypatch.setattr(capture_module.sd, "check_input_settings", lambda **kwargs: None)
    monkeypatch.setattr(capture_module.sd, "InputStream", FakeStream)
    with pytest.raises(AudioCaptureError, match="queue overflow"):
        capture_module.capture_microphone(tmp_path / "mic.wav", stop, ready, start)


def test_recording_worker_exception_is_reported_and_no_final_wav(monkeypatch, tmp_path):
    import celvo.core.recorder as recorder

    class BrokenBackend:
        name = "mock"

        def capture_microphone(self, *args):
            raise AudioCaptureError("mic disconnected")

        def capture_system_audio(self, *args):
            raise AudioCaptureError("loopback unavailable")

    monkeypatch.setattr(recorder, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(recorder, "TEMP_DIR", tmp_path / "temporary")

    def dirs():
        (tmp_path / "audio").mkdir(exist_ok=True)
        (tmp_path / "temporary").mkdir(exist_ok=True)

    monkeypatch.setattr(recorder, "ensure_directories", dirs)
    monkeypatch.setattr(recorder, "get_audio_backend", lambda: BrokenBackend())
    with pytest.raises(AudioCaptureError, match="mic disconnected|loopback unavailable"):
        record_audio()
    assert not list((tmp_path / "audio").glob("recording_*.wav"))
    assert list((tmp_path / "temporary").glob("recording_*.partial"))


def test_portaudio_adc_time_is_mapped_to_monotonic_clock():
    assert map_stream_time(
        100.0, {"input_buffer_adc_time": 20.0, "current_time": 20.025}, pyaudio=True
    ) == pytest.approx(99.975)


def test_sounddevice_microphone_stream_uses_supported_lifecycle(monkeypatch, tmp_path):
    import numpy as np
    import sounddevice as sd

    from celvo.core.audio.capture import capture_microphone

    stop, ready, start = Event(), Event(), Event()
    start.set()
    observed = {}

    class FakeStream:
        active = True

        def __init__(self, **kwargs):
            observed.update(kwargs)

        def start(self):
            observed["callback"](np.zeros((8, 1), dtype=np.int16), 8, {}, None)
            stop.set()

        def stop(self):
            observed["stopped"] = True

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr(sd, "check_input_settings", lambda **_kwargs: None)
    monkeypatch.setattr(sd, "InputStream", FakeStream)
    result = capture_microphone(tmp_path / "mic.wav", stop, ready, start)

    assert ready.is_set()
    assert result.frames == 8
    assert "start" not in observed
    assert observed["stopped"] and observed["closed"]


def test_wasapi_loopback_uses_bounded_callback_queue(monkeypatch, tmp_path):
    stop, ready, start = Event(), Event(), Event()
    start.set()
    observed = {}

    class FakeStream:
        def __init__(self, **kwargs):
            observed.update(kwargs)

        def start_stream(self):
            callback = observed["stream_callback"]
            callback(b"\x10\x00\x10\x00" * 16, 16, {"input_buffer_adc_time": 1.0, "current_time": 1.0}, 0)
            stop.set()

        def stop_stream(self):
            pass

        def close(self):
            pass

        def is_active(self):
            return True

    class FakeAudio:
        def get_default_wasapi_loopback(self):
            return {
                "index": 5,
                "name": "Speakers loopback",
                "defaultSampleRate": 48000,
                "maxInputChannels": 2,
            }

        def is_format_supported(self, *args, **kwargs):
            return True

        def open(self, **kwargs):
            return FakeStream(**kwargs)

        def terminate(self):
            pass

    fake_module = type(
        "PyAudioModule",
        (),
        {
            "PyAudio": FakeAudio,
            "paInt16": 8,
            "paContinue": 0,
            "paAbort": 2,
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "pyaudiowpatch", fake_module)
    result = WindowsAudioBackend().capture_system_audio(tmp_path / "loopback.wav", stop, ready, start)
    assert result.frames >= 16
    assert observed["input_device_index"] == 5
    assert observed["start"] is False
    with wave.open(str(result.path), "rb") as recorded:
        assert recorded.getframerate() == 48000
        assert recorded.getnchannels() == 2
        assert b"\x10\x00\x10\x00" in recorded.readframes(recorded.getnframes())


def test_wasapi_loopback_records_silence_while_output_is_idle(monkeypatch, tmp_path):
    stop, ready, start = Event(), Event(), Event()
    start.set()

    class FakeStream:
        def start_stream(self):
            time.sleep(0.05)
            stop.set()

        def stop_stream(self):
            pass

        def close(self):
            pass

        def is_active(self):
            return True

    class FakeAudio:
        def get_default_wasapi_loopback(self):
            return {"index": 5, "name": "Speakers loopback", "defaultSampleRate": 48000,
                    "maxInputChannels": 2}

        def is_format_supported(self, *args, **kwargs):
            return True

        def open(self, **kwargs):
            return FakeStream()

        def terminate(self):
            pass

    fake_module = type("PyAudioModule", (), {
        "PyAudio": FakeAudio, "paInt16": 8, "paContinue": 0, "paAbort": 2
    })
    monkeypatch.setitem(__import__("sys").modules, "pyaudiowpatch", fake_module)

    result = WindowsAudioBackend().capture_system_audio(tmp_path / "idle.wav", stop, ready, start)

    assert result.frames > 0
    with wave.open(str(result.path), "rb") as recorded:
        assert recorded.getnframes() == result.frames
        assert set(recorded.readframes(result.frames)) <= {0}


def test_wasapi_stop_stops_producer_before_draining(monkeypatch, tmp_path):
    stop, ready, start = Event(), Event(), Event()
    start.set()
    producing, producer_done = Event(), Event()

    class FakeStream:
        def __init__(self, callback):
            self.callback = callback
            self.active = False

        def start_stream(self):
            self.active = True
            producing.set()

            def produce():
                while self.active:
                    self.callback(
                        b"\x01\x00\x01\x00" * 16, 16,
                        {"input_buffer_adc_time": 1.0, "current_time": 1.0}, 0
                    )
                    time.sleep(0.002)
                producer_done.set()

            self.thread = threading.Thread(target=produce)
            self.thread.start()

        def stop_stream(self):
            self.active = False
            self.thread.join(timeout=2)

        def close(self):
            pass

        def is_active(self):
            return self.active

    class FakeAudio:
        def get_default_wasapi_loopback(self):
            return {"index": 5, "name": "Speakers loopback", "defaultSampleRate": 48000,
                    "maxInputChannels": 2}

        def is_format_supported(self, *args, **kwargs):
            return True

        def open(self, **kwargs):
            return FakeStream(kwargs["stream_callback"])

        def terminate(self):
            pass

    fake_module = type("PyAudioModule", (), {
        "PyAudio": FakeAudio, "paInt16": 8, "paContinue": 0, "paAbort": 2
    })
    monkeypatch.setitem(__import__("sys").modules, "pyaudiowpatch", fake_module)
    output = tmp_path / "stopped.wav"
    result_holder = []
    error_holder = []

    def capture():
        try:
            result_holder.append(WindowsAudioBackend().capture_system_audio(output, stop, ready, start))
        except Exception as exc:  # surfaced in the main test thread
            error_holder.append(exc)

    worker = threading.Thread(target=capture)
    worker.start()
    assert producing.wait(2)
    time.sleep(0.05)
    stop.set()
    worker.join(timeout=3)

    assert not worker.is_alive(), "capture must stop even while callbacks keep producing blocks"
    assert producer_done.is_set()
    assert not error_holder
    assert result_holder and result_holder[0].frames > 0


def test_wasapi_loopback_places_audio_after_idle_silence(monkeypatch, tmp_path):
    stop, ready, start = Event(), Event(), Event()
    start.set()
    observed = {}

    class FakeStream:
        def start_stream(self):
            time.sleep(0.06)
            observed["stream_callback"](
                b"\x10\x00\x10\x00" * 16, 16,
                {"input_buffer_adc_time": 1.0, "current_time": 1.0}, 0
            )
            stop.set()

        def stop_stream(self):
            pass

        def close(self):
            pass

        def is_active(self):
            return True

    class FakeAudio:
        def get_default_wasapi_loopback(self):
            return {"index": 5, "name": "Speakers loopback", "defaultSampleRate": 48000,
                    "maxInputChannels": 2}

        def is_format_supported(self, *args, **kwargs):
            return True

        def open(self, **kwargs):
            observed.update(kwargs)
            return FakeStream()

        def terminate(self):
            pass

    fake_module = type("PyAudioModule", (), {
        "PyAudio": FakeAudio, "paInt16": 8, "paContinue": 0, "paAbort": 2
    })
    monkeypatch.setitem(__import__("sys").modules, "pyaudiowpatch", fake_module)

    result = WindowsAudioBackend().capture_system_audio(tmp_path / "delayed.wav", stop, ready, start)

    with wave.open(str(result.path), "rb") as recorded:
        samples = recorded.readframes(recorded.getnframes())
    assert samples[:16 * 4] == bytes(16 * 4)
    assert b"\x10\x00\x10\x00" in samples
    assert result.frames > 16


def test_wasapi_callback_overflow_is_reported(monkeypatch, tmp_path):
    stop, ready, start = Event(), Event(), Event()
    start.set()
    observed = {}

    class FakeStream:
        def __init__(self, **kwargs):
            observed.update(kwargs)
        def start_stream(self):
            observed["stream_callback"](b"\0\0\0\0", 1, {}, 1)
        def stop_stream(self): pass
        def close(self): pass
        def is_active(self): return True

    class FakeAudio:
        def get_default_wasapi_loopback(self):
            return {"index": 5, "name": "Speakers loopback", "defaultSampleRate": 48000,
                    "maxInputChannels": 2}
        def is_format_supported(self, *args, **kwargs): return True
        def open(self, **kwargs): return FakeStream(**kwargs)
        def terminate(self): pass

    fake_module = type("PyAudioModule", (), {
        "PyAudio": FakeAudio, "paInt16": 8, "paContinue": 0, "paAbort": 2
    })
    monkeypatch.setitem(__import__("sys").modules, "pyaudiowpatch", fake_module)
    with pytest.raises(AudioCaptureError, match="overflow/status"):
        WindowsAudioBackend().capture_system_audio(tmp_path / "loopback.wav", stop, ready, start)


def test_successful_recording_is_atomically_finalized_and_temp_is_cleaned(monkeypatch, tmp_path):
    import time

    import celvo.core.recorder as recorder

    class FakeBackend:
        name = "mock"

        def _write(self, path, stop, ready, start, channels):
            ready.set()
            assert start.wait(2)
            frames, rate = 1600, 16000
            began = time.monotonic()
            with wave.open(str(path), "wb") as output:
                output.setnchannels(channels)
                output.setsampwidth(2)
                output.setframerate(rate)
                output.writeframes(b"\x01\x00" * frames * channels)
            return TrackInfo(path, rate, channels, frames, began, began + frames / rate)

        def capture_microphone(self, path, stop, ready, start, device=None):
            return self._write(path, stop, ready, start, channels=1)

        def capture_system_audio(self, path, stop, ready, start, device=None):
            return self._write(path, stop, ready, start, channels=2)

    audio_dir, temp_dir = tmp_path / "audio", tmp_path / "temporary"
    monkeypatch.setattr(recorder, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(recorder, "TEMP_DIR", temp_dir)
    monkeypatch.setattr(recorder, "ensure_directories", lambda: (audio_dir.mkdir(), temp_dir.mkdir()))
    monkeypatch.setattr(recorder, "get_next_id", lambda: 1)
    monkeypatch.setattr(recorder, "get_audio_backend", FakeBackend)
    output = recorder.record_audio()
    assert output.is_file()
    assert not list(temp_dir.iterdir())
    with wave.open(str(output), "rb") as recorded:
        assert recorded.getnframes() >= 1600


def test_record_audio_accepts_external_stop_event_for_desktop_controller(monkeypatch, tmp_path):
    import celvo.core.recorder as recorder

    class StoppableBackend:
        name = "mock"

        def capture_microphone(self, path, stop, ready, start, device=None):
            ready.set()
            assert start.wait(2)
            assert stop.wait(2)
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\x01\x00" * 1600)
            now = time.monotonic()
            return TrackInfo(path, 16000, 1, 1600, now, now + 0.1)

        def capture_system_audio(self, *args, **kwargs):
            raise AssertionError("System audio should not be started for microphone-only capture")

    audio_dir, temp_dir = tmp_path / "audio", tmp_path / "temporary"
    monkeypatch.setattr(recorder, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(recorder, "TEMP_DIR", temp_dir)
    monkeypatch.setattr(recorder, "ensure_directories", lambda: (audio_dir.mkdir(), temp_dir.mkdir()))
    monkeypatch.setattr(recorder, "get_next_id", lambda: 1)
    monkeypatch.setattr(recorder, "get_audio_backend", StoppableBackend)
    stop = Event()
    progress = []

    def stop_after_start(elapsed):
        progress.append(elapsed)
        if elapsed == 0:
            stop.set()

    output = recorder.record_audio("microphone", stop_event=stop, progress_callback=stop_after_start)

    assert output.is_file()
    assert progress[0] == 0
    with wave.open(str(output), "rb") as recorded:
        assert recorded.getnframes() in (1600, 1601, 1602)
