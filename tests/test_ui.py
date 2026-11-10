from __future__ import annotations

import os
import sys
import time
import wave
from pathlib import Path
from threading import Event
from types import ModuleType

import pytest

from celvo import main as cli
from celvo.core import processor
from celvo.ui import app as ui_app
from celvo.ui import theme
from celvo.ui.controller import RecordingController, TranscriptionController
from celvo.ui.library import delete_recording, list_recordings, open_local_path, rename_recording
from celvo.ui.theme import apply_theme


def _write_wav(path: Path, frames: int = 1600, rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"\x00\x00" * frames)


def test_recording_library_lists_valid_files_newest_first_and_transcript_status(tmp_path):
    audio_dir, transcripts = tmp_path / "recordings", tmp_path / "transcripts"
    older = audio_dir / "meeting one.wav"
    newer = audio_dir / "recording_002.wav"
    _write_wav(older, frames=8000, rate=16000)
    _write_wav(newer, frames=24000, rate=24000)
    broken = audio_dir / "broken.wav"
    broken.write_bytes(b"not a wav")
    transcripts.mkdir()
    (transcripts / "recording_002.txt").write_text("local transcript", encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 30, now - 30))
    os.utime(newer, (now, now))
    os.utime(broken, (now - 60, now - 60))

    entries = list_recordings(audio_dir, transcripts)

    assert [entry.path for entry in entries] == [newer, older, audio_dir / "broken.wav"]
    assert entries[0].duration_seconds == pytest.approx(1.0)
    assert entries[0].has_transcript
    assert entries[0].transcript_path == transcripts / "recording_002.txt"
    assert entries[1].duration_seconds == pytest.approx(0.5)
    assert not entries[1].has_transcript
    assert entries[2].duration_seconds is None


def test_open_local_path_reports_missing_file(tmp_path):
    with pytest.raises(RuntimeError, match="File does not exist"):
        open_local_path(tmp_path / "missing.wav")


def test_rename_recording_keeps_transcript_sidecar(tmp_path):
    audio_dir, transcripts = tmp_path / "audio", tmp_path / "transcription"
    source = audio_dir / "meeting.wav"
    transcript = transcripts / "meeting.txt"
    _write_wav(source)
    transcript.parent.mkdir()
    transcript.write_text("transcript", encoding="utf-8")
    entry = list_recordings(audio_dir, transcripts)[0]

    renamed = rename_recording(entry, "Team meeting.wav", transcripts)

    assert renamed == audio_dir / "Team meeting.wav"
    assert renamed.is_file()
    assert not source.exists()
    assert (transcripts / "Team meeting.txt").read_text(encoding="utf-8") == "transcript"
    assert not transcript.exists()


def test_rename_rejects_collision_and_invalid_windows_names(tmp_path):
    audio_dir = tmp_path / "audio"
    source = audio_dir / "meeting.wav"
    _write_wav(source)
    _write_wav(audio_dir / "existing.wav")
    entries = list_recordings(audio_dir, tmp_path / "transcription")
    entry = next(item for item in entries if item.path == source)

    with pytest.raises(FileExistsError, match="already exists"):
        rename_recording(entry, "existing")
    with pytest.raises(ValueError, match="not allow"):
        rename_recording(entry, "bad/name")
    with pytest.raises(ValueError, match="reserved"):
        rename_recording(entry, "CON")
    assert source.exists()


def test_delete_moves_audio_and_transcript_to_recycle_bin(monkeypatch, tmp_path):
    audio_dir, transcripts = tmp_path / "audio", tmp_path / "transcription"
    audio, transcript = audio_dir / "meeting.wav", transcripts / "meeting.txt"
    _write_wav(audio)
    transcript.parent.mkdir()
    transcript.write_text("text", encoding="utf-8")
    entry = list_recordings(audio_dir, transcripts)[0]
    trashed = []
    monkeypatch.setattr("celvo.ui.library.send2trash", lambda path: trashed.append(Path(path)))

    delete_recording(entry, transcripts)

    assert trashed == [transcript, audio]
    assert audio.exists() and transcript.exists()  # The mock leaves them available for recovery.


