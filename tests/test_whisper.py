from __future__ import annotations

import wave
from pathlib import Path
from threading import Event

import pytest

from celvo.core import whisper


def valid_wav(path):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\0\0" * 16)


def test_reports_missing_executable_and_model(monkeypatch, tmp_path):
    audio = tmp_path / "audio.wav"
    valid_wav(audio)
    monkeypatch.setattr(whisper, "WHISPER_CLI", tmp_path / "missing.exe")
    with pytest.raises(RuntimeError, match="whisper.cpp executable"):
        whisper.transcribe_audio(audio)


def test_reports_missing_model(monkeypatch, tmp_path):
    audio, exe = tmp_path / "audio.wav", tmp_path / "whisper-cli.exe"
    valid_wav(audio)
    exe.touch()
    monkeypatch.setattr(whisper, "WHISPER_CLI", exe)
    monkeypatch.setattr(whisper, "WHISPER_MODEL", tmp_path / "missing model.bin")
    with pytest.raises(RuntimeError, match="Whisper model was not found"):
        whisper.transcribe_audio(audio)


def test_subprocess_failure_is_not_success(monkeypatch, tmp_path):
    audio, exe, model = tmp_path / "audio.wav", tmp_path / "whisper-cli", tmp_path / "model.bin"
    valid_wav(audio)
    exe.touch()
    model.touch()
    monkeypatch.setattr(whisper, "WHISPER_CLI", exe)
    monkeypatch.setattr(whisper, "WHISPER_MODEL", model)

    class FakeProcess:
        returncode = 2
        stdout = ""
        stderr = "model load failed"

        def communicate(self, timeout=None):
            return self.stdout, self.stderr

    monkeypatch.setattr(whisper.subprocess, "Popen", lambda *a, **k: FakeProcess())
    with pytest.raises(RuntimeError, match="model load failed"):
        whisper.transcribe_audio(audio)


def test_validates_utf8_transcription(monkeypatch, tmp_path):
    audio, exe, model = tmp_path / "meeting.wav", tmp_path / "whisper-cli", tmp_path / "model.bin"
    valid_wav(audio)
    exe.touch()
    model.touch()
    monkeypatch.setattr(whisper, "WHISPER_CLI", exe)
    monkeypatch.setattr(whisper, "WHISPER_MODEL", model)

    class FakeProcess:
        returncode = 0

        def __init__(self, command):
            self.command = command

        def communicate(self, timeout=None):
            output_base = self.command[self.command.index("-of") + 1]
            (tmp_path / "transcription" / f"{Path(output_base).name}.txt").write_text(
                "hola, mundo\n", encoding="utf-8"
            )
            return "", ""

    def popen(command, **kwargs):
        return FakeProcess(command)

    monkeypatch.setattr(whisper, "OUTPUT_DIR", tmp_path / "transcription")
    monkeypatch.setattr(whisper.subprocess, "Popen", popen)
    result = whisper.transcribe_audio(audio)
    assert result["text"] == "hola, mundo\n"


def test_windows_transcription_suppresses_console_window(monkeypatch, tmp_path):
    audio, exe, model = tmp_path / "meeting.wav", tmp_path / "whisper-cli.exe", tmp_path / "model.bin"
    valid_wav(audio)
    exe.touch()
    model.touch()
    monkeypatch.setattr(whisper, "WHISPER_CLI", exe)
    monkeypatch.setattr(whisper, "WHISPER_MODEL", model)
    monkeypatch.setattr(whisper.os, "name", "nt")
    monkeypatch.setattr(whisper.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(whisper, "OUTPUT_DIR", tmp_path / "transcription")
    observed = {}

    class FakeProcess:
        returncode = 0

        def __init__(self, command):
            self.command = command

        def communicate(self, timeout=None):
            output_base = self.command[self.command.index("-of") + 1]
            output = tmp_path / "transcription" / f"{Path(output_base).name}.txt"
            output.write_text("ready", encoding="utf-8")
            return "", ""

    def popen(command, **kwargs):
        observed.update(kwargs)
        return FakeProcess(command)

    monkeypatch.setattr(whisper.subprocess, "Popen", popen)
    whisper.transcribe_audio(audio)
    assert observed["creationflags"] & 0x08000000


def test_transcription_cancellation_terminates_whisper_and_keeps_no_partial_transcript(monkeypatch, tmp_path):
    audio, exe, model = tmp_path / "meeting.wav", tmp_path / "whisper-cli", tmp_path / "model.bin"
    valid_wav(audio)
    exe.touch()
    model.touch()
    monkeypatch.setattr(whisper, "WHISPER_CLI", exe)
    monkeypatch.setattr(whisper, "WHISPER_MODEL", model)
    monkeypatch.setattr(whisper, "OUTPUT_DIR", tmp_path / "transcription")
    monkeypatch.setattr(whisper.subprocess, "TimeoutExpired", TimeoutError)
    cancel = Event()
    terminated = []

    class FakeProcess:
        returncode = None

        def communicate(self, timeout=None):
            if not terminated:
                cancel.set()
                raise TimeoutError()
            return "", ""

        def terminate(self):
            terminated.append("terminate")
            self.returncode = 1

        def kill(self):
            terminated.append("kill")
            self.returncode = -9

    monkeypatch.setattr(whisper.subprocess, "Popen", lambda *a, **k: FakeProcess())
    with pytest.raises(whisper.TranscriptionCancelled):
        whisper.transcribe_audio(audio, cancel_event=cancel)
    assert terminated == ["terminate"]
    assert not list((tmp_path / "transcription").glob("*.partial.txt"))


def test_terminate_active_transcriptions_stops_live_process(monkeypatch):
    calls = []

    class FakeProcess:
        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

    process = FakeProcess()
    monkeypatch.setattr(whisper, "_active_processes", {process})
    whisper.terminate_active_transcriptions()
    assert calls == ["terminate"]