def test_recording_controller_emits_progress_completion_and_stops(tmp_path):
    output = tmp_path / "recording_001.wav"
    stop_seen = Event()

    def fake_record(source, microphone_device, system_device, *, stop_event, progress_callback):
        assert source == "both"
        assert microphone_device == 2
        assert system_device == 5
        progress_callback(0)
        assert stop_event.wait(2)
        stop_seen.set()
        return output

    controller = RecordingController(fake_record)
    controller.start("both", 2, 5)
    deadline = time.monotonic() + 2
    events = []
    while time.monotonic() < deadline and not any(e.kind == "recording_progress" for e in events):
        events.extend(controller.drain_events())
        time.sleep(0.01)
    controller.stop()
    while time.monotonic() < deadline and not any(e.kind == "recording_finished" for e in events):
        events.extend(controller.drain_events())
        time.sleep(0.01)

    assert stop_seen.is_set()
    assert any(e.kind == "recording_progress" and e.payload == 0 for e in events)
    assert any(e.kind == "recording_finished" and e.payload == output for e in events)


def test_recording_controller_propagates_worker_failure():
    def failed_record(*_args, **_kwargs):
        raise RuntimeError("USB microphone disconnected")

    controller = RecordingController(failed_record)
    controller.start("microphone", None, None)
    deadline = time.monotonic() + 2
    events = []
    while time.monotonic() < deadline and not any(e.kind == "recording_failed" for e in events):
        events.extend(controller.drain_events())
        time.sleep(0.01)
    assert any(e.kind == "recording_failed" and "disconnected" in e.payload for e in events)


def test_transcription_controller_processes_selected_recording():
    selected = Path("meeting selected.wav")
    transcript = Path("meeting selected.txt")

    def fake_process(path, *, status_callback, cancel_event):
        assert path == selected
        status_callback("Transcribing meeting selected.wav locally…")
        return transcript

    controller = TranscriptionController(fake_process)
    controller.start(selected)
    deadline = time.monotonic() + 2
    events = []
    while time.monotonic() < deadline and not any(e.kind == "transcription_finished" for e in events):
        events.extend(controller.drain_events())
        time.sleep(0.01)
    assert any(e.kind == "transcription_status" for e in events)
    assert any(e.kind == "transcription_finished" and e.payload == transcript for e in events)


def test_transcription_controller_reports_failure():
    controller = TranscriptionController(
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("model missing"))
    )
    controller.start(Path("selected.wav"))
    deadline = time.monotonic() + 2
    events = []
    while time.monotonic() < deadline and not any(e.kind == "transcription_failed" for e in events):
        events.extend(controller.drain_events())
        time.sleep(0.01)
    assert any(e.kind == "transcription_failed" and e.payload == "model missing" for e in events)


def test_process_audio_transcribes_selected_path_with_status(monkeypatch, tmp_path):
    selected = tmp_path / "selected.wav"
    selected.touch()
    monkeypatch.setattr(
        processor,
        "transcribe_audio",
        lambda path, **_kwargs: {"file": tmp_path / f"{path.stem}.txt", "language": "en", "text": "hello"},
    )
    statuses = []

    result = processor.process_audio(selected, status_callback=statuses.append)

    assert result == tmp_path / "selected.txt"
    assert statuses == [
        "Transcribing selected.wav locally with whisper.cpp…",
        f"Transcript saved: {result}",
    ]


def test_cli_ui_command_lazily_launches_window(monkeypatch):
    called = []
    fake_app = ModuleType("celvo.ui.app")
    fake_app.launch_ui = lambda: called.append(True)
    monkeypatch.setitem(sys.modules, "celvo.ui.app", fake_app)

    assert cli.main(["ui"]) == 0
    assert called == [True]


def test_desktop_shortcuts_are_configured_for_both_platform_installers():
    root = Path(__file__).resolve().parents[1]
    linux_setup = (root / "setup.sh").read_text(encoding="utf-8")
    windows_setup = (root / "install.ps1").read_text(encoding="utf-8")

    assert 'import tkinter' in linux_setup
    assert "celvo.desktop" in linux_setup and "ui" in linux_setup
    assert "WScript.Shell" in windows_setup and "Celvo.lnk" in windows_setup
    assert "celvo-ui.pyw" in windows_setup and "launch_ui" in windows_setup


def test_theme_applies_dark_palette():
    class FakeStyle:
        def __init__(self):
            self.configured = {}

        def theme_use(self, name):
            self.theme = name

        def configure(self, name, **kwargs):
            self.configured[name] = kwargs

        def map(self, *_args, **_kwargs):
            pass

    class FakeRoot:
        def configure(self, **kwargs):
            self.configured = kwargs

    style, root = FakeStyle(), FakeRoot()
    apply_theme(root, style)
    assert style.theme == "clam"
    assert style.configured["TLabel"]["background"] == "#202124"
    assert root.configured["background"] == "#202124"


def test_windows_titlebar_requests_dark_dwm_attribute(monkeypatch):
    calls = []

    class FakeDwmCall:
        argtypes = None
        restype = None

        def __call__(self, hwnd, attribute, _value, _size):
            calls.append((hwnd.value, attribute))
            return 0

    class FakeDwm:
        DwmSetWindowAttribute = FakeDwmCall()

    class FakeUser32Call:
        argtypes = None
        restype = None

        def __call__(self, hwnd, _flag):
            return 54321

    class FakeUser32:
        GetAncestor = FakeUser32Call()

    class FakeRoot:
        def winfo_id(self):
            return 12345

    monkeypatch.setattr(theme.sys, "platform", "win32")
    monkeypatch.setattr(
        theme.ctypes,
        "WinDLL",
        lambda name: FakeUser32() if name == "user32" else FakeDwm(),
        raising=False,
    )

    assert theme.apply_windows_dark_titlebar(FakeRoot())
    assert calls == [(54321, 20)]


def test_ui_is_dark_only_and_has_no_refresh_controls():
    source = (Path(__file__).resolve().parents[1] / "celvo" / "ui" / "app.py").read_text(
        encoding="utf-8"
    )
    assert "Light mode" not in source
    assert "Dark mode" not in source
    assert "Refresh devices" not in source
    assert 'text="Refresh"' not in source


def test_transcription_ready_notification_is_visual_and_audible(monkeypatch, tmp_path):
    class FakeRoot:
        def __init__(self):
            self.bells = 0

        def bell(self):
            self.bells += 1

    root = FakeRoot()
    shown = []
    monkeypatch.setattr(ui_app.sys, "platform", "linux")
    monkeypatch.setattr(ui_app.messagebox, "showinfo", lambda *args, **kwargs: shown.append((args, kwargs)))

    ui_app.notify_transcription_ready(root, tmp_path / "ready.txt")

    assert root.bells == 1
    assert shown and shown[0][0][0] == "Transcription ready"


def test_transcription_ready_uses_windows_system_sound(monkeypatch, tmp_path):
    class FakeRoot:
        def bell(self):
            raise AssertionError("Windows should use winsound, not the Tk bell")

    sounds = []
    winsound = ModuleType("winsound")
    winsound.MB_ICONINFORMATION = 0x40
    winsound.MessageBeep = lambda sound: sounds.append(sound)
    monkeypatch.setattr(ui_app.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winsound", winsound)
    monkeypatch.setattr(ui_app.messagebox, "showinfo", lambda *args, **kwargs: None)

    ui_app.notify_transcription_ready(FakeRoot(), tmp_path / "ready.txt")

    assert sounds == [0x40]


def test_close_no_keeps_celvo_running(monkeypatch):
    app = ui_app.CelvoWindow.__new__(ui_app.CelvoWindow)
    app.root = type("Root", (), {"destroy": lambda _self: pytest.fail("window should stay open")})()
    app._closing = False
    app._recording_active = app._transcribing = True
    monkeypatch.setattr(ui_app.messagebox, "askyesno", lambda *a, **k: False)
    monkeypatch.setattr(ui_app.os, "_exit", lambda _code: pytest.fail("Celvo should keep running"))

    app.close()

    assert not app._closing


def test_close_yes_terminates_active_work_and_exits(monkeypatch):
    app = ui_app.CelvoWindow.__new__(ui_app.CelvoWindow)
    calls = []
    app.root = type("Root", (), {"destroy": lambda _self: calls.append("destroy")})()
    app._closing = False
    app._recording_active = app._transcribing = True
    app.recording = type("Recording", (), {"stop": lambda _self: calls.append("stop_recording")})()
    app.transcription = type(
        "Transcription", (), {"cancel": lambda _self: calls.append("cancel_transcription")}
    )()
    monkeypatch.setattr(ui_app.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(ui_app.os, "_exit", lambda code: calls.append(("exit", code)))

    app.close()

    assert calls == ["stop_recording", "cancel_transcription", "destroy", ("exit", 0)]
